import { Injectable, Inject, Logger } from '@nestjs/common';
import Redis from 'ioredis';
import { REDIS_CLIENT } from '../redis/redis.module';
import {
  JobType,
  JobTypeValue,
  JobStatus,
  JobStatusValue,
  JobState,
  CreateJobOptions,
  JobStateResult,
  JOB_MANAGER_CONSTANTS,
} from './job-manager.types';

/**
 * Redis 기반 작업 상태 관리 서비스
 *
 * batch/src/job_manager.py의 JobStateManager를 NestJS로 포팅
 *
 * Redis 키 구조:
 * - job:{type}:{id}:state - Hash (상태, 진행률, heartbeat 등)
 * - job:{type}:{id}:lock - String (분산 락, 워커 ID)
 * - queue:{type}:pending - List (대기 중인 작업 ID)
 */
@Injectable()
export class JobManagerService {
  private readonly logger = new Logger(JobManagerService.name);

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  // ============================================================
  // 키 생성 헬퍼
  // ============================================================

  private stateKey(jobType: JobTypeValue, jobId: string): string {
    return `job:${jobType}:${jobId}:state`;
  }

  private lockKey(jobType: JobTypeValue, jobId: string): string {
    return `job:${jobType}:${jobId}:lock`;
  }

  private queueKey(jobType: JobTypeValue): string {
    return `queue:${jobType}:pending`;
  }

  // ============================================================
  // 작업 생성/조회
  // ============================================================

  /**
   * 작업 생성 및 큐에 추가
   */
  async createJob(options: CreateJobOptions): Promise<void> {
    const { jobId, jobType, metadata } = options;
    const stateKey = this.stateKey(jobType, jobId);
    const queueKey = this.queueKey(jobType);
    const now = new Date().toISOString();

    const state: Record<string, string | number> = {
      status: JobStatus.QUEUED,
      progress: 0,
      total: 0,
      retry_count: 0,
      error: '',
      worker_id: '',
      created_at: now,
      queued_at: now,
      started_at: '',
      completed_at: '',
      heartbeat: '',
      ...metadata,
    };

    // 상태 저장 + 큐에 추가 (atomic)
    const pipeline = this.redis.pipeline();
    pipeline.hset(stateKey, state);
    pipeline.rpush(queueKey, jobId);
    await pipeline.exec();

    this.logger.log(`Job created: ${jobId} (type: ${jobType})`);
  }

  /**
   * 작업 상태 조회
   */
  async getJobState(jobId: string, jobType: JobTypeValue): Promise<JobStateResult | null> {
    const stateKey = this.stateKey(jobType, jobId);
    const state = await this.redis.hgetall(stateKey);

    if (!state || Object.keys(state).length === 0) {
      return null;
    }

    return {
      status: state.status as JobStatusValue,
      progress: parseInt(state.progress || '0', 10),
      total: parseInt(state.total || '0', 10),
      retryCount: parseInt(state.retry_count || '0', 10),
      error: state.error || '',
      workerId: state.worker_id || '',
      createdAt: state.created_at || null,
      queuedAt: state.queued_at || null,
      startedAt: state.started_at || null,
      completedAt: state.completed_at || null,
      heartbeat: state.heartbeat || null,
      chunkCount: state.chunk_count ? parseInt(state.chunk_count, 10) : null,
    };
  }

  /**
   * 작업 존재 여부 확인
   */
  async jobExists(jobId: string, jobType: JobTypeValue): Promise<boolean> {
    const stateKey = this.stateKey(jobType, jobId);
    return (await this.redis.exists(stateKey)) > 0;
  }

  /**
   * 특정 타입의 모든 작업 상태 조회
   */
  async getAllJobs(jobType: JobTypeValue): Promise<Array<{ jobId: string; state: JobStateResult }>> {
    const pattern = `job:${jobType}:*:state`;
    const keys = await this.redis.keys(pattern);
    const jobs: Array<{ jobId: string; state: JobStateResult }> = [];

    for (const key of keys) {
      // key에서 jobId 추출: job:embed:xxx:state -> xxx
      const parts = key.split(':');
      if (parts.length >= 3) {
        const jobId = parts[2];
        const state = await this.getJobState(jobId, jobType);
        if (state) {
          jobs.push({ jobId, state });
        }
      }
    }

    return jobs;
  }

  // ============================================================
  // 재시도 / 취소
  // ============================================================

