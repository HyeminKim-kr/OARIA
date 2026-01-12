import { IsString, IsBoolean, IsOptional, IsObject, MaxLength } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class RAGParametersDto {
  @ApiPropertyOptional({ description: '검색 결과 개수', example: 10 })
  @IsOptional()
  limit?: number;

  @ApiPropertyOptional({ description: 'Hybrid 검색 alpha 값 (0=키워드, 1=벡터)', example: 0.7 })
  @IsOptional()
  alpha?: number;

  @ApiPropertyOptional({ description: '최소 리랭크 점수', example: 0.3 })
  @IsOptional()
  minRerankScore?: number;

  @ApiPropertyOptional({ description: 'LLM temperature', example: 0.7 })
  @IsOptional()
  temperature?: number;
}

export class CreateRAGSettingsDto {
  @ApiProperty({ description: '설정 이름', example: 'high-precision' })
  @IsString()
  @MaxLength(50)
  name: string;

  @ApiPropertyOptional({ description: '설정 설명' })
  @IsOptional()
  @IsString()
  description?: string;

  @ApiPropertyOptional({ description: '청킹 전략', example: 'semantic' })
  @IsOptional()
  @IsString()
  chunker?: string;

  @ApiPropertyOptional({ description: '임베딩 모델', example: 'openai' })
  @IsOptional()
  @IsString()
  embedder?: string;

  @ApiPropertyOptional({ description: '검색 전략', example: 'hybrid' })
  @IsOptional()
  @IsString()
  retriever?: string;

  @ApiPropertyOptional({ description: '리랭킹 모델 (null=미사용)', example: 'bge' })
  @IsOptional()
  @IsString()
  reranker?: string | null;

  @ApiPropertyOptional({ description: '도메인 분류기 (null=미사용)', example: 'pubmedbert_domain_v1' })
  @IsOptional()
  @IsString()
  classifier?: string | null;

  @ApiPropertyOptional({ description: '추가 파라미터' })
  @IsOptional()
  @IsObject()
  parameters?: RAGParametersDto;
}

export class UpdateRAGSettingsDto {
  @ApiPropertyOptional({ description: '설정 이름' })
  @IsOptional()
  @IsString()
  @MaxLength(50)
  name?: string;

  @ApiPropertyOptional({ description: '설정 설명' })
  @IsOptional()
  @IsString()
  description?: string;

  @ApiPropertyOptional({ description: '청킹 전략' })
  @IsOptional()
  @IsString()
  chunker?: string;

  @ApiPropertyOptional({ description: '임베딩 모델' })
  @IsOptional()
  @IsString()
  embedder?: string;

  @ApiPropertyOptional({ description: '검색 전략' })
  @IsOptional()
  @IsString()
  retriever?: string;

  @ApiPropertyOptional({ description: '리랭킹 모델' })
  @IsOptional()
  @IsString()
  reranker?: string | null;

  @ApiPropertyOptional({ description: '도메인 분류기' })
  @IsOptional()
  @IsString()
  classifier?: string | null;

  @ApiPropertyOptional({ description: '추가 파라미터' })
  @IsOptional()
  @IsObject()
  parameters?: RAGParametersDto;

  @ApiPropertyOptional({ description: '활성화 여부' })
  @IsOptional()
  @IsBoolean()
  isActive?: boolean;
}

export class ActivateRAGSettingsDto {
  @ApiProperty({ description: '활성화할 설정 ID' })
  @IsString()
  id: string;
}
