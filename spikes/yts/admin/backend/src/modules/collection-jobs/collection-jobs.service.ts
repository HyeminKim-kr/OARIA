import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';
import { CollectionJob, JobStatus } from '../../entities/collection-job.entity';
import { ArticleError } from '../../entities/article-error.entity';
import {
  JobSearchOptions,
  JobErrorOptions,
  JobStats,
  JobErrorStats,
  TaskTriggerResult,
  JobStatusEnum,
} from './types';

// Re-export types for external use
export {
  JobSearchOptions,
  JobErrorOptions,
  JobStats,
  JobErrorStats,
  TaskTriggerResult,
} from './types';

@Injectable()
export class CollectionJobsService {
  private redis: Redis;

  constructor(
    @InjectRepository(CollectionJob)
    private readonly repository: Repository<CollectionJob>,
    @InjectRepository(ArticleError)
    private readonly articleErrorRepository: Repository<ArticleError>,
    private readonly configService: ConfigService,
  ) {
    // Redis 연결 (Celery 트리거용)
    this.redis = new Redis({
      host: this.configService.get('REDIS_HOST', 'localhost'),
      port: this.configService.get('REDIS_PORT', 16379),
    });
  }

  async findAll(options?: JobSearchOptions): Promise<CollectionJob[]> {
    const query = this.repository
      .createQueryBuilder('job')
      .leftJoinAndSelect('job.searchQuery', 'searchQuery')
      .orderBy('job.createdAt', 'DESC');

    if (options?.status) {
      query.andWhere('job.status = :status', { status: options.status });
    }
    if (options?.jobType) {
      query.andWhere('job.jobType = :jobType', { jobType: options.jobType });
    }
    if (options?.limit) {
      query.take(options.limit);
    }

    return query.getMany();
  }

  async findOne(id: string): Promise<CollectionJob> {
    const job = await this.repository.findOne({
      where: { id },
      relations: ['searchQuery'],
    });
    if (!job) {
      throw new NotFoundException(`CollectionJob #${id} not found`);
    }
    return job;
  }

  async getRunningJobs(): Promise<CollectionJob[]> {
    return this.repository.find({
      where: { status: JobStatusEnum.RUNNING as JobStatus },
      relations: ['searchQuery'],
      order: { startedAt: 'DESC' },
    });
  }

  async triggerBackfill(queryId: string): Promise<TaskTriggerResult> {
    // Celery 태스크 트리거 (Redis LPUSH)
    // 참고: queryId 존재 검증은 Controller에서 수행됨
    const taskId = this.generateTaskId();
    const message = JSON.stringify({
      body: Buffer.from(JSON.stringify([[queryId], {}, {}])).toString('base64'),
      'content-encoding': 'utf-8',
      'content-type': 'application/json',
      headers: {
        task: 'src.tasks.backfill.run_backfill',
        id: taskId,
        lang: 'py',
        root_id: taskId,
        parent_id: null,
        group: null,
      },
      properties: {
        correlation_id: taskId,
        reply_to: null,
        delivery_mode: 2,
        delivery_info: { exchange: '', routing_key: 'backfill' },
        priority: 0,
        body_encoding: 'base64',
        delivery_tag: taskId,
      },
    });

    // Celery 메시지 형식으로 전송
    await this.redis.lpush('backfill', message);

    return { taskId };
  }

  async cancelJob(id: string): Promise<CollectionJob> {
    const job = await this.findOne(id);
    if (job.status !== JobStatusEnum.RUNNING && job.status !== JobStatusEnum.PENDING) {
      throw new BadRequestException('Only running or pending jobs can be cancelled');
    }

    job.status = JobStatusEnum.CANCELLED as JobStatus;
    job.completedAt = new Date();
    return this.repository.save(job);
  }

  async retryJob(id: string): Promise<TaskTriggerResult> {
    const job = await this.findOne(id);

    if (job.status !== JobStatusEnum.FAILED && job.status !== JobStatusEnum.CANCELLED) {
      throw new BadRequestException('Only failed or cancelled jobs can be retried');
    }

    if (!job.queryId) {
      throw new BadRequestException('Job has no associated query_id');
    }

    // 기존 job을 'retried' 상태로 변경 (자동 Retry 대상에서 제외)
    job.status = JobStatusEnum.RETRIED as JobStatus;
    job.attemptCount = (job.attemptCount || 0) + 1;
    await this.repository.save(job);

    // 새 backfill 트리거 (같은 query_id로)
    const result = await this.triggerBackfill(job.queryId);

    return {
      taskId: result.taskId,
      newJobTriggered: true,
    };
  }

