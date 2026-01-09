import { ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsString,
  IsOptional,
  IsInt,
  IsEnum,
  Min,
  Max,
} from 'class-validator';
import { Type } from 'class-transformer';
import { PaperStatusEnum, EmbeddingStatusEnum } from '../types';

/**
 * 논문 목록 조회 Query DTO
 */
export class FindAllPapersQueryDto {
  @ApiPropertyOptional({
    description: '검색어 (제목, paperId, pmcid)',
    example: 'lung cancer',
  })
  @IsOptional()
  @IsString()
  search?: string;

  @ApiPropertyOptional({
    description: '논문 상태',
    enum: PaperStatusEnum,
  })
  @IsOptional()
  @IsEnum(PaperStatusEnum, { message: 'status는 collected, chunked, indexed 중 하나여야 합니다' })
  status?: PaperStatusEnum;

  @ApiPropertyOptional({
    description: '임베딩 상태',
    enum: EmbeddingStatusEnum,
  })
  @IsOptional()
  @IsEnum(EmbeddingStatusEnum, { message: 'embeddingStatus는 not_started, pending, processing, completed, failed 중 하나여야 합니다' })
  embeddingStatus?: EmbeddingStatusEnum;

  @ApiPropertyOptional({
    description: '시작 연도',
    example: 2020,
    minimum: 1900,
    maximum: 2100,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'yearFrom은 정수여야 합니다' })
  @Min(1900)
  @Max(2100)
  yearFrom?: number;

  @ApiPropertyOptional({
    description: '종료 연도',
    example: 2024,
    minimum: 1900,
    maximum: 2100,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'yearTo는 정수여야 합니다' })
  @Min(1900)
  @Max(2100)
  yearTo?: number;

  @ApiPropertyOptional({
    description: '페이지 번호',
    example: 1,
    minimum: 1,
    default: 1,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'page는 정수여야 합니다' })
  @Min(1)
  page?: number = 1;

  @ApiPropertyOptional({
    description: '페이지당 항목 수',
    example: 20,
    minimum: 1,
    maximum: 100,
    default: 20,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1)
  @Max(100)
  limit?: number = 20;
}

/**
 * 최근 논문 조회 Query DTO
 */
export class GetRecentPapersQueryDto {
  @ApiPropertyOptional({
    description: '조회할 논문 수',
    example: 10,
    minimum: 1,
    maximum: 50,
    default: 10,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1)
  @Max(50)
  limit?: number = 10;
}

/**
 * 전체 임베딩 트리거 Query DTO
 */
export class TriggerEmbedAllQueryDto {
  @ApiPropertyOptional({
    description: '처리할 논문 수',
    example: 100,
    minimum: 1,
    maximum: 1000,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1)
  @Max(1000)
  limit?: number;
}

/**
 * 쿼리별 임베딩 트리거 Query DTO
 */
export class TriggerEmbedByQueryQueryDto {
  @ApiPropertyOptional({
    description: '처리할 논문 수',
    example: 100,
    minimum: 1,
    maximum: 1000,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1)
  @Max(1000)
  limit?: number;
}

/**
 * 재임베딩 트리거 Query DTO
 */
export class TriggerReembedQueryDto {
  @ApiPropertyOptional({
    description: '특정 쿼리 ID로 필터링',
  })
  @IsOptional()
  @IsString()
  queryId?: string;
}

/**
 * 배치 임베딩 트리거 Query DTO (Job Manager V2)
 */
export class TriggerEmbedBatchQueryDto {
  @ApiPropertyOptional({
    description: '처리할 최대 논문 수 (미지정시 전체)',
    example: 100,
    minimum: 1,
    maximum: 10000,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1)
  @Max(10000)
  limit?: number;
}
