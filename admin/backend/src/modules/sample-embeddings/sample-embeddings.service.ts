import {
  Injectable,
  NotFoundException,
  ConflictException,
  BadRequestException,
  Logger,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { SampleEmbedding } from '../../entities/sample-embedding.entity';
import { SearchQuery } from '../../entities/search-query.entity';
import { CreateSampleEmbeddingDto, ListSampleEmbeddingsQueryDto } from './dto';

@Injectable()
export class SampleEmbeddingsService {
  private readonly logger = new Logger(SampleEmbeddingsService.name);
  private readonly userBackendUrl: string;

  constructor(
    @InjectRepository(SampleEmbedding)
    private readonly sampleEmbeddingRepository: Repository<SampleEmbedding>,
    @InjectRepository(SearchQuery)
    private readonly searchQueryRepository: Repository<SearchQuery>,
  ) {
    this.userBackendUrl = process.env.USER_BACKEND_URL || 'http://localhost:8000';
  }

  async findAll(query: ListSampleEmbeddingsQueryDto): Promise<SampleEmbedding[]> {
    const qb = this.sampleEmbeddingRepository
      .createQueryBuilder('se')
      .leftJoinAndSelect('se.searchQuery', 'sq')
      .orderBy('se.createdAt', 'DESC');

    if (query.queryId) {
      qb.andWhere('se.queryId = :queryId', { queryId: query.queryId });
    }

    if (query.status) {
      qb.andWhere('se.status = :status', { status: query.status });
    }

    return qb.getMany();
  }

  async findOne(id: string): Promise<SampleEmbedding> {
    const embedding = await this.sampleEmbeddingRepository.findOne({
      where: { id },
      relations: ['searchQuery'],
    });
    if (!embedding) {
      throw new NotFoundException(`샘플 임베딩을 찾을 수 없습니다: ${id}`);
    }
    return embedding;
  }

  async create(dto: CreateSampleEmbeddingDto): Promise<SampleEmbedding> {
    // Validate search query exists and is a sample type
    const searchQuery = await this.searchQueryRepository.findOne({
      where: { id: dto.queryId },
    });

    if (!searchQuery) {
      throw new NotFoundException(`수집 쿼리를 찾을 수 없습니다: ${dto.queryId}`);
    }

    if (searchQuery.queryType !== 'sample') {
      throw new BadRequestException(
        `샘플 타입의 쿼리만 임베딩 생성이 가능합니다. 현재 타입: ${searchQuery.queryType}`,
      );
    }

    // Generate pipeline key and collection name
    const pipelineKey = `${dto.chunker}__${dto.embedder}`;
    const collectionName = `MedicalChunks_sample_${dto.chunker}_${dto.embedder}`;

    // Check for duplicate pipeline
    const existing = await this.sampleEmbeddingRepository.findOne({
      where: { queryId: dto.queryId, pipelineKey },
    });

    if (existing) {
      throw new ConflictException(
        `이미 동일한 파이프라인이 존재합니다: ${pipelineKey}`,
      );
    }

    const embedding = this.sampleEmbeddingRepository.create({
      queryId: dto.queryId,
      chunker: dto.chunker,
      embedder: dto.embedder,
      pipelineKey,
      collectionName,
      status: 'pending',
      paperCount: 0,
      chunkCount: 0,
    });

    const savedEmbedding = await this.sampleEmbeddingRepository.save(embedding);

    // Trigger Celery task via User Backend
    await this.triggerEmbeddingTask(savedEmbedding.id);

    return savedEmbedding;
  }

  private async triggerEmbeddingTask(embeddingId: string): Promise<void> {
    try {
      const response = await fetch(
        `${this.userBackendUrl}/lab/sample-embed/trigger`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ embedding_id: embeddingId }),
        },
      );

      const result = await response.json();

      if (result.success) {
        this.logger.log(
          `Embedding task triggered: ${embeddingId}, taskId: ${result.task_id}`,
        );
      } else {
        this.logger.warn(
          `Failed to trigger embedding task: ${embeddingId}, message: ${result.message}`,
        );
      }
    } catch (error) {
      this.logger.error(
        `Error triggering embedding task: ${embeddingId}`,
        error,
      );
      // Don't throw - the embedding record is created, task can be retried
    }
  }

  async delete(id: string): Promise<void> {
    const embedding = await this.findOne(id);

    // Cannot delete if processing
    if (embedding.status === 'processing') {
      throw new ConflictException(
        '처리 중인 임베딩은 삭제할 수 없습니다. 완료 후 다시 시도해주세요.',
      );
    }

    // Trigger delete task via User Backend (deletes Weaviate collection and DB record)
    await this.triggerDeleteTask(id);
  }

  private async triggerDeleteTask(embeddingId: string): Promise<void> {
    try {
      const response = await fetch(
        `${this.userBackendUrl}/lab/sample-embed/delete`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ embedding_id: embeddingId }),
        },
      );

      const result = await response.json();

      if (result.success) {
        this.logger.log(
          `Delete task triggered: ${embeddingId}, taskId: ${result.task_id}`,
        );
      } else {
        // If task trigger fails, delete DB record directly
        this.logger.warn(
          `Failed to trigger delete task, deleting record directly: ${embeddingId}`,
        );
        await this.sampleEmbeddingRepository.delete(embeddingId);
      }
    } catch (error) {
      this.logger.error(`Error triggering delete task: ${embeddingId}`, error);
      // If task trigger fails, delete DB record directly
      await this.sampleEmbeddingRepository.delete(embeddingId);
    }
  }

  async updateStatus(
    id: string,
    status: SampleEmbedding['status'],
    extra?: { paperCount?: number; chunkCount?: number; errorMessage?: string },
  ): Promise<SampleEmbedding> {
    const embedding = await this.findOne(id);

    embedding.status = status;

    if (status === 'processing') {
      embedding.startedAt = new Date();
    } else if (status === 'completed' || status === 'failed') {
      embedding.completedAt = new Date();
    }

    if (extra?.paperCount !== undefined) {
      embedding.paperCount = extra.paperCount;
    }
    if (extra?.chunkCount !== undefined) {
      embedding.chunkCount = extra.chunkCount;
    }
    if (extra?.errorMessage !== undefined) {
      embedding.errorMessage = extra.errorMessage;
    }

    return this.sampleEmbeddingRepository.save(embedding);
  }

  async getStatsByQueryId(queryId: string): Promise<{
    total: number;
    pending: number;
    processing: number;
    completed: number;
    failed: number;
  }> {
    const embeddings = await this.sampleEmbeddingRepository.find({
      where: { queryId },
    });

    return {
      total: embeddings.length,
      pending: embeddings.filter((e) => e.status === 'pending').length,
      processing: embeddings.filter((e) => e.status === 'processing').length,
      completed: embeddings.filter((e) => e.status === 'completed').length,
      failed: embeddings.filter((e) => e.status === 'failed').length,
    };
  }

  // ============================================================
  // V2 Job Management API (User Backend 프록시)
  // ============================================================

  async getJobStatus(embeddingId: string): Promise<any> {
    try {
      const response = await fetch(
        `${this.userBackendUrl}/lab/sample-embed/${embeddingId}/status`,
      );

      if (!response.ok) {
        // Redis에 없으면 DB 상태 반환
        const embedding = await this.findOne(embeddingId);
        return {
          job_id: embeddingId,
          status: embedding.status,
          progress: embedding.paperCount || 0,
          total: 0,
          retry_count: 0,
          error: embedding.errorMessage || null,
          source: 'database',
        };
      }

      const result = await response.json();
      return { ...result, source: 'redis' };
    } catch (error) {
      this.logger.error(`Error getting job status: ${embeddingId}`, error);
      throw error;
    }
  }

  async retryJob(embeddingId: string): Promise<any> {
    try {
      const response = await fetch(
        `${this.userBackendUrl}/lab/sample-embed/${embeddingId}/retry`,
        { method: 'POST' },
      );

      const result = await response.json();

      if (result.success) {
        this.logger.log(`Job retry queued: ${embeddingId}`);
      } else {
        this.logger.warn(`Failed to retry job: ${embeddingId}, ${result.message}`);
      }

      return result;
    } catch (error) {
      this.logger.error(`Error retrying job: ${embeddingId}`, error);
      throw error;
    }
  }

  async cancelJob(embeddingId: string): Promise<any> {
    try {
      const response = await fetch(
        `${this.userBackendUrl}/lab/sample-embed/${embeddingId}/cancel`,
        { method: 'POST' },
      );

      const result = await response.json();

      if (result.success) {
        // DB 상태도 업데이트
        await this.sampleEmbeddingRepository.update(embeddingId, {
          status: 'failed',
          errorMessage: 'Cancelled by user',
        });
        this.logger.log(`Job cancelled: ${embeddingId}`);
      } else {
        this.logger.warn(`Failed to cancel job: ${embeddingId}, ${result.message}`);
      }

      return result;
    } catch (error) {
      this.logger.error(`Error cancelling job: ${embeddingId}`, error);
      throw error;
    }
  }
}
