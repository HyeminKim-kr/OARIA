import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
} from 'typeorm';

@Entity('paper_citations')
@Index('idx_paper_citations_source', ['sourcePaperId'])
@Index('idx_paper_citations_target', ['targetPaperId'])
@Index('idx_paper_citations_collected', ['collectedFrom'])
export class PaperCitation {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  // 인용하는 논문 (citing paper)
  @Column({ name: 'source_paper_id', type: 'varchar', length: 100 })
  sourcePaperId: string;

  // 인용되는 논문 (cited paper)
  @Column({ name: 'target_paper_id', type: 'varchar', length: 100 })
  targetPaperId: string;

  // 추가 식별자
  @Column({ name: 'source_pmcid', type: 'varchar', length: 20, nullable: true })
  sourcePmcid: string | null;

  @Column({ name: 'source_pmid', type: 'varchar', length: 20, nullable: true })
  sourcePmid: string | null;

  @Column({ name: 'target_pmcid', type: 'varchar', length: 20, nullable: true })
  targetPmcid: string | null;

  @Column({ name: 'target_pmid', type: 'varchar', length: 20, nullable: true })
  targetPmid: string | null;

  // 어떤 논문 수집 시 발견됨
  @Column({ name: 'collected_from', type: 'varchar', length: 100 })
  collectedFrom: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;
}
