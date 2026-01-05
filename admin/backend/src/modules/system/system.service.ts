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
    // 인프라 서비스 체크
    const infraServices = await Promise.all([
      this.checkPostgres(),
      this.checkRedis(),
      this.checkWeaviate(),
      this.checkMinio(),
    ]);

    // Celery 워커 상태 체크 (Flower API 통해)
    const workerServices = await this.checkCeleryWorkers();

    const services = [...infraServices, ...workerServices];

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

  /**
   * Celery 워커들 상태 체크 (Flower API 통해)
   * - Flower 자체 상태
   * - 개별 워커 상태 (backfill, embed, beat)
   */
  private async checkCeleryWorkers(): Promise<ServiceStatus[]> {
    const start = Date.now();
    const host = this.configService.get('FLOWER_HOST', 'localhost');
    const port = this.configService.get('FLOWER_PORT', 15555);
    const url = `http://${host}:${port}/api/workers`;

    // 워커 이름 → ServiceName 매핑
    const workerMapping: Record<string, ServiceName> = {
      backfill: ServiceName.CELERY_BACKFILL,
      embed: ServiceName.CELERY_EMBED,
    };

    // 기대하는 워커들
    const expectedWorkers = [
      ServiceName.CELERY_BACKFILL,
      ServiceName.CELERY_EMBED,
    ];

    try {
      const response = await firstValueFrom(
        this.httpService.get(url, { headers: this.getFlowerAuthHeaders() }).pipe(
          timeout(5000),
          catchError(() => of(null)),
        ),
      );

      const results: ServiceStatus[] = [];

      // Flower 자체 상태
      if (response?.data) {
        results.push({
          name: ServiceName.CELERY_FLOWER,
          status: ServiceHealthStatus.HEALTHY,
          latency: Date.now() - start,
        });

        // 워커 데이터 파싱
        const workersData = response.data as Record<string, {
          status?: boolean;
          active?: number;
          stats?: { total?: Record<string, number> };
        }>;

        // 발견된 워커들 추적
        const foundWorkers = new Set<ServiceName>();

        for (const [, info] of Object.entries(workersData)) {
          // 워커 이름에서 타입 추출 (예: "celery@abc123" → queue 이름으로 매핑)
          // Flower API는 워커 이름을 "celery@hostname" 형태로 반환
          // 우리는 active_queues를 확인해서 어떤 워커인지 판단해야 함
          const workerInfo = info as {
            status?: boolean;
            active?: number;
            active_queues?: Array<{ name: string }>;
          };

          const queues = workerInfo.active_queues?.map(q => q.name) || [];

          for (const queue of queues) {
            const serviceName = workerMapping[queue];
            if (serviceName && !foundWorkers.has(serviceName)) {
              foundWorkers.add(serviceName);

              const isOnline = workerInfo.status !== false;
              results.push({
                name: serviceName,
                status: isOnline ? ServiceHealthStatus.HEALTHY : ServiceHealthStatus.UNHEALTHY,
                details: {
                  active: workerInfo.active || 0,
                  queues,
                },
              });
            }
          }
        }

        // 기대하는 워커 중 발견되지 않은 것들은 UNHEALTHY
        for (const expected of expectedWorkers) {
          if (!foundWorkers.has(expected)) {
            results.push({
              name: expected,
              status: ServiceHealthStatus.UNHEALTHY,
              message: 'Worker not found',
            });
          }
        }

      } else {
        // Flower 응답 없음 - 모든 워커 상태 unknown
        results.push({
          name: ServiceName.CELERY_FLOWER,
          status: ServiceHealthStatus.UNHEALTHY,
          message: 'No response from Flower',
        });

        for (const expected of expectedWorkers) {
          results.push({
            name: expected,
            status: ServiceHealthStatus.UNKNOWN,
            message: 'Cannot check - Flower unavailable',
          });
        }

      }

      return results;

    } catch (error) {
      // Flower 연결 실패
      return [
        {
          name: ServiceName.CELERY_FLOWER,
          status: ServiceHealthStatus.UNHEALTHY,
          message: error instanceof Error ? error.message : 'Connection failed',
        },
        ...expectedWorkers.map(name => ({
          name,
          status: ServiceHealthStatus.UNKNOWN,
          message: 'Cannot check - Flower unavailable',
        })),
      ];
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
