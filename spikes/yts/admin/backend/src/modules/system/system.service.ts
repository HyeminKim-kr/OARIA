import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { DataSource } from 'typeorm';
import { HttpService } from '@nestjs/axios';
import Redis from 'ioredis';
import { firstValueFrom, timeout, catchError } from 'rxjs';
import { of } from 'rxjs';
import {
  ServiceStatus,
  SystemHealth,
  CeleryWorkerInfo,
  CeleryQueueInfo,
  TaskTriggerResult,
  ServiceHealthStatus,
  SystemHealthStatus,
  CeleryWorkerStatus,
  ServiceName,
} from './types';

// Re-export types for controller
export {
  ServiceStatus,
  SystemHealth,
  CeleryWorkerInfo,
  CeleryQueueInfo,
  TaskTriggerResult,
} from './types';

@Injectable()
export class SystemService {
  private readonly logger = new Logger(SystemService.name);
  private redis: Redis | null = null;

  constructor(
    private readonly dataSource: DataSource,
    private readonly configService: ConfigService,
    private readonly httpService: HttpService,
  ) {
    this.initRedis();
  }

  private initRedis(): void {
    const host = this.configService.get('REDIS_HOST', 'localhost');
    const port = this.configService.get('REDIS_PORT', 16379);

    this.redis = new Redis({
      host,
      port: Number(port),
      lazyConnect: true,
      maxRetriesPerRequest: 1,
      connectTimeout: 3000,
    });
  }

  /**
   * Flower API Basic Auth 헤더 생성
   */
  private getFlowerAuthHeaders(): Record<string, string> {
    const user = this.configService.get('FLOWER_USER', 'admin');
    const password = this.configService.get('FLOWER_PASSWORD', 'flower_dev_2024');
    const token = Buffer.from(`${user}:${password}`).toString('base64');
    return {
      Authorization: `Basic ${token}`,
    };
  }

  async getSystemHealth(): Promise<SystemHealth> {
    const services = await Promise.all([
      this.checkPostgres(),
      this.checkRedis(),
      this.checkWeaviate(),
      this.checkMinio(),
      this.checkFlower(),
    ]);

    const unhealthyCount = services.filter(
      (s) => s.status === ServiceHealthStatus.UNHEALTHY,
    ).length;

    let overallStatus: SystemHealthStatus;
    if (unhealthyCount === 0) {
      overallStatus = SystemHealthStatus.HEALTHY;
    } else if (unhealthyCount === services.length) {
      overallStatus = SystemHealthStatus.UNHEALTHY;
    } else {
      overallStatus = SystemHealthStatus.DEGRADED;
    }

    return {
      status: overallStatus,
      timestamp: new Date().toISOString(),
      services,
    };
  }

  private async checkPostgres(): Promise<ServiceStatus> {
    const start = Date.now();
    try {
      await this.dataSource.query('SELECT 1');
      return {
        name: ServiceName.POSTGRESQL,
        status: ServiceHealthStatus.HEALTHY,
        latency: Date.now() - start,
      };
    } catch (error) {
      return {
        name: ServiceName.POSTGRESQL,
        status: ServiceHealthStatus.UNHEALTHY,
        message: error instanceof Error ? error.message : 'Connection failed',
      };
    }
  }

  private async checkRedis(): Promise<ServiceStatus> {
    const start = Date.now();
    try {
      if (!this.redis) {
        this.initRedis();
      }

      await this.redis!.ping();
      return {
        name: ServiceName.REDIS,
        status: ServiceHealthStatus.HEALTHY,
        latency: Date.now() - start,
      };
    } catch (error) {
      return {
        name: ServiceName.REDIS,
        status: ServiceHealthStatus.UNHEALTHY,
        message: error instanceof Error ? error.message : 'Connection failed',
      };
    }
  }

  private async checkWeaviate(): Promise<ServiceStatus> {
    const start = Date.now();
    const host = this.configService.get('WEAVIATE_HOST', 'localhost');
    const port = this.configService.get('WEAVIATE_PORT', 18080);
    const url = `http://${host}:${port}/v1/.well-known/ready`;

    try {
      const response = await firstValueFrom(
        this.httpService.get(url).pipe(
          timeout(3000),
          catchError(() => of(null)),
        ),
      );

      if (response) {
        return {
          name: ServiceName.WEAVIATE,
          status: ServiceHealthStatus.HEALTHY,
          latency: Date.now() - start,
        };
      }

      return {
        name: ServiceName.WEAVIATE,
        status: ServiceHealthStatus.UNHEALTHY,
        message: 'Connection failed',
      };
    } catch (error) {
      return {
        name: ServiceName.WEAVIATE,
        status: ServiceHealthStatus.UNHEALTHY,
        message: error instanceof Error ? error.message : 'Connection failed',
      };
    }
  }

  private async checkMinio(): Promise<ServiceStatus> {
    const start = Date.now();
    const endpoint = this.configService.get('S3_ENDPOINT', 'http://localhost:19000');
    const url = `${endpoint}/minio/health/live`;

    try {
      const response = await firstValueFrom(
        this.httpService.get(url).pipe(
          timeout(3000),
          catchError(() => of(null)),
        ),
      );

      if (response) {
        return {
          name: ServiceName.MINIO,
          status: ServiceHealthStatus.HEALTHY,
          latency: Date.now() - start,
        };
      }

      return {
        name: ServiceName.MINIO,
        status: ServiceHealthStatus.UNHEALTHY,
        message: 'Connection failed',
      };
    } catch (error) {
      return {
        name: ServiceName.MINIO,
        status: ServiceHealthStatus.UNHEALTHY,
        message: error instanceof Error ? error.message : 'Connection failed',
      };
    }
  }

