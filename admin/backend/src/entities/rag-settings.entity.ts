import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

export interface RAGParameters {
  limit?: number;
  alpha?: number;
  minRerankScore?: number;
  temperature?: number;
}

@Entity('rag_settings')
export class RAGSettings {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 50, unique: true })
  name: string;

  @Column({ type: 'text', nullable: true })
  description: string | null;

  @Column({ type: 'varchar', length: 50, default: 'semantic' })
  chunker: string;

  @Column({ type: 'varchar', length: 50, default: 'openai' })
  embedder: string;

  @Column({ type: 'varchar', length: 50, default: 'hybrid' })
  retriever: string;

  @Column({ type: 'varchar', length: 50, nullable: true })
  reranker: string | null;

  @Column({ type: 'jsonb', nullable: true })
  parameters: RAGParameters | null;

  @Column({ type: 'boolean', default: false, name: 'is_active' })
  isActive: boolean;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ type: 'timestamptz', name: 'updated_at' })
  updatedAt: Date;
}
