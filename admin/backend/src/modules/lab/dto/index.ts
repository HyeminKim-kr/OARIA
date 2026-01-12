import { IsString, IsOptional, IsNumber, Min, Max, IsIn, IsBoolean, IsUUID, ValidateNested } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Type } from 'class-transformer';

export class SearchTestDto {
  @ApiProperty({
    description: '검색할 질문/쿼리',
    example: 'What are the effects of climate change on biodiversity?',
  })
  @IsString()
  query: string;

  @ApiPropertyOptional({
    description: '검색 결과 개수 (기본값: 10)',
    minimum: 1,
    maximum: 50,
    default: 10,
  })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  @Min(1)
  @Max(50)
  limit?: number = 10;

  @ApiPropertyOptional({
    description: '하이브리드 검색 가중치 (0: 키워드 only, 1: 벡터 only, 기본값: 0.7)',
    minimum: 0,
    maximum: 1,
    default: 0.7,
  })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  @Min(0)
  @Max(1)
  alpha?: number = 0.7;

  @ApiPropertyOptional({
    description: 'Reranker 사용 여부 (기본값: false)',
    default: false,
  })
  @IsOptional()
  @IsBoolean()
  @Type(() => Boolean)
  useReranker?: boolean = false;

  @ApiPropertyOptional({
    description: 'Reranker 모델 선택 (예: bge, none)',
    example: 'bge',
  })
  @IsOptional()
  @IsString()
  reranker?: string;

  @ApiPropertyOptional({
    description: 'Reranker 최소 점수 임계값 (0~1)',
    minimum: 0,
    maximum: 1,
  })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  @Min(0)
  @Max(1)
  minRerankScore?: number;

  @ApiPropertyOptional({
    description: '샘플 임베딩 컬렉션 이름',
    example: 'MedicalChunks_sample_semantic_section_700t_openai_3small',
  })
  @IsOptional()
  @IsString()
  collectionName?: string;

  @ApiPropertyOptional({
    description: 'Classifier 전략 (예: pubmedbert_domain_v1). None이면 분류하지 않음',
    example: 'pubmedbert_domain_v1',
  })
  @IsOptional()
  @IsString()
  classifier?: string;
}

export class GenerateTestDto {
  @ApiProperty({
    description: '질문',
    example: 'What are the main findings about climate change impacts?',
  })
  @IsString()
  query: string;

  @ApiPropertyOptional({
    description: '검색 결과 개수 (기본값: 5)',
    minimum: 1,
    maximum: 20,
    default: 5,
  })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  @Min(1)
  @Max(20)
  limit?: number = 5;

  @ApiPropertyOptional({
    description: '하이브리드 검색 가중치',
    minimum: 0,
    maximum: 1,
    default: 0.7,
  })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  @Min(0)
  @Max(1)
  alpha?: number = 0.7;

  @ApiPropertyOptional({
    description: 'Reranker 사용 여부 (기본값: false)',
    default: false,
  })
  @IsOptional()
  @IsBoolean()
  @Type(() => Boolean)
  useReranker?: boolean = false;

  @ApiPropertyOptional({
    description: 'Reranker 모델 선택 (예: bge, none)',
    example: 'bge',
  })
  @IsOptional()
  @IsString()
  reranker?: string;

  @ApiPropertyOptional({
    description: '샘플 임베딩 컬렉션 이름',
  })
  @IsOptional()
  @IsString()
  collectionName?: string;

  @ApiPropertyOptional({
    description: 'Classifier 전략 (예: pubmedbert_domain_v1). None이면 분류하지 않음',
    example: 'pubmedbert_domain_v1',
  })
  @IsOptional()
  @IsString()
  classifier?: string;
}

export class CompareSearchConfigDto {
  @ApiProperty({
    description: '검색 결과 개수',
    minimum: 1,
    maximum: 50,
    default: 10,
  })
  @IsNumber()
  @Type(() => Number)
  @Min(1)
  @Max(50)
  limit: number = 10;

  @ApiProperty({
    description: '하이브리드 검색 가중치 (0: 키워드 only, 1: 벡터 only)',
    minimum: 0,
    maximum: 1,
    default: 0.7,
  })
  @IsNumber()
  @Type(() => Number)
  @Min(0)
  @Max(1)
  alpha: number = 0.7;

  @ApiPropertyOptional({
    description: 'Reranker 모델 (null이면 리랭킹 안함)',
    example: 'bge',
  })
  @IsOptional()
  @IsString()
  reranker?: string | null = null;

  @ApiPropertyOptional({
    description: '샘플 임베딩 컬렉션 이름 (null이면 프로덕션 사용)',
  })
  @IsOptional()
  @IsString()
  collectionName?: string | null = null;
}

