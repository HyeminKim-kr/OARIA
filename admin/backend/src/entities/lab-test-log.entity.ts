import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { AdminUser } from './admin-user.entity';

export enum LabTestLogType {
  SEARCH = 'search',
  GENERATE = 'generate',
  COMPARE = 'compare',
}

export interface SearchChunkResult {
  paperId: string;
  paperTitle: string;
  sectionName: string;
  chunkIndex: number;
  content: string;
  score: number;
  rerankScore?: number;
  originalScore?: number;
}

export interface ReferenceResult {
  paperId: string;
  title: string;
  section: string;
  content: string;
  score: number;
}

export interface SearchResults {
  chunks: SearchChunkResult[];
  totalChunks: number;
}

export interface GenerateResults {
  answer: string;
  references: ReferenceResult[];
  model: string;
  tokensUsed?: {
    prompt: number;
    completion: number;
  };
}

export interface CompareResults {
  configA: SearchResults & { rerankLatencyMs?: number };
  configB: SearchResults & { rerankLatencyMs?: number };
}

export type TestLogResults = SearchResults | GenerateResults | CompareResults;

export interface SearchConfigParameters {
  limit: number;
  alpha: number;
  reranker?: string | null;
}

export interface TestLogParameters {
  limit?: number;
  alpha?: number;
  useReranker?: boolean;
  minRerankScore?: number;
  rerankerModel?: string;
  // A/B 비교용
  configA?: SearchConfigParameters;
  configB?: SearchConfigParameters;
}

@Entity('lab_test_logs')
export class LabTestLog {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'uuid', nullable: true, name: 'admin_user_id' })
  adminUserId: string | null;

  @ManyToOne(() => AdminUser, { nullable: true })
  @JoinColumn({ name: 'admin_user_id' })
  adminUser: AdminUser;

  @Column({ type: 'varchar', length: 20, name: 'test_type' })
  testType: LabTestLogType;

  @Column({ type: 'text' })
  query: string;

  @Column({ type: 'jsonb' })
  parameters: TestLogParameters;

  @Column({ type: 'jsonb' })
  results: TestLogResults;

  @Column({ type: 'int', nullable: true, name: 'search_latency_ms' })
  searchLatencyMs: number | null;

  @Column({ type: 'int', nullable: true, name: 'rerank_latency_ms' })
  rerankLatencyMs: number | null;

  @Column({ type: 'int', nullable: true, name: 'llm_latency_ms' })
  llmLatencyMs: number | null;

  @Column({ type: 'int', nullable: true, name: 'total_latency_ms' })
  totalLatencyMs: number | null;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt: Date;
}
