import {
  Controller,
  Get,
  Post,
  Delete,
  Body,
  Param,
  Query,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiQuery } from '@nestjs/swagger';
import { SampleEmbeddingsService } from './sample-embeddings.service';
import {
  CreateSampleEmbeddingDto,
  SampleEmbeddingResponseDto,
  ListSampleEmbeddingsQueryDto,
} from './dto';
import { SampleEmbedding } from '../../entities/sample-embedding.entity';

@ApiTags('Sample Embeddings')
@Controller('sample-embeddings')
export class SampleEmbeddingsController {
  constructor(private readonly sampleEmbeddingsService: SampleEmbeddingsService) {}

  @Get()
  @ApiOperation({ summary: '샘플 임베딩 목록 조회' })
  @ApiResponse({ status: 200, description: '샘플 임베딩 목록', type: [SampleEmbeddingResponseDto] })
  @ApiQuery({ name: 'queryId', required: false, description: '샘플 쿼리 ID로 필터링' })
  @ApiQuery({ name: 'status', required: false, description: '상태로 필터링' })
  async findAll(@Query() query: ListSampleEmbeddingsQueryDto): Promise<SampleEmbedding[]> {
    return this.sampleEmbeddingsService.findAll(query);
  }

  @Get(':id')
  @ApiOperation({ summary: '샘플 임베딩 상세 조회' })
  @ApiResponse({ status: 200, description: '샘플 임베딩 상세', type: SampleEmbeddingResponseDto })
  async findOne(@Param('id') id: string): Promise<SampleEmbedding> {
    return this.sampleEmbeddingsService.findOne(id);
  }

  @Post()
  @ApiOperation({ summary: '새 샘플 임베딩 생성 (임베딩 작업 시작)' })
  @ApiResponse({ status: 201, description: '생성된 샘플 임베딩', type: SampleEmbeddingResponseDto })
  async create(@Body() dto: CreateSampleEmbeddingDto): Promise<SampleEmbedding> {
    const embedding = await this.sampleEmbeddingsService.create(dto);

    // TODO: Trigger Celery task to process embedding
    // await this.celeryService.triggerSampleEmbedding(embedding.id);

    return embedding;
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: '샘플 임베딩 삭제 (Weaviate 컬렉션도 삭제)' })
  @ApiResponse({ status: 204, description: '삭제 완료' })
  async delete(@Param('id') id: string): Promise<void> {
    return this.sampleEmbeddingsService.delete(id);
  }

  @Get('stats/:queryId')
  @ApiOperation({ summary: '샘플 쿼리별 임베딩 통계' })
  @ApiResponse({ status: 200, description: '임베딩 통계' })
  async getStats(@Param('queryId') queryId: string): Promise<{
    total: number;
    pending: number;
    processing: number;
    completed: number;
    failed: number;
  }> {
    return this.sampleEmbeddingsService.getStatsByQueryId(queryId);
  }

  // ============================================================
  // V2 Job Management API
  // ============================================================

  @Get(':id/status')
  @ApiOperation({ summary: '작업 실시간 상태 조회 (Redis)' })
  @ApiResponse({ status: 200, description: '작업 상태' })
  async getJobStatus(@Param('id') id: string): Promise<any> {
    return this.sampleEmbeddingsService.getJobStatus(id);
  }

  @Post(':id/retry')
  @ApiOperation({ summary: '작업 재시도' })
  @ApiResponse({ status: 200, description: '재시도 결과' })
  async retryJob(@Param('id') id: string): Promise<any> {
    return this.sampleEmbeddingsService.retryJob(id);
  }

  @Post(':id/cancel')
  @ApiOperation({ summary: '작업 취소' })
  @ApiResponse({ status: 200, description: '취소 결과' })
  async cancelJob(@Param('id') id: string): Promise<any> {
    return this.sampleEmbeddingsService.cancelJob(id);
  }
}
