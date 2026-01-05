import {
  Entity,
  PrimaryColumn,
  Column,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { Paper } from './paper.entity';

@Entity('paper_authors')
export class PaperAuthor {
  @PrimaryColumn({ name: 'paper_id', type: 'uuid' })
  paperId: string;

  @PrimaryColumn({ name: 'author_order', type: 'smallint' })
  authorOrder: number;

  @ManyToOne(() => Paper, (paper) => paper.authors, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'paper_id' })
  paper: Paper;

  @Column({ name: 'author_name', type: 'text' })
  authorName: string;

  @Column({ name: 'is_corresponding', type: 'boolean', default: false })
  isCorresponding: boolean;

  @Column({ type: 'varchar', length: 50, nullable: true })
  orcid: string | null;

  @Column({ type: 'text', nullable: true })
  affiliation: string | null;
}
