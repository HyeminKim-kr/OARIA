import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
} from 'typeorm';
import { PaperAuthor } from './paper-author.entity';

export type PaperStatus = 'collected' | 'chunked' | 'indexed';

@Entity('papers')
export class Paper {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'paper_id', type: 'varchar', length: 100, unique: true })
  paperId: string;

  @Column({ type: 'varchar', length: 20, nullable: true })
  pmcid: string | null;

  @Column({ type: 'varchar', length: 20, nullable: true })
  pmid: string | null;

  @Column({ type: 'varchar', length: 200, nullable: true })
  doi: string | null;

  @Column({ type: 'text' })
  title: string;

  @Column({ type: 'text', nullable: true })
  abstract: string | null;

  @Column({ type: 'varchar', length: 500, nullable: true })
  journal: string | null;

  @Column({ type: 'int', nullable: true })
  year: number | null;

  @Column({ type: 'text', array: true, nullable: true })
  keywords: string[] | null;

  @Column({ name: 'canonical_bucket', type: 'varchar', length: 100, default: 'oaria-papers' })
  canonicalBucket: string;

  @Column({ name: 'canonical_prefix', type: 'text', nullable: true })
  canonicalPrefix: string | null;

  @Column({ name: 'canonical_text_version', type: 'varchar', length: 50, default: 'v1' })
  canonicalTextVersion: string;

  @Column({ name: 'canonical_text_hash', type: 'varchar', length: 64, nullable: true })
  canonicalTextHash: string | null;

  @Column({ name: 'canonical_text_length', type: 'int', nullable: true })
  canonicalTextLength: number | null;

  @Column({ name: 'raw_xml_hash', type: 'varchar', length: 64, nullable: true })
  rawXmlHash: string | null;

  @Column({ name: 'parser_version', type: 'varchar', length: 20, default: '1.0.0' })
  parserVersion: string;

  @Column({ type: 'varchar', length: 50, default: 'europe_pmc' })
  source: string;

  @Column({ name: 'source_url', type: 'text', nullable: true })
  sourceUrl: string | null;

  @Column({ name: 'is_open_access', type: 'boolean', default: true })
  isOpenAccess: boolean;

  @Column({ type: 'varchar', length: 20, default: 'collected' })
  status: PaperStatus;

  @Column({ name: 'chunked_at', type: 'timestamptz', nullable: true })
  chunkedAt: Date | null;

  @Column({ name: 'indexed_at', type: 'timestamptz', nullable: true })
  indexedAt: Date | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;

  @OneToMany(() => PaperAuthor, (author) => author.paper)
  authors: PaperAuthor[];
}
