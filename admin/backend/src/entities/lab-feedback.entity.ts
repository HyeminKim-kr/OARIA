import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { AdminUser } from './admin-user.entity';

export enum LabTestType {
  SEARCH = 'search',
  GENERATE = 'generate',
}

export enum FeedbackRating {
  GOOD = 'good',
  BAD = 'bad',
}

export interface LabTestParameters {
  limit: number;
  alpha: number;
  useReranker?: boolean;
  minRerankScore?: number;
  rerankerModel?: string;
}

export interface LabResultSummary {
  totalChunks: number;
  topScore: number;
  relevantCount?: number;
  lowRelevanceCount?: number;
  model?: string;
  tokensUsed?: {
    prompt: number;
    completion: number;
  };
}

@Entity('lab_feedbacks')
export class LabFeedback {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'uuid', nullable: true, name: 'admin_user_id' })
  adminUserId: string | null;

  @ManyToOne(() => AdminUser, { nullable: true })
  @JoinColumn({ name: 'admin_user_id' })
  adminUser: AdminUser;

  @Column({ type: 'varchar', length: 20, name: 'test_type' })
  testType: LabTestType;

  @Column({ type: 'text' })
  query: string;

  @Column({ type: 'varchar', length: 10 })
  rating: FeedbackRating;

  @Column({ type: 'text', nullable: true })
  comment: string | null;

  @Column({ type: 'jsonb' })
  parameters: LabTestParameters;

  @Column({ type: 'jsonb', nullable: true, name: 'result_summary' })
  resultSummary: LabResultSummary | null;

  @Column({ type: 'int', nullable: true, name: 'search_latency_ms' })
  searchLatencyMs: number | null;

  @Column({ type: 'int', nullable: true, name: 'rerank_latency_ms' })
  rerankLatencyMs: number | null;

  @Column({ type: 'int', nullable: true, name: 'llm_latency_ms' })
  llmLatencyMs: number | null;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt: Date;
}