  /**
   * 작업 재시도 (failed 또는 stuck 상태에서)
   */
  async retryJob(jobId: string, jobType: JobTypeValue): Promise<boolean> {
    const stateKey = this.stateKey(jobType, jobId);
    const queueKey = this.queueKey(jobType);
    const lockKey = this.lockKey(jobType, jobId);

    const state = await this.redis.hgetall(stateKey);
    if (!state || Object.keys(state).length === 0) {
      this.logger.warn(`Retry failed: job not found - ${jobId}`);
      return false;
    }

    const retryCount = parseInt(state.retry_count || '0', 10);
    if (retryCount >= JOB_MANAGER_CONSTANTS.MAX_RETRIES) {
      this.logger.warn(`Retry failed: max retries exceeded - ${jobId} (${retryCount}/${JOB_MANAGER_CONSTANTS.MAX_RETRIES})`);
      return false;
    }

    const now = new Date().toISOString();
    const pipeline = this.redis.pipeline();
    pipeline.hset(stateKey, {
      status: JobStatus.QUEUED,
      queued_at: now,
      error: '',
      worker_id: '',
    });
    pipeline.rpush(queueKey, jobId);
    pipeline.del(lockKey); // 기존 락 제거
    await pipeline.exec();

    this.logger.log(`Job retried: ${jobId} (retry: ${retryCount + 1})`);
    return true;
  }

  /**
   * 작업 취소
   */
  async cancelJob(jobId: string, jobType: JobTypeValue): Promise<boolean> {
    const stateKey = this.stateKey(jobType, jobId);
    const lockKey = this.lockKey(jobType, jobId);

    const state = await this.redis.hgetall(stateKey);
    if (!state || Object.keys(state).length === 0) {
      return false;
    }

    // 이미 완료된 작업은 취소 불가
    if (state.status === JobStatus.COMPLETED) {
      return false;
    }

    const now = new Date().toISOString();
    const pipeline = this.redis.pipeline();
    pipeline.hset(stateKey, {
      status: JobStatus.CANCELLED,
      cancelled_at: now,
    });
    pipeline.del(lockKey);
    await pipeline.exec();

    this.logger.log(`Job cancelled: ${jobId}`);
    return true;
  }

  /**
   * 작업 삭제 (Redis에서)
   */
  async deleteJob(jobId: string, jobType: JobTypeValue): Promise<void> {
    const stateKey = this.stateKey(jobType, jobId);
    const lockKey = this.lockKey(jobType, jobId);

    await this.redis.del(stateKey, lockKey);
    this.logger.debug(`Job deleted from Redis: ${jobId}`);
  }

  // ============================================================
  // 큐 관리
  // ============================================================

  /**
   * 대기 큐의 작업 수
   */
  async getPendingCount(jobType: JobTypeValue): Promise<number> {
    const queueKey = this.queueKey(jobType);
    return await this.redis.llen(queueKey);
  }

  /**
   * 특정 상태의 작업 수
   */
  async getJobCountByStatus(
    jobType: JobTypeValue,
    status: JobStatusValue,
  ): Promise<number> {
    const jobs = await this.getAllJobs(jobType);
    return jobs.filter((j) => j.state.status === status).length;
  }

  // ============================================================
  // Papers 임베딩 전용 메서드
  // ============================================================

  /**
   * Papers 임베딩 배치 작업 생성
   * 개별 논문이 아닌 배치 단위로 관리
   */
  async createPaperBatchJob(batchId: string, paperIds: string[]): Promise<void> {
    await this.createJob({
      jobId: batchId,
      jobType: JobType.PAPER_EMBED,
      metadata: {
        total: paperIds.length,
        paper_ids: JSON.stringify(paperIds),
      },
    });
  }

  /**
   * Processing 상태의 모든 papers 배치 작업 취소
   */
  async cancelAllProcessingPaperJobs(): Promise<number> {
    const jobs = await this.getAllJobs(JobType.PAPER_EMBED);
    let cancelledCount = 0;

    for (const job of jobs) {
      if (job.state.status === JobStatus.PROCESSING) {
        const cancelled = await this.cancelJob(job.jobId, JobType.PAPER_EMBED);
        if (cancelled) {
          cancelledCount++;
        }
      }
    }

    return cancelledCount;
  }

  // ============================================================
  // 상태 통계
  // ============================================================

  /**
   * 작업 유형별 상태 통계
   */
  async getJobStats(jobType: JobTypeValue): Promise<Record<JobStatusValue, number>> {
    const jobs = await this.getAllJobs(jobType);
    const stats: Record<string, number> = {
      [JobStatus.PENDING]: 0,
      [JobStatus.QUEUED]: 0,
      [JobStatus.PROCESSING]: 0,
      [JobStatus.COMPLETED]: 0,
      [JobStatus.FAILED]: 0,
      [JobStatus.CANCELLED]: 0,
    };

    for (const job of jobs) {
      if (stats[job.state.status] !== undefined) {
        stats[job.state.status]++;
      }
    }

    return stats as Record<JobStatusValue, number>;
  }
}
