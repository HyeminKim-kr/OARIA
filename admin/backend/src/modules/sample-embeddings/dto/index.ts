import { IsString, IsUUID, IsOptional, IsEnum } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { SampleEmbeddingStatus } from '../../../entities/sample-embedding.entity';

export class CreateSampleEmbeddingDto {
  @ApiProperty({ description: '샘플 쿼리 ID', example: 'uuid' })
  @IsUUID()
  queryId: string;

  @ApiProperty({ description: '청킹 전략', example: 'semantic_section_700t' })
  @IsString()
  chunker: string;

  @ApiProperty({ description: '임베딩 모델', example: 'openai_3small_1536d' })
  @IsString()
  embedder: string;
}

export class SampleEmbeddingResponseDto {
  @ApiProperty({ description: 'ID' })
  id: string;

  @ApiProperty({ description: '샘플 쿼리 ID' })
  queryId: string;

  @ApiProperty({ description: '청킹 전략' })
  chunker: string;

  @ApiProperty({ description: '임베딩 모델' })
  embedder: string;

  @ApiProperty({ description: '파이프라인 키' })
  pipelineKey: string;

  @ApiProperty({ description: 'Weaviate 컬렉션명' })
  collectionName: string;

  @ApiProperty({ description: '상태', enum: ['pending', 'processing', 'completed', 'failed'] })
  status: SampleEmbeddingStatus;

  @ApiProperty({ description: '논문 수' })
  paperCount: number;

  @ApiProperty({ description: '청크 수' })
  chunkCount: number;

  @ApiPropertyOptional({ description: '에러 메시지' })
  errorMessage: string | null;

  @ApiProperty({ description: '생성일시' })
  createdAt: Date;

  @ApiPropertyOptional({ description: '시작일시' })
  startedAt: Date | null;

  @ApiPropertyOptional({ description: '완료일시' })
  completedAt: Date | null;
}

export class ListSampleEmbeddingsQueryDto {
  @ApiPropertyOptional({ description: '샘플 쿼리 ID로 필터링' })
  @IsOptional()
  @IsUUID()
  queryId?: string;

  @ApiPropertyOptional({ description: '상태로 필터링', enum: ['pending', 'processing', 'completed', 'failed'] })
  @IsOptional()
  @IsEnum(['pending', 'processing', 'completed', 'failed'])
  status?: SampleEmbeddingStatus;
}
