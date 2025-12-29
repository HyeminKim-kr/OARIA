import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { CollectionJob } from './collection-job.entity';

export type ErrorStage = 'search' | 'download' | 'parse' | 'save';

@Entity('article_errors')
export class ArticleError {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'job_id', type: 'uuid' })
  jobId: string;

  @ManyToOne(() => CollectionJob, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'job_id' })
  job: CollectionJob;

  @Column({ type: 'varchar', length: 20, nullable: true })
  pmcid: string | null;

  @Column({ type: 'varchar', length: 20, nullable: true })
  pmid: string | null;

  @Column({ type: 'varchar', length: 100, nullable: true })
  doi: string | null;

  @Column({ type: 'varchar', length: 30 })
  stage: ErrorStage;

  @Column({ name: 'error_code', type: 'varchar', length: 50, nullable: true })
  errorCode: string | null;

  @Column({ name: 'error_message', type: 'text' })
  errorMessage: string;

  @Column({ name: 'error_detail', type: 'text', nullable: true })
  errorDetail: string | null;

  @Column({ name: 'raw_response', type: 'text', nullable: true })
  rawResponse: string | null;

  @Column({ type: 'jsonb', nullable: true })
  context: Record<string, unknown> | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;
}
