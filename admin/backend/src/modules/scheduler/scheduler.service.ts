import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, LessThan, IsNull, Or, Not } from 'typeorm';
import { CollectionJob, JobStatus } from '../../entities/collection-job.entity';
import { CollectionJobsService } from '../collection-jobs/collection-jobs.service';
import { JobStatusEnum } from '../collection-jobs/types';

@Injectable()
export class SchedulerService {
  private readonly logger = new Logger(SchedulerService.name);

  // Heartbeat timeout: 10분 동안 locked_at 업데이트 없으면 stale로 간주
  private readonly HEARTBEAT_TIMEOUT_MINUTES = 10;
  // 자동 재시도 최대 횟수
  private readonly MAX_AUTO_RETRY = 3;
  // 재시도 쿨다운: 최소 1시간 이후에 재시도
  private readonly RETRY_COOLDOWN_HOURS = 1;

  constructor(
    @InjectRepository(CollectionJob)
    private readonly jobRepository: Repository<CollectionJob>,
    private readonly collectionJobsService: CollectionJobsService,
  ) {}

  /**
   * 5분마다 stale job 체크 및 복구
   * - running 상태인데 locked_at이 10분 이상 지났거나 NULL인 job → failed로 변경
   */
  @Cron(CronExpression.EVERY_5_MINUTES)
  async handleStaleJobs(): Promise<void> {
    this.logger.debug('Checking for stale jobs...');

    const cutoffTime = new Date();
    cutoffTime.setMinutes(cutoffTime.getMinutes() - this.HEARTBEAT_TIMEOUT_MINUTES);

    // running 상태이면서 locked_at이 NULL이거나 timeout 이전인 job 조회
    const staleJobs = await this.jobRepository.find({
      where: {
        status: JobStatusEnum.RUNNING as JobStatus,
        lockedAt: Or(IsNull(), LessThan(cutoffTime)),
      },
    });

    if (staleJobs.length === 0) {
      this.logger.debug('No stale jobs found');
      return;
    }

    this.logger.warn(`Found ${staleJobs.length} stale job(s), recovering...`);

    for (const job of staleJobs) {
      // stale job을 failed로 변경 (재시도 가능하도록)
      job.status = JobStatusEnum.FAILED as JobStatus;
      job.lastErrorCode = 'STALE_JOB';
      job.lastErrorMessage = `Job was stale (no heartbeat for ${this.HEARTBEAT_TIMEOUT_MINUTES} minutes)`;
      job.lastErrorAt = new Date();
      job.completedAt = new Date();

      await this.jobRepository.save(job);

      this.logger.warn(`Recovered stale job: ${job.id}`, {
        jobId: job.id,
        queryId: job.queryId,
        lastLockedAt: job.lockedAt,
      });
    }
  }

  /**
   * 매 시간마다 pending 상태로 오래된 job 정리
   * - 24시간 이상 pending인 job → 자동 취소
   */
  @Cron(CronExpression.EVERY_HOUR)
  async handleStalePendingJobs(): Promise<void> {
    this.logger.debug('Checking for stale pending jobs...');

    const cutoffTime = new Date();
    cutoffTime.setHours(cutoffTime.getHours() - 24);

    const stalePendingJobs = await this.jobRepository.find({
      where: {
        status: JobStatusEnum.PENDING as JobStatus,
        createdAt: LessThan(cutoffTime),
      },
    });

    if (stalePendingJobs.length === 0) {
      return;
    }

    this.logger.warn(`Found ${stalePendingJobs.length} stale pending job(s), cancelling...`);

    for (const job of stalePendingJobs) {
      job.status = JobStatusEnum.CANCELLED as JobStatus;
      job.lastErrorCode = 'STALE_PENDING';
      job.lastErrorMessage = 'Job was pending for more than 24 hours';
      job.completedAt = new Date();

      await this.jobRepository.save(job);
    }
  }

  /**
   * 30분마다 failed job 자동 재시도
   * - failed 상태 + attempt_count < 3 + 쿨다운(1시간) 지남 + queryId 있음
   */
  @Cron(CronExpression.EVERY_30_MINUTES)
  async handleAutoRetry(): Promise<void> {
    this.logger.debug('Checking for jobs to auto-retry...');

    const cooldownTime = new Date();
    cooldownTime.setHours(cooldownTime.getHours() - this.RETRY_COOLDOWN_HOURS);

    // failed 상태 + attempt_count < MAX_AUTO_RETRY + 쿨다운 지남 + queryId 있음
    const retryableJobs = await this.jobRepository.find({
      where: {
        status: JobStatusEnum.FAILED as JobStatus,
        attemptCount: LessThan(this.MAX_AUTO_RETRY),
        completedAt: LessThan(cooldownTime),
        queryId: Not(IsNull()),
      },
      order: { completedAt: 'ASC' }, // 오래된 것부터
      take: 5, // 한 번에 최대 5개까지만
    });

    if (retryableJobs.length === 0) {
      this.logger.debug('No jobs to auto-retry');
      return;
    }

    this.logger.log(`Found ${retryableJobs.length} job(s) to auto-retry`);

    for (const job of retryableJobs) {
      try {
        // queryId가 없으면 스킵 (이미 필터링됨, 타입 가드용)
        if (!job.queryId) continue;

        // 같은 queryId에 이미 running Job이 있는지 체크 (중복 방지)
        const existingRunningJob = await this.jobRepository.findOne({
          where: {
            queryId: job.queryId,
            status: 'running' as JobStatus,
          },
        });

        if (existingRunningJob) {
          this.logger.debug(`Skipping auto-retry for job ${job.id}: another job is running`);
          continue;
        }

        const result = await this.collectionJobsService.retryJob(job.id);
        this.logger.log(`Auto-retry triggered for job ${job.id}`, {
          taskId: result.taskId,
          attemptCount: job.attemptCount + 1,
        });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        this.logger.error(`Failed to auto-retry job ${job.id}: ${errorMessage}`);
      }
    }
  }
}
