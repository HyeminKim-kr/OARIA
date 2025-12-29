import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
} from 'typeorm';
import { CollectionJob } from './collection-job.entity';

@Entity('search_queries')
export class SearchQuery {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 100 })
  name: string;

  @Column({ type: 'text' })
  query: string;

  @Column({ type: 'text', nullable: true })
  description: string | null;

  @Column({ name: 'is_active', type: 'boolean', default: true })
  isActive: boolean;

  @Column({ type: 'int', default: 10 })
  priority: number;

  @Column({ name: 'max_results', type: 'int', nullable: true })
  maxResults: number | null;

  @Column({ name: 'year_from', type: 'int', nullable: true })
  yearFrom: number | null;

  @Column({ name: 'year_to', type: 'int', nullable: true })
  yearTo: number | null;

  @Column({ name: 'open_access_only', type: 'boolean', default: true })
  openAccessOnly: boolean;

  @Column({ name: 'max_concurrent', type: 'int', default: 35 })
  maxConcurrent: number;

  @Column({ name: 'auto_backfill', type: 'boolean', default: false })
  autoBackfill: boolean;

  @Column({ name: 'total_collected', type: 'int', default: 0 })
  totalCollected: number;

  @Column({ name: 'last_backfill_at', type: 'timestamptz', nullable: true })
  lastBackfillAt: Date | null;

  @Column({ name: 'last_incremental_at', type: 'timestamptz', nullable: true })
  lastIncrementalAt: Date | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;

  @Column({ name: 'created_by', type: 'varchar', length: 100, nullable: true })
  createdBy: string | null;

  @Column({ name: 'updated_by', type: 'varchar', length: 100, nullable: true })
  updatedBy: string | null;

  @OneToMany(() => CollectionJob, (job) => job.searchQuery)
  jobs: CollectionJob[];
}
