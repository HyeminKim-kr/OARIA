import { ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsOptional,
  IsInt,
  IsEnum,
  Min,
  Max,
} from 'class-validator';
import { Type } from 'class-transformer';
import { JobStatusEnum, JobTypeEnum, ErrorStageEnum } from '../types';

/**
 * Job 목록 조회 Query DTO
 */
export class FindAllJobsQueryDto {
  @ApiPropertyOptional({
    description: 'Job 상태',
    enum: JobStatusEnum,
  })
  @IsOptional()
  @IsEnum(JobStatusEnum, { message: 'status는 유효한 상태값이어야 합니다' })
  status?: JobStatusEnum;

  @ApiPropertyOptional({
    description: 'Job 타입',
    enum: JobTypeEnum,
  })
  @IsOptional()
  @IsEnum(JobTypeEnum, { message: 'jobType은 backfill, incremental, repair 중 하나여야 합니다' })
  jobType?: JobTypeEnum;

  @ApiPropertyOptional({
    description: '조회할 Job 수',
    example: 50,
    minimum: 1,
    maximum: 100,
    default: 50,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1)
  @Max(100)
  limit?: number = 50;
}

/**
 * Job 에러 조회 Query DTO
 */
export class GetJobErrorsQueryDto {
  @ApiPropertyOptional({
    description: '에러 스테이지',
    enum: ErrorStageEnum,
  })
  @IsOptional()
  @IsEnum(ErrorStageEnum, { message: 'stage는 search, download, parse, save 중 하나여야 합니다' })
  stage?: ErrorStageEnum;

  @ApiPropertyOptional({
    description: '조회할 에러 수',
    example: 100,
    minimum: 1,
    maximum: 500,
    default: 100,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1)
  @Max(500)
  limit?: number = 100;

  @ApiPropertyOptional({
    description: '시작 오프셋',
    example: 0,
    minimum: 0,
    default: 0,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt({ message: 'offset은 정수여야 합니다' })
  @Min(0)
  offset?: number = 0;
}