export class CompareTestDto {
  @ApiProperty({
    description: 'A/B 비교할 질문/쿼리',
    example: 'What are the effects of climate change on biodiversity?',
  })
  @IsString()
  query: string;

  @ApiProperty({
    description: '설정 A',
    type: CompareSearchConfigDto,
  })
  @ValidateNested()
  @Type(() => CompareSearchConfigDto)
  configA: CompareSearchConfigDto;

  @ApiProperty({
    description: '설정 B',
    type: CompareSearchConfigDto,
  })
  @ValidateNested()
  @Type(() => CompareSearchConfigDto)
  configB: CompareSearchConfigDto;
}

// 피드백 파라미터 (테스트 시 사용된 설정)
export class FeedbackParametersDto {
  @ApiProperty({ description: '검색 결과 개수' })
  @IsNumber()
  limit: number;

  @ApiProperty({ description: '하이브리드 검색 가중치' })
  @IsNumber()
  alpha: number;

  @ApiPropertyOptional({ description: 'Reranker 사용 여부' })
  @IsOptional()
  @IsBoolean()
  useReranker?: boolean;

  @ApiPropertyOptional({ description: 'Reranker 최소 점수' })
  @IsOptional()
  @IsNumber()
  minRerankScore?: number;

  @ApiPropertyOptional({ description: 'Reranker 모델명' })
  @IsOptional()
  @IsString()
  rerankerModel?: string;
}

// 피드백 결과 요약
export class FeedbackResultSummaryDto {
  @ApiProperty({ description: '총 청크 수' })
  @IsNumber()
  totalChunks: number;

  @ApiProperty({ description: '최고 점수' })
  @IsNumber()
  topScore: number;

  @ApiPropertyOptional({ description: '관련성 높은 결과 수' })
  @IsOptional()
  @IsNumber()
  relevantCount?: number;

  @ApiPropertyOptional({ description: '관련성 낮은 결과 수' })
  @IsOptional()
  @IsNumber()
  lowRelevanceCount?: number;

  @ApiPropertyOptional({ description: 'LLM 모델명' })
  @IsOptional()
  @IsString()
  model?: string;

  @ApiPropertyOptional({ description: '토큰 사용량' })
  @IsOptional()
  tokensUsed?: {
    prompt: number;
    completion: number;
  };
}

export class FeedbackDto {
  @ApiProperty({
    description: '피드백 타입',
    enum: ['search', 'generate'],
  })
  @IsString()
  @IsIn(['search', 'generate'])
  type: 'search' | 'generate';

  @ApiProperty({
    description: '검색 쿼리',
    example: 'What are the effects of climate change?',
  })
  @IsString()
  query: string;

  @ApiProperty({
    description: '평가',
    enum: ['good', 'bad'],
  })
  @IsString()
  @IsIn(['good', 'bad'])
  rating: 'good' | 'bad';

  @ApiPropertyOptional({
    description: '추가 코멘트',
  })
  @IsOptional()
  @IsString()
  comment?: string;

  @ApiProperty({
    description: '테스트 파라미터',
    type: FeedbackParametersDto,
  })
  parameters: FeedbackParametersDto;

  @ApiPropertyOptional({
    description: '결과 요약',
    type: FeedbackResultSummaryDto,
  })
  @IsOptional()
  resultSummary?: FeedbackResultSummaryDto;

  @ApiPropertyOptional({ description: '검색 소요 시간 (ms)' })
  @IsOptional()
  @IsNumber()
  searchLatencyMs?: number;

  @ApiPropertyOptional({ description: 'Rerank 소요 시간 (ms)' })
  @IsOptional()
  @IsNumber()
  rerankLatencyMs?: number;

  @ApiPropertyOptional({ description: 'LLM 소요 시간 (ms)' })
  @IsOptional()
  @IsNumber()
  llmLatencyMs?: number;
}

// ===== Test Logs DTOs =====

export class TestLogQueryDto {
  @ApiPropertyOptional({
    description: '페이지 번호 (1부터 시작)',
    minimum: 1,
    default: 1,
  })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  @Min(1)
  page?: number = 1;

  @ApiPropertyOptional({
    description: '페이지당 개수',
    minimum: 1,
    maximum: 100,
    default: 20,
  })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  @Min(1)
  @Max(100)
  limit?: number = 20;

  @ApiPropertyOptional({
    description: '테스트 유형 필터',
    enum: ['search', 'generate', 'compare'],
  })
  @IsOptional()
  @IsString()
  @IsIn(['search', 'generate', 'compare'])
  testType?: 'search' | 'generate' | 'compare';

  @ApiPropertyOptional({
    description: '쿼리 검색어',
  })
  @IsOptional()
  @IsString()
  query?: string;
}

export class DeleteTestLogDto {
  @ApiProperty({ description: '삭제할 로그 ID' })
  @IsUUID()
  id: string;
}
