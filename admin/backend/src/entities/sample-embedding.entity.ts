import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { SearchQuery } from './search-query.entity';

export type SampleEmbeddingStatus = 'pending' | 'processing' | 'completed' | 'failed';

@Entity('sample_embeddings')
export class SampleEmbedding {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'query_id', type: 'uuid' })
  queryId: string;

  @Column({ type: 'varchar', length: 100 })
  chunker: string;

  @Column({ type: 'varchar', length: 100 })
  embedder: string;

  @Column({ name: 'pipeline_key', type: 'varchar', length: 200 })
  pipelineKey: string;

  @Column({ name: 'collection_name', type: 'varchar', length: 200 })
  collectionName: string;

  @Column({ type: 'varchar', length: 20, default: 'pending' })
  status: SampleEmbeddingStatus;

  @Column({ name: 'paper_count', type: 'int', default: 0 })
  paperCount: number;

  @Column({ name: 'chunk_count', type: 'int', default: 0 })
  chunkCount: number;

  @Column({ name: 'error_message', type: 'text', nullable: true })
  errorMessage: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @Column({ name: 'started_at', type: 'timestamptz', nullable: true })
  startedAt: Date | null;

  @Column({ name: 'completed_at', type: 'timestamptz', nullable: true })
  completedAt: Date | null;

  @ManyToOne(() => SearchQuery, (query) => query.sampleEmbeddings, {
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'query_id' })
  searchQuery: SearchQuery;
}