  private async checkFlower(): Promise<ServiceStatus> {
    const start = Date.now();
    const host = this.configService.get('FLOWER_HOST', 'localhost');
    const port = this.configService.get('FLOWER_PORT', 15555);
    const url = `http://${host}:${port}/api/workers`;

    try {
      const response = await firstValueFrom(
        this.httpService.get(url, { headers: this.getFlowerAuthHeaders() }).pipe(
          timeout(3000),
          catchError(() => of(null)),
        ),
      );

      if (response?.data) {
        const workers = Object.keys(response.data);
        return {
          name: ServiceName.CELERY_FLOWER,
          status: ServiceHealthStatus.HEALTHY,
          latency: Date.now() - start,
          details: { workers: workers.length },
        };
      }

      return {
        name: ServiceName.CELERY_FLOWER,
        status: ServiceHealthStatus.UNHEALTHY,
        message: 'No response from Flower',
      };
    } catch (error) {
      return {
        name: ServiceName.CELERY_FLOWER,
        status: ServiceHealthStatus.UNHEALTHY,
        message: error instanceof Error ? error.message : 'Connection failed',
      };
    }
  }

  async getCeleryWorkers(): Promise<CeleryWorkerInfo[]> {
    const host = this.configService.get('FLOWER_HOST', 'localhost');
    const port = this.configService.get('FLOWER_PORT', 15555);
    const url = `http://${host}:${port}/api/workers`;

    try {
      const response = await firstValueFrom(
        this.httpService.get(url, { headers: this.getFlowerAuthHeaders() }).pipe(
          timeout(5000),
          catchError(() => of({ data: {} })),
        ),
      );

      const workers: CeleryWorkerInfo[] = [];
      for (const [name, info] of Object.entries(response.data)) {
        const workerInfo = info as {
          status?: boolean;
          active?: number;
          stats?: { total?: Record<string, number> };
          active_queues?: Array<{ name: string }>;
        };

        workers.push({
          name,
          status: workerInfo?.status ? CeleryWorkerStatus.ONLINE : CeleryWorkerStatus.OFFLINE,
          active: workerInfo?.active || 0,
          processed: Object.values(workerInfo?.stats?.total || {}).reduce((sum: number, val) => sum + (val as number), 0),
          queues: (workerInfo?.active_queues || []).map((q) => q.name),
        });
      }

      return workers;
    } catch (error) {
      this.logger.error('Failed to get Celery workers', error);
      return [];
    }
  }

  async getCeleryQueues(): Promise<CeleryQueueInfo[]> {
    const host = this.configService.get('FLOWER_HOST', 'localhost');
    const port = this.configService.get('FLOWER_PORT', 15555);

    const queues = ['backfill', 'embed', 'celery'];
    const results: CeleryQueueInfo[] = [];

    for (const queue of queues) {
      try {
        const url = `http://${host}:${port}/api/queues/length`;
        const response = await firstValueFrom(
          this.httpService.get(url, { headers: this.getFlowerAuthHeaders() }).pipe(
            timeout(3000),
            catchError(() => of({ data: { active_queues: [] } })),
          ),
        );

        const queueData = response.data?.active_queues?.find(
          (q: { name: string }) => q.name === queue
        );

        results.push({
          name: queue,
          pending: queueData?.messages || 0,
        });
      } catch {
        results.push({ name: queue, pending: 0 });
      }
    }

    return results;
  }

  async triggerEmbedding(limit: number = 50): Promise<TaskTriggerResult> {
    const host = this.configService.get('FLOWER_HOST', 'localhost');
    const port = this.configService.get('FLOWER_PORT', 15555);
    const url = `http://${host}:${port}/api/task/async-apply/src.tasks.embed.run_embed`;

    try {
      const response = await firstValueFrom(
        this.httpService.post(
          url,
          {
            args: [null, limit],
            kwargs: {},
            options: { queue: 'embed' },
          },
          { headers: this.getFlowerAuthHeaders() },
        ).pipe(
          timeout(5000),
        ),
      );

      return {
        success: true,
        taskId: response.data?.task_id,
        message: `Embedding task triggered for ${limit} papers`,
      };
    } catch (error) {
      this.logger.error('Failed to trigger embedding', error);
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Failed to trigger task',
      };
    }
  }

  async triggerReembedding(limit?: number): Promise<TaskTriggerResult> {
    const host = this.configService.get('FLOWER_HOST', 'localhost');
    const port = this.configService.get('FLOWER_PORT', 15555);
    const url = `http://${host}:${port}/api/task/async-apply/src.tasks.embed.run_reembed`;

    try {
      const response = await firstValueFrom(
        this.httpService.post(
          url,
          {
            args: [null, limit || null],
            kwargs: {},
            options: { queue: 'embed' },
          },
          { headers: this.getFlowerAuthHeaders() },
        ).pipe(
          timeout(5000),
        ),
      );

      return {
        success: true,
        taskId: response.data?.task_id,
        message: `Re-embedding task triggered${limit ? ` for ${limit} papers` : ' for all failed papers'}`,
      };
    } catch (error) {
      this.logger.error('Failed to trigger re-embedding', error);
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Failed to trigger task',
      };
    }
  }
}
