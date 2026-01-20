import { IsInt, IsOptional, Min, Max } from 'class-validator';
import { Type } from 'class-transformer';
import { ApiPropertyOptional } from '@nestjs/swagger';

/**
 * 임베딩 트리거 요청 DTO
 */
export class TriggerEmbeddingDto {
  @ApiPropertyOptional({
    description: '처리할 논문 수 (기본값: 50, 최대: 500)',
    example: 100,
    minimum: 1,
    maximum: 500,
  })
  @IsOptional()
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1, { message: 'limit은 최소 1 이상이어야 합니다' })
  @Max(500, { message: 'limit은 최대 500 이하여야 합니다' })
  @Type(() => Number)
  limit?: number;
}

/**
 * 재임베딩 트리거 요청 DTO
 */
export class TriggerReembeddingDto {
  @ApiPropertyOptional({
    description: '처리할 논문 수 (미지정 시 전체)',
    example: 50,
    minimum: 1,
    maximum: 500,
  })
  @IsOptional()
  @IsInt({ message: 'limit은 정수여야 합니다' })
  @Min(1, { message: 'limit은 최소 1 이상이어야 합니다' })
  @Max(500, { message: 'limit은 최대 500 이하여야 합니다' })
  @Type(() => Number)
  limit?: number;
}
