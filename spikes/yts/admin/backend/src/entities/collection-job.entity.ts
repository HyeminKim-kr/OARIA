import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { SearchQuery } from './search-query.entity';

export type JobType = 'backfill' | 'incremental' | 'repair';
export type JobStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'partial'
  | 'delayed'
  | 'cancelled'
  | 'retried';

@Entity('collection_jobs')
export class CollectionJob {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'job_type', type: 'varchar', length: 20 })
  jobType: JobType;

  @Column({ name: 'query_id', type: 'uuid', nullable: true })
  queryId: string | null;

  @ManyToOne(() => SearchQuery, (query) => query.jobs, { nullable: true })
  @JoinColumn({ name: 'query_id' })
  searchQuery: SearchQuery | null;

  @Column({ type: 'int', default: 10 })
  priority: number;

  @Column({ type: 'text' })
  query: string;

  @Column({ type: 'jsonb', nullable: true })
  params: Record<string, unknown> | null;

  @Column({ name: 'api_name', type: 'varchar', length: 50, default: 'europe_pmc' })
  apiName: string;

  @Column({ type: 'varchar', length: 20, default: 'pending' })
  status: JobStatus;

  @Column({ type: 'jsonb', nullable: true })
  checkpoint: Record<string, unknown> | null;

  @Column({ name: 'total_count', type: 'int', nullable: true })
  totalCount: number | null;

  @Column({ name: 'processed_count', type: 'int', default: 0 })
  processedCount: number;

  @Column({ name: 'success_count', type: 'int', default: 0 })
  successCount: number;

  @Column({ name: 'failed_count', type: 'int', default: 0 })
  failedCount: number;

  @Column({ name: 'attempt_count', type: 'int', default: 0 })
  attemptCount: number;

  @Column({ name: 'max_attempts', type: 'int', default: 5 })
  maxAttempts: number;

  @Column({ name: 'next_run_at', type: 'timestamptz', nullable: true })
  nextRunAt: Date | null;

  @Column({ name: 'locked_at', type: 'timestamptz', nullable: true })
  lockedAt: Date | null;

  @Column({ name: 'locked_by', type: 'varchar', length: 100, nullable: true })
  lockedBy: string | null;

  @Column({ name: 'last_error_code', type: 'varchar', length: 20, nullable: true })
  lastErrorCode: string | null;

  @Column({ name: 'last_error_message', type: 'text', nullable: true })
  lastErrorMessage: string | null;

  @Column({ name: 'last_error_at', type: 'timestamptz', nullable: true })
  lastErrorAt: Date | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;

  @Column({ name: 'started_at', type: 'timestamptz', nullable: true })
  startedAt: Date | null;

  @Column({ name: 'completed_at', type: 'timestamptz', nullable: true })
  completedAt: Date | null;

  @Column({ name: 'duration_ms', type: 'int', nullable: true })
  durationMs: number | null;
}
