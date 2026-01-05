import { ApiProperty, ApiPropertyOptional, PartialType } from '@nestjs/swagger';
import {
  IsString,
  IsBoolean,
  IsNumber,
  IsOptional,
  MinLength,
  MaxLength,
  Min,
  Max,
} from 'class-validator';

export class CreateSearchQueryDto {
  @ApiProperty({ description: '쿼리 이름', example: '폐암 면역치료' })
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  name: string;

  @ApiProperty({
    description: 'Europe PMC 검색 쿼리',
    example: 'lung cancer immunotherapy',
  })
  @IsString()
  @MinLength(1)
  query: string;

  @ApiPropertyOptional({ description: '설명' })
  @IsString()
  @IsOptional()
  description?: string;

  @ApiPropertyOptional({ description: '활성화 여부', default: true })
  @IsBoolean()
  @IsOptional()
  isActive?: boolean;

  @ApiPropertyOptional({ description: '우선순위 (낮을수록 먼저)', default: 10 })
  @IsNumber()
  @IsOptional()
  @Min(1)
  @Max(100)
  priority?: number;

  @ApiPropertyOptional({ description: '최대 수집 건수' })
  @IsNumber()
  @IsOptional()
  @Min(1)
  maxResults?: number;

  @ApiPropertyOptional({ description: '시작 연도', example: 2020 })
  @IsNumber()
  @IsOptional()
  @Min(1900)
  @Max(2100)
  yearFrom?: number;

  @ApiPropertyOptional({ description: '종료 연도', example: 2024 })
  @IsNumber()
  @IsOptional()
  @Min(1900)
  @Max(2100)
  yearTo?: number;

  @ApiPropertyOptional({ description: 'OA만 수집', default: true })
  @IsBoolean()
  @IsOptional()
  openAccessOnly?: boolean;

  @ApiPropertyOptional({ description: '동시 API 요청 수', default: 35 })
  @IsNumber()
  @IsOptional()
  @Min(1)
  @Max(100)
  maxConcurrent?: number;

  @ApiPropertyOptional({ description: '생성 시 자동 백필 실행', default: false })
  @IsBoolean()
  @IsOptional()
  autoBackfill?: boolean;
}

export class UpdateSearchQueryDto extends PartialType(CreateSearchQueryDto) {}

export class PreviewQueryDto {
  @ApiProperty({
    description: 'Europe PMC 검색 쿼리',
    example: 'lung cancer immunotherapy',
  })
  @IsString()
  @MinLength(1)
  query: string;

  @ApiPropertyOptional({ description: '시작 연도', example: 2020 })
  @IsNumber()
  @IsOptional()
  @Min(1900)
  @Max(2100)
  yearFrom?: number;

  @ApiPropertyOptional({ description: '종료 연도', example: 2024 })
  @IsNumber()
  @IsOptional()
  @Min(1900)
  @Max(2100)
  yearTo?: number;

  @ApiPropertyOptional({ description: 'OA만 수집', default: true })
  @IsBoolean()
  @IsOptional()
  openAccessOnly?: boolean;
}

export class PreviewResponseDto {
  @ApiProperty({ description: '검색 결과 총 건수' })
  hitCount: number;

  @ApiProperty({ description: '실제 검색에 사용된 쿼리' })
  fullQuery: string;
}

export class SearchQueryResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  name: string;

  @ApiProperty()
  query: string;

  @ApiPropertyOptional()
  description: string | null;

  @ApiProperty()
  isActive: boolean;

  @ApiProperty()
  priority: number;

  @ApiPropertyOptional()
  maxResults: number | null;

  @ApiPropertyOptional()
  yearFrom: number | null;

  @ApiPropertyOptional()
  yearTo: number | null;

  @ApiProperty()
  openAccessOnly: boolean;

  @ApiProperty()
  maxConcurrent: number;

  @ApiProperty()
  autoBackfill: boolean;

  @ApiProperty()
  totalCollected: number;

  @ApiPropertyOptional()
  lastBackfillAt: Date | null;

  @ApiProperty()
  createdAt: Date;

  @ApiProperty()
  updatedAt: Date;
}
