import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import Redis from 'ioredis';
import { randomUUID } from 'crypto';
import { Paper, PaperStatus, EmbeddingStatusValue } from '../../entities/paper.entity';
import {
  PaperSearchOptions,
  PaginatedResult,
  PaperStats,
  EmbedTriggerResult,
  FulltextResult,
  EmbeddingStatusEnum,
  PaperStatusEnum,
} from './types';

// Re-export types for external use
export {
  PaperSearchOptions,
  PaginatedResult,
  PaperStats,
  EmbedTriggerResult,
  FulltextResult,
} from './types';

@Injectable()
export class PapersService {
  private s3Client: S3Client;
  private bucket: string;
  private redis: Redis;

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
    // Redis 연결 (Celery 트리거용)
    this.redis = new Redis({
      host: this.configService.get('REDIS_HOST', 'localhost'),
      port: this.configService.get('REDIS_PORT', 16379),
    });
  }

  async findAll(options: PaperSearchOptions = {}): Promise<PaginatedResult<Paper>> {
    const {
      search,
      status,
      embeddingStatus,
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

    // 임베딩 상태 필터
    if (embeddingStatus === EmbeddingStatusEnum.NOT_STARTED) {
      query.andWhere('paper.embeddingStatus IS NULL');
    } else if (embeddingStatus) {
      query.andWhere('paper.embeddingStatus = :embeddingStatus', { embeddingStatus });
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

  async getStats(): Promise<PaperStats> {
    const [
      total,
      collected,
      chunked,
      indexed,
      byYear,
      recentCount,
      embeddingNotStarted,
      embeddingPending,
      embeddingProcessing,
      embeddingCompleted,
      embeddingFailed,
      totalChunksResult,
    ] = await Promise.all([
      this.repository.count(),
      this.repository.count({ where: { status: PaperStatusEnum.COLLECTED as PaperStatus } }),
      this.repository.count({ where: { status: PaperStatusEnum.CHUNKED as PaperStatus } }),
      this.repository.count({ where: { status: PaperStatusEnum.INDEXED as PaperStatus } }),
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
      // 임베딩 통계
      this.repository
        .createQueryBuilder('paper')
        .where('paper.embeddingStatus IS NULL')
        .getCount(),
      this.repository.count({ where: { embeddingStatus: EmbeddingStatusEnum.PENDING as EmbeddingStatusValue } }),
      this.repository.count({ where: { embeddingStatus: EmbeddingStatusEnum.PROCESSING as EmbeddingStatusValue } }),
      this.repository.count({ where: { embeddingStatus: EmbeddingStatusEnum.COMPLETED as EmbeddingStatusValue } }),
      this.repository.count({ where: { embeddingStatus: EmbeddingStatusEnum.FAILED as EmbeddingStatusValue } }),
      this.repository
        .createQueryBuilder('paper')
        .select('COALESCE(SUM(paper.embeddingChunkCount), 0)', 'total')
        .getRawOne(),
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
      embedding: {
        notStarted: embeddingNotStarted,
        pending: embeddingPending,
        processing: embeddingProcessing,
        completed: embeddingCompleted,
        failed: embeddingFailed,
        totalChunks: parseInt(totalChunksResult?.total ?? '0', 10),
      },
    };
  }

  async getRecentPapers(limit = 10): Promise<Paper[]> {
    return this.repository.find({
      order: { createdAt: 'DESC' },
      take: limit,
      relations: ['authors'],
    });
  }

  async getFulltext(id: string): Promise<FulltextResult> {
    const paper = await this.findOne(id);

    if (!paper.canonicalPrefix) {
      return { fulltext: null, rawXml: null, display: null };
    }

    const [fulltext, rawXml, displayJson] = await Promise.all([
      this.getS3Object(`${paper.canonicalPrefix}/fulltext.txt`),
      this.getS3Object(`${paper.canonicalPrefix}/raw.xml`),
      this.getS3Object(`${paper.canonicalPrefix}/display.json`),
    ]);

    // display.json 파싱
    let display = null;
    if (displayJson) {
      try {
        display = JSON.parse(displayJson);
      } catch {
        display = null;
      }
    }

    return { fulltext, rawXml, display };
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

  // ─────────────────────────────────────────────────────────────
  // 임베딩 관련
  // ─────────────────────────────────────────────────────────────

  private generateTaskId(): string {
    return randomUUID();
  }

  /**
   * 전체 논문 임베딩 시작
   */
  async triggerEmbedAll(limit?: number): Promise<EmbedTriggerResult> {
    const taskId = this.generateTaskId();

    // 대기 중인 논문 수 조회
    const pendingCount = await this.repository
      .createQueryBuilder('paper')
      .where('paper.embeddingStatus IS NULL OR paper.embeddingStatus = :status', { status: EmbeddingStatusEnum.PENDING })
      .andWhere('paper.canonicalPrefix IS NOT NULL')
      .getCount();

    // Celery 메시지 생성
    const args = limit ? [null, limit] : [null, null];
    const message = JSON.stringify({
      body: Buffer.from(JSON.stringify([args, {}, {}])).toString('base64'),
      'content-encoding': 'utf-8',
      'content-type': 'application/json',
      headers: {
        task: 'src.tasks.embed.run_embed',
        id: taskId,
        lang: 'py',
        root_id: taskId,
        parent_id: null,
        group: null,
      },
      properties: {
        correlation_id: taskId,
        reply_to: null,
        delivery_mode: 2,
        delivery_info: { exchange: '', routing_key: 'embed' },
        priority: 0,
        body_encoding: 'base64',
        delivery_tag: taskId,
      },
    });

    await this.redis.lpush('embed', message);

    return { taskId, pendingCount };
  }

  /**
   * 특정 쿼리로 수집된 논문 임베딩
   */
  async triggerEmbedByQuery(queryId: string, limit?: number): Promise<EmbedTriggerResult> {
    const taskId = this.generateTaskId();

    const args = limit ? [queryId, limit] : [queryId, null];
    const message = JSON.stringify({
      body: Buffer.from(JSON.stringify([args, {}, {}])).toString('base64'),
      'content-encoding': 'utf-8',
      'content-type': 'application/json',
      headers: {
        task: 'src.tasks.embed.run_embed',
        id: taskId,
        lang: 'py',
        root_id: taskId,
        parent_id: null,
        group: null,
      },
      properties: {
        correlation_id: taskId,
        reply_to: null,
        delivery_mode: 2,
        delivery_info: { exchange: '', routing_key: 'embed' },
        priority: 0,
        body_encoding: 'base64',
        delivery_tag: taskId,
      },
    });

    await this.redis.lpush('embed', message);

    return { taskId };
  }

  /**
   * 단일 논문 임베딩
   */
  async triggerEmbedPaper(paperId: string): Promise<EmbedTriggerResult> {
    const taskId = this.generateTaskId();

    const message = JSON.stringify({
      body: Buffer.from(JSON.stringify([[paperId], {}, {}])).toString('base64'),
      'content-encoding': 'utf-8',
      'content-type': 'application/json',
      headers: {
        task: 'src.tasks.embed.run_embed_paper',
        id: taskId,
        lang: 'py',
        root_id: taskId,
        parent_id: null,
        group: null,
      },
      properties: {
        correlation_id: taskId,
        reply_to: null,
        delivery_mode: 2,
        delivery_info: { exchange: '', routing_key: 'embed' },
        priority: 0,
        body_encoding: 'base64',
        delivery_tag: taskId,
      },
    });

    await this.redis.lpush('embed', message);

    return { taskId };
  }

  /**
   * 실패한 논문 재임베딩
   */
  async triggerReembed(queryId?: string): Promise<EmbedTriggerResult> {
    const taskId = this.generateTaskId();

    // 실패한 논문 수 조회
    const failedCount = await this.repository.count({
      where: { embeddingStatus: EmbeddingStatusEnum.FAILED as EmbeddingStatusValue },
    });

    const args = queryId ? [queryId, null] : [null, null];
    const message = JSON.stringify({
      body: Buffer.from(JSON.stringify([args, {}, {}])).toString('base64'),
      'content-encoding': 'utf-8',
      'content-type': 'application/json',
      headers: {
        task: 'src.tasks.embed.run_reembed',
        id: taskId,
        lang: 'py',
        root_id: taskId,
        parent_id: null,
        group: null,
      },
      properties: {
        correlation_id: taskId,
        reply_to: null,
        delivery_mode: 2,
        delivery_info: { exchange: '', routing_key: 'embed' },
        priority: 0,
        body_encoding: 'base64',
        delivery_tag: taskId,
      },
    });

    await this.redis.lpush('embed', message);

    return { taskId, failedCount };
  }
}
