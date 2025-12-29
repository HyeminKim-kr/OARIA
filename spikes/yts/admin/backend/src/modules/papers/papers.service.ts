import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, Like, Between } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { Paper, PaperStatus } from '../../entities/paper.entity';

export interface PaperSearchOptions {
  search?: string;
  status?: PaperStatus;
  yearFrom?: number;
  yearTo?: number;
  page?: number;
  limit?: number;
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

@Injectable()
export class PapersService {
  private s3Client: S3Client;
  private bucket: string;

  constructor(
    @InjectRepository(Paper)
    private readonly repository: Repository<Paper>,
    private readonly configService: ConfigService,
  ) {
    this.bucket = this.configService.get('S3_BUCKET', 'oaria-papers');
    this.s3Client = new S3Client({
      endpoint: this.configService.get('S3_ENDPOINT', 'http://localhost:19000'),
      region: 'us-east-1',
      credentials: {
        accessKeyId: this.configService.get('S3_ACCESS_KEY', 'minioadmin'),
        secretAccessKey: this.configService.get('S3_SECRET_KEY', 'minioadmin_2024'),
      },
      forcePathStyle: true,
    });
  }

  async findAll(options: PaperSearchOptions = {}): Promise<PaginatedResult<Paper>> {
    const {
      search,
      status,
      yearFrom,
      yearTo,
      page = 1,
      limit = 20,
    } = options;

    const query = this.repository
      .createQueryBuilder('paper')
      .leftJoinAndSelect('paper.authors', 'authors')
      .orderBy('paper.createdAt', 'DESC');

    // 검색어
    if (search) {
      query.andWhere(
        '(paper.title ILIKE :search OR paper.paperId ILIKE :search OR paper.pmcid ILIKE :search)',
        { search: `%${search}%` },
      );
    }

    // 상태 필터
    if (status) {
      query.andWhere('paper.status = :status', { status });
    }

    // 연도 필터
    if (yearFrom) {
      query.andWhere('paper.year >= :yearFrom', { yearFrom });
    }
    if (yearTo) {
      query.andWhere('paper.year <= :yearTo', { yearTo });
    }

    // 페이지네이션
    const total = await query.getCount();
    const items = await query
      .skip((page - 1) * limit)
      .take(limit)
      .getMany();

    return {
      items,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  async findOne(id: string): Promise<Paper> {
    const paper = await this.repository.findOne({
      where: { id },
      relations: ['authors'],
    });
    if (!paper) {
      throw new NotFoundException(`Paper #${id} not found`);
    }
    return paper;
  }

  async findByPaperId(paperId: string): Promise<Paper | null> {
    return this.repository.findOne({
      where: { paperId },
      relations: ['authors'],
    });
  }

  async getStats(): Promise<{
    total: number;
    collected: number;
    chunked: number;
    indexed: number;
    byYear: { year: number; count: number }[];
    recentCount: number;
  }> {
    const [total, collected, chunked, indexed, byYear, recentCount] =
      await Promise.all([
        this.repository.count(),
        this.repository.count({ where: { status: 'collected' as PaperStatus } }),
        this.repository.count({ where: { status: 'chunked' as PaperStatus } }),
        this.repository.count({ where: { status: 'indexed' as PaperStatus } }),
        this.repository
          .createQueryBuilder('paper')
          .select('paper.year', 'year')
          .addSelect('COUNT(*)', 'count')
          .where('paper.year IS NOT NULL')
          .groupBy('paper.year')
          .orderBy('paper.year', 'DESC')
          .limit(10)
          .getRawMany(),
        this.repository
          .createQueryBuilder('paper')
          .where('paper.createdAt >= NOW() - INTERVAL \'7 days\'')
          .getCount(),
      ]);

    return {
      total,
      collected,
      chunked,
      indexed,
      byYear: byYear.map((r) => ({
        year: parseInt(r.year, 10),
        count: parseInt(r.count, 10),
      })),
      recentCount,
    };
  }

  async getRecentPapers(limit = 10): Promise<Paper[]> {
    return this.repository.find({
      order: { createdAt: 'DESC' },
      take: limit,
      relations: ['authors'],
    });
  }

  async getFulltext(id: string): Promise<{ fulltext: string | null; rawXml: string | null }> {
    const paper = await this.findOne(id);

    if (!paper.canonicalPrefix) {
      return { fulltext: null, rawXml: null };
    }

    const [fulltext, rawXml] = await Promise.all([
      this.getS3Object(`${paper.canonicalPrefix}/fulltext.txt`),
      this.getS3Object(`${paper.canonicalPrefix}/raw.xml`),
    ]);

    return { fulltext, rawXml };
  }

  private async getS3Object(key: string): Promise<string | null> {
    try {
      const command = new GetObjectCommand({
        Bucket: this.bucket,
        Key: key,
      });
      const response = await this.s3Client.send(command);
      return await response.Body?.transformToString() ?? null;
    } catch (error) {
      return null;
    }
  }
}
