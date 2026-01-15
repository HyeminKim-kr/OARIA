import { Injectable, NotFoundException, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, In, IsNull } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import Redis from 'ioredis';
import { randomUUID } from 'crypto';
import { Paper, PaperStatus, EmbeddingStatusValue } from '../../entities/paper.entity';
import { PaperCitation } from '../../entities/paper-citation.entity';
import { JobManagerService, JobType, JobStatus } from '../job-manager';
import {
  PaperSearchOptions,
  PaginatedResult,
  PaperStats,
  EmbedTriggerResult,
  FulltextResult,
  EmbeddingStatusEnum,
  PaperStatusEnum,
  EmbedBatchTriggerResult,
  EmbedJobState,
  EmbedJobsResult,
  EmbedBatchCancelResult,
  CitationItem,
  CitationListResult,
  PdfUrlResult,
  PdfExistsResult,
} from './types';

// Re-export types for external use
export {
  PaperSearchOptions,
  PaginatedResult,
  PaperStats,
  EmbedTriggerResult,
  FulltextResult,
  EmbedBatchTriggerResult,
  EmbedJobsResult,
  EmbedBatchCancelResult,
  CitationListResult,
  PdfUrlResult,
  PdfExistsResult,
} from './types';

@Injectable()
export class PapersService {
  private readonly logger = new Logger(PapersService.name);
  private s3Client: S3Client;
  private bucket: string;
  private redis: Redis;