  async resumeJob(id: string): Promise<TaskTriggerResult> {
    const job = await this.findOne(id);

    // partial 또는 failed 상태만 resume 가능
    if (job.status !== JobStatusEnum.PARTIAL && job.status !== JobStatusEnum.FAILED) {
      throw new BadRequestException('Only partial or failed jobs can be resumed');
    }

    if (!job.queryId) {
      throw new BadRequestException('Job has no associated query_id');
    }

    // job을 running으로 변경
    job.status = JobStatusEnum.RUNNING as JobStatus;
    job.lockedAt = new Date();
    await this.repository.save(job);

    // 기존 job_id로 resume 트리거
    const taskId = this.generateTaskId();
    const message = JSON.stringify({
      body: Buffer.from(JSON.stringify([[job.queryId, id], {}, {}])).toString('base64'),
      'content-encoding': 'utf-8',
      'content-type': 'application/json',
      headers: {
        task: 'src.tasks.backfill.run_backfill_resume',
        id: taskId,
        lang: 'py',
        root_id: taskId,
        parent_id: null,
        group: null,
      },
      properties: {
        correlation_id: taskId,
        reply_to: null,
        delivery_mode: 2,
        delivery_info: { exchange: '', routing_key: 'backfill' },
        priority: 0,
        body_encoding: 'base64',
        delivery_tag: taskId,
      },
    });

    await this.redis.lpush('backfill', message);

    return { taskId, resumed: true };
  }

  async getStats(): Promise<JobStats> {
    const [total, pending, running, completed, failed, todayStats] =
      await Promise.all([
        this.repository.count(),
        this.repository.count({ where: { status: JobStatusEnum.PENDING as JobStatus } }),
        this.repository.count({ where: { status: JobStatusEnum.RUNNING as JobStatus } }),
        this.repository.count({ where: { status: JobStatusEnum.COMPLETED as JobStatus } }),
        this.repository.count({ where: { status: JobStatusEnum.FAILED as JobStatus } }),
        this.repository
          .createQueryBuilder('job')
          .select('SUM(job.success_count)', 'todayCollected')
          .where('job.completed_at >= CURRENT_DATE')
          .getRawOne(),
      ]);

    return {
      total,
      pending,
      running,
      completed,
      failed,
      todayCollected: parseInt(todayStats?.todayCollected || '0', 10),
    };
  }

  private generateTaskId(): string {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 15)}`;
  }

  // ============================================================
  // Article Errors
  // ============================================================

  async getJobErrors(
    jobId: string,
    options?: JobErrorOptions,
  ): Promise<{ errors: ArticleError[]; total: number }> {
    const query = this.articleErrorRepository
      .createQueryBuilder('error')
      .where('error.job_id = :jobId', { jobId })
      .orderBy('error.created_at', 'DESC');

    if (options?.stage) {
      query.andWhere('error.stage = :stage', { stage: options.stage });
    }

    const total = await query.getCount();

    if (options?.limit) {
      query.take(options.limit);
    }
    if (options?.offset) {
      query.skip(options.offset);
    }

    const errors = await query.getMany();
    return { errors, total };
  }

  async getJobErrorStats(jobId: string): Promise<JobErrorStats> {
    const [stageStats, codeStats, total] = await Promise.all([
      this.articleErrorRepository
        .createQueryBuilder('error')
        .select('error.stage', 'stage')
        .addSelect('COUNT(*)', 'count')
        .where('error.job_id = :jobId', { jobId })
        .groupBy('error.stage')
        .getRawMany(),
      this.articleErrorRepository
        .createQueryBuilder('error')
        .select('error.error_code', 'code')
        .addSelect('COUNT(*)', 'count')
        .where('error.job_id = :jobId', { jobId })
        .andWhere('error.error_code IS NOT NULL')
        .groupBy('error.error_code')
        .getRawMany(),
      this.articleErrorRepository.count({ where: { jobId } }),
    ]);

    const byStage: Record<string, number> = {};
    for (const row of stageStats) {
      byStage[row.stage] = parseInt(row.count, 10);
    }

    const byCode: Record<string, number> = {};
    for (const row of codeStats) {
      byCode[row.code] = parseInt(row.count, 10);
    }

    return { total, byStage, byCode };
  }
}