  constructor(
    @InjectRepository(Paper)
    private readonly repository: Repository<Paper>,
    @InjectRepository(PaperCitation)
    private readonly citationRepository: Repository<PaperCitation>,
    private readonly configService: ConfigService,
    private readonly jobManager: JobManagerService,
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
    // Redis 연결 (Celery 트리거용 - 레거시)
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
      pdfStatsResult,
      citationStatsResult,
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
      // PDF 통계
      this.repository
        .createQueryBuilder('paper')
        .select([
          'COUNT(*) FILTER (WHERE has_pdf = true) as "withPdf"',
          'COUNT(*) FILTER (WHERE has_pdf = false OR has_pdf IS NULL) as "withoutPdf"',
          'COALESCE(SUM(pdf_size), 0) as "totalSize"',
        ])
        .getRawOne(),
      // 인용 통계
      this.citationRepository
        .createQueryBuilder('citation')
        .select('COUNT(*)', 'total')
        .getRawOne(),
    ]);

    const totalPapers = total || 1; // 0으로 나누기 방지

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
      pdf: {
        withPdf: parseInt(pdfStatsResult?.withPdf ?? '0', 10),
        withoutPdf: parseInt(pdfStatsResult?.withoutPdf ?? '0', 10),
        totalSize: parseInt(pdfStatsResult?.totalSize ?? '0', 10),
      },
      citations: {
        total: parseInt(citationStatsResult?.total ?? '0', 10),
        avgPerPaper: parseInt(citationStatsResult?.total ?? '0', 10) / totalPapers,
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

  // ─────────────────────────────────────────────────────────────
  // Job Manager V2 기반 임베딩 관리
  // ─────────────────────────────────────────────────────────────

  /**
   * 임베딩 대기/실패 논문 일괄 임베딩 시작 (Job Manager V2)
   *
   * pending/failed 상태의 논문들을 수집하여 배치 작업으로 등록
   */
  async triggerEmbedBatch(limit?: number): Promise<EmbedBatchTriggerResult> {
    // pending 또는 failed 또는 NULL 상태인 논문 조회
    const queryBuilder = this.repository
      .createQueryBuilder('paper')
      .select('paper.id')
      .where('paper.canonicalPrefix IS NOT NULL')
      .andWhere(
        '(paper.embeddingStatus IS NULL OR paper.embeddingStatus IN (:...statuses))',
        { statuses: [EmbeddingStatusEnum.PENDING, EmbeddingStatusEnum.FAILED] },
      )
      .orderBy('paper.createdAt', 'ASC');

    if (limit) {
      queryBuilder.limit(limit);
    }

    const papers = await queryBuilder.getMany();

    if (papers.length === 0) {
      return {
        batchId: '',
        paperCount: 0,
        message: 'No papers to embed',
      };
    }

    // 배치 ID 생성 (타임스탬프 기반)
    const timestamp = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
    const batchId = `paper_batch_${timestamp}`;

    // 논문들의 상태를 pending으로 업데이트
    const paperIds = papers.map(p => p.id);
    await this.repository.update(
      { id: In(paperIds) },
      { embeddingStatus: EmbeddingStatusEnum.PENDING as EmbeddingStatusValue },
    );

    // Job Manager에 배치 작업 등록
    await this.jobManager.createPaperBatchJob(batchId, paperIds);

    this.logger.log(`Embedding batch triggered: ${batchId} with ${paperIds.length} papers`);

    return {
      batchId,
      paperCount: paperIds.length,
      message: `Batch job created for ${paperIds.length} papers`,
    };
  }

  /**
   * 임베딩 진행 중인 작업 일괄 취소
   */
  async cancelEmbedBatch(): Promise<EmbedBatchCancelResult> {
    // Redis에서 processing 상태 작업 취소
    const cancelledCount = await this.jobManager.cancelAllProcessingPaperJobs();

    // DB에서 processing 상태인 논문을 failed로 변경
    await this.repository.update(
      { embeddingStatus: EmbeddingStatusEnum.PROCESSING as EmbeddingStatusValue },
      {
        embeddingStatus: EmbeddingStatusEnum.FAILED as EmbeddingStatusValue,
        embeddingError: 'Cancelled by admin',
      },
    );

    this.logger.log(`Embedding batch cancelled: ${cancelledCount} jobs`);

    return {
      cancelledCount,
      message: `Cancelled ${cancelledCount} embedding jobs`,
    };
  }

  /**
   * 임베딩 작업 목록 조회 (Redis에서)
   */
  async getEmbedJobs(): Promise<EmbedJobsResult> {
    const jobs = await this.jobManager.getAllJobs(JobType.PAPER_EMBED);

    const embedJobs: EmbedJobState[] = jobs.map(job => ({
      jobId: job.jobId,
      status: job.state.status,
      progress: job.state.progress,
      total: job.state.total,
      retryCount: job.state.retryCount,
      error: job.state.error,
      startedAt: job.state.startedAt,
      completedAt: job.state.completedAt,
    }));

    return {
      jobs: embedJobs,
      total: embedJobs.length,
    };
  }

  /**
   * 특정 임베딩 작업 재시도
   */
  async retryEmbedJob(jobId: string): Promise<boolean> {
    return this.jobManager.retryJob(jobId, JobType.PAPER_EMBED);
  }

  /**
   * 특정 임베딩 작업 취소
   */
  async cancelEmbedJob(jobId: string): Promise<boolean> {
    return this.jobManager.cancelJob(jobId, JobType.PAPER_EMBED);
  }

  // ─────────────────────────────────────────────────────────────
  // PDF 관련
  // ─────────────────────────────────────────────────────────────

  /**
   * PDF 존재 여부 확인
   */
  async checkPdfExists(id: string): Promise<PdfExistsResult> {
    const paper = await this.findOne(id);
    return {
      hasPdf: paper.hasPdf,
      pdfSize: paper.pdfSize,
    };
  }

  /**
   * PDF Presigned URL 생성
   */
  async getPdfUrl(id: string): Promise<PdfUrlResult> {
    const paper = await this.findOne(id);

    if (!paper.hasPdf || !paper.canonicalPrefix) {
      throw new NotFoundException('PDF not available');
    }

    const pdfKey = `${paper.canonicalPrefix}/paper.pdf`;
    const expiresIn = 3600; // 1시간

    const command = new GetObjectCommand({
      Bucket: this.bucket,
      Key: pdfKey,
    });

    const url = await getSignedUrl(this.s3Client, command, { expiresIn });

    return { url, expiresIn };
  }

  // ─────────────────────────────────────────────────────────────
  // Citations/References 관련
  // ─────────────────────────────────────────────────────────────

  /**
   * 이 논문을 인용한 논문 목록 (Citations)
   * source_paper_id가 다른 논문이고, target_paper_id가 현재 논문인 경우
   */
  async getCitations(id: string, limit = 50): Promise<CitationListResult> {
    const paper = await this.findOne(id);

    const [items, total] = await this.citationRepository.findAndCount({
      where: { targetPaperId: paper.paperId },
      order: { createdAt: 'DESC' },
      take: limit,
    });

    return {
      items: items.map((item) => ({
        id: item.id,
        paperId: item.sourcePaperId,
        pmcid: item.sourcePmcid,
        pmid: item.sourcePmid,
        collectedFrom: item.collectedFrom,
        createdAt: item.createdAt,
      })),
      total,
    };
  }

  /**
   * 이 논문이 인용한 논문 목록 (References)
   * source_paper_id가 현재 논문이고, target_paper_id가 다른 논문인 경우
   */
  async getReferences(id: string, limit = 50): Promise<CitationListResult> {
    const paper = await this.findOne(id);

    const [items, total] = await this.citationRepository.findAndCount({
      where: { sourcePaperId: paper.paperId },
      order: { createdAt: 'DESC' },
      take: limit,
    });

    return {
      items: items.map((item) => ({
        id: item.id,
        paperId: item.targetPaperId,
        pmcid: item.targetPmcid,
        pmid: item.targetPmid,
        collectedFrom: item.collectedFrom,
        createdAt: item.createdAt,
      })),
      total,
    };
  }
}
