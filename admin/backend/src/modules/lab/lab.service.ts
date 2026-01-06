import { Injectable, Logger, HttpException, HttpStatus, NotFoundException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { HttpService } from '@nestjs/axios';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, Like, ILike } from 'typeorm';
import { firstValueFrom, timeout, catchError } from 'rxjs';
import { of } from 'rxjs';
import {
  SearchTestResult,
  SearchedChunk,
  GenerateTestResult,
  Reference,
  FeedbackResult,
  UserBackendStatus,
  TestLogListResult,
  TestLogItem,
  TestLogParametersType,
} from './types';
import {
  LabFeedback,
  LabTestType,
  FeedbackRating,
  LabTestLog,
  LabTestLogType,
  TestLogParameters,
  TestLogResults,
} from '../../entities';

@Injectable()
export class LabService {
  private readonly logger = new Logger(LabService.name);
  private readonly userBackendUrl: string;

  constructor(
    private readonly configService: ConfigService,
    private readonly httpService: HttpService,
    @InjectRepository(LabFeedback)
    private readonly feedbackRepository: Repository<LabFeedback>,
    @InjectRepository(LabTestLog)
    private readonly testLogRepository: Repository<LabTestLog>,
  ) {
    this.userBackendUrl = this.configService.get('USER_BACKEND_URL', 'http://localhost:8000');
  }

  /**
   * User Backend 상태 확인
   */
  async checkUserBackendStatus(): Promise<UserBackendStatus> {
    const start = Date.now();
    const url = `${this.userBackendUrl}/health`;

    try {
      const response = await firstValueFrom(
        this.httpService.get(url).pipe(
          timeout(5000),
          catchError(() => of(null)),
        ),
      );

      if (response) {
        return {
          available: true,
          url: this.userBackendUrl,
          latencyMs: Date.now() - start,
        };
      }

      return {
        available: false,
        url: this.userBackendUrl,
        error: 'No response',
      };
    } catch (error) {
      return {
        available: false,
        url: this.userBackendUrl,
        error: error instanceof Error ? error.message : 'Connection failed',
      };
    }
  }

  /**
   * RAG 검색 테스트
   * @param skipLog - true면 자동 로그 저장 스킵 (compare 모드에서 사용)
   */
  async testSearch(
    query: string,
    limit: number = 10,
    alpha: number = 0.7,
    useReranker: boolean = false,
    minRerankScore?: number,
    skipLog: boolean = false,
  ): Promise<SearchTestResult> {
    const start = Date.now();
    const url = `${this.userBackendUrl}/lab/search`;

    try {
      const response = await firstValueFrom(
        this.httpService.post(url, {
          query,
          limit,
          alpha,
          use_reranker: useReranker,
          min_rerank_score: minRerankScore,
        }).pipe(
          timeout(60000), // Reranker 사용 시 시간이 더 걸릴 수 있음
        ),
      );

      const data = response.data;
      const chunks: SearchedChunk[] = (data.chunks || []).map((chunk: Record<string, unknown>) => ({
        paperId: chunk.paper_id as string,
        paperTitle: chunk.paper_title as string,
        sectionName: chunk.section_name as string,
        chunkIndex: chunk.chunk_index as number,
        content: chunk.content as string,
        score: chunk.score as number,
        rerankScore: chunk.rerank_score as number | undefined,
        originalScore: chunk.original_score as number | undefined,
        metadata: chunk.metadata as Record<string, unknown>,
      }));

      const result: SearchTestResult = {
        query,
        chunks,
        searchLatencyMs: Date.now() - start,
        rerankLatencyMs: data.rerank_latency_ms as number | undefined,
        totalChunks: chunks.length,
        parameters: {
          limit,
          alpha,
          useReranker,
          minRerankScore,
          rerankerModel: data.parameters?.reranker_model as string | undefined,
        },
      };

      // 자동 로그 저장 (skipLog가 true면 스킵 - compare 모드에서 사용)
      if (!skipLog) {
        this.saveTestLog(
          'search',
          query,
          result.parameters,
          { chunks: result.chunks, totalChunks: result.totalChunks },
          {
            searchLatencyMs: result.searchLatencyMs,
            rerankLatencyMs: result.rerankLatencyMs,
          },
        ).catch((err) => this.logger.error('Failed to auto-save search log', err));
      }

      return result;
    } catch (error) {
      this.logger.error('Search test failed', error);
      this.handleUserBackendError(error);
    }
  }

  /**
   * User Backend 에러를 Admin Frontend로 전달
   */
  private handleUserBackendError(error: unknown): never {
    // axios 에러에서 User Backend 응답 추출
    const axiosError = error as {
      response?: {
        status?: number;
        data?: { detail?: unknown };
      };
    };

    if (axiosError.response?.data?.detail) {
      // User Backend의 에러 응답을 그대로 전달
      throw new HttpException(
        { detail: axiosError.response.data.detail },
        axiosError.response.status || HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }

    // 기타 에러
    throw new HttpException(
      { detail: error instanceof Error ? error.message : 'Unknown error' },
      HttpStatus.INTERNAL_SERVER_ERROR,
    );
  }

  /**
   * RAG + LLM 답변 생성 테스트
   */
  async testGenerate(
    query: string,
    limit: number = 5,
    alpha: number = 0.7,
    useReranker: boolean = false,
  ): Promise<GenerateTestResult> {
    const start = Date.now();
    const url = `${this.userBackendUrl}/lab/generate`;

    try {
      const response = await firstValueFrom(
        this.httpService.post(url, {
          query,
          limit,
          alpha,
          use_reranker: useReranker,
        }).pipe(
          timeout(120000), // Reranker + LLM 시간 고려
        ),
      );

      const data = response.data;
      const references: Reference[] = (data.references || []).map((ref: Record<string, unknown>) => ({
        paperId: ref.paper_id as string,
        title: ref.title as string,
        section: ref.section as string,
        content: ref.content as string,
        score: ref.score as number,
      }));

      const result: GenerateTestResult = {
        query,
        answer: data.answer as string,
        references,
        searchLatencyMs: data.search_latency_ms as number,
        rerankLatencyMs: data.rerank_latency_ms as number | undefined,
        llmLatencyMs: data.llm_latency_ms as number,
        totalLatencyMs: Date.now() - start,
        model: data.model as string,
        tokensUsed: data.tokens_used ? {
          prompt: data.tokens_used.prompt as number,
          completion: data.tokens_used.completion as number,
        } : undefined,
        useReranker: data.use_reranker as boolean | undefined,
      };

      // 자동 로그 저장
      this.saveTestLog(
        'generate',
        query,
        { limit, alpha, useReranker },
        {
          answer: result.answer,
          references: result.references,
          model: result.model,
          tokensUsed: result.tokensUsed,
        },
        {
          searchLatencyMs: result.searchLatencyMs,
          rerankLatencyMs: result.rerankLatencyMs,
          llmLatencyMs: result.llmLatencyMs,
          totalLatencyMs: result.totalLatencyMs,
        },
      ).catch((err) => this.logger.error('Failed to auto-save generate log', err));

      return result;
    } catch (error) {
      this.logger.error('Generate test failed', error);
      this.handleUserBackendError(error);
    }
  }

  /**
   * A/B 비교 테스트 (Reranker ON vs OFF)
   * 두 검색을 수행하고 하나의 compare 로그로 저장
   */
  async testCompare(
    query: string,
    limit: number = 10,
    alpha: number = 0.7,
  ): Promise<{
    withReranker: SearchTestResult;
    withoutReranker: SearchTestResult;
  }> {
    // 두 검색을 병렬로 수행 (skipLog = true로 개별 저장 방지)
    const [withReranker, withoutReranker] = await Promise.all([
      this.testSearch(query, limit, alpha, true, undefined, true),
      this.testSearch(query, limit, alpha, false, undefined, true),
    ]);

    // compare 로그로 단일 저장
    this.saveTestLog(
      'compare',
      query,
      { limit, alpha, useReranker: true }, // compare는 항상 reranker 비교
      {
        withReranker: { chunks: withReranker.chunks, totalChunks: withReranker.totalChunks },
        withoutReranker: { chunks: withoutReranker.chunks, totalChunks: withoutReranker.totalChunks },
      },
      {
        // withReranker의 레이턴시를 기준으로 저장
        searchLatencyMs: withReranker.searchLatencyMs,
        rerankLatencyMs: withReranker.rerankLatencyMs,
      },
    ).catch((err) => this.logger.error('Failed to auto-save compare log', err));

    return { withReranker, withoutReranker };
  }

  /**
   * 피드백 저장
   */
  async saveFeedback(
    type: 'search' | 'generate',
    query: string,
    rating: 'good' | 'bad',
    parameters: {
      limit: number;
      alpha: number;
      useReranker?: boolean;
      minRerankScore?: number;
      rerankerModel?: string;
    },
    options?: {
      comment?: string;
      resultSummary?: {
        totalChunks: number;
        topScore: number;
        relevantCount?: number;
        lowRelevanceCount?: number;
        model?: string;
        tokensUsed?: { prompt: number; completion: number };
      };
      searchLatencyMs?: number;
      rerankLatencyMs?: number;
      llmLatencyMs?: number;
      adminUserId?: string;
    },
  ): Promise<FeedbackResult> {
    try {
      const feedback = this.feedbackRepository.create({
        testType: type === 'search' ? LabTestType.SEARCH : LabTestType.GENERATE,
        query,
        rating: rating === 'good' ? FeedbackRating.GOOD : FeedbackRating.BAD,
        comment: options?.comment || null,
        parameters,
        resultSummary: options?.resultSummary || null,
        searchLatencyMs: options?.searchLatencyMs || null,
        rerankLatencyMs: options?.rerankLatencyMs || null,
        llmLatencyMs: options?.llmLatencyMs || null,
        adminUserId: options?.adminUserId || null,
      });

      const saved = await this.feedbackRepository.save(feedback);

      this.logger.log(`Feedback saved: ${saved.id} - ${type} - ${rating}`);

      return {
        success: true,
        feedbackId: saved.id,
        message: 'Feedback saved successfully',
      };
    } catch (error) {
      this.logger.error('Failed to save feedback', error);
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Failed to save feedback',
      };
    }
  }

  // ===== Test Log Methods =====

  /**
   * 테스트 로그 자동 저장
   */
  async saveTestLog(
    testType: 'search' | 'generate' | 'compare',
    query: string,
    parameters: TestLogParameters,
    results: TestLogResults,
    latency: {
      searchLatencyMs?: number;
      rerankLatencyMs?: number;
      llmLatencyMs?: number;
      totalLatencyMs?: number;
    },
    adminUserId?: string,
  ): Promise<{ id: string }> {
    try {
      const typeMap: Record<string, LabTestLogType> = {
        search: LabTestLogType.SEARCH,
        generate: LabTestLogType.GENERATE,
        compare: LabTestLogType.COMPARE,
      };

      const testLog = this.testLogRepository.create({
        testType: typeMap[testType],
        query,
        parameters,
        results,
        searchLatencyMs: latency.searchLatencyMs ?? null,
        rerankLatencyMs: latency.rerankLatencyMs ?? null,
        llmLatencyMs: latency.llmLatencyMs ?? null,
        totalLatencyMs: latency.totalLatencyMs ?? null,
        adminUserId: adminUserId ?? null,
      });

      const saved = await this.testLogRepository.save(testLog);
      this.logger.log(`Test log saved: ${saved.id} - ${testType}`);

      return { id: saved.id };
    } catch (error) {
      this.logger.error('Failed to save test log', error);
      throw new HttpException(
        { detail: error instanceof Error ? error.message : 'Failed to save test log' },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  /**
   * 테스트 로그 목록 조회
   */
  async getTestLogs(
    page: number = 1,
    limit: number = 20,
    testType?: 'search' | 'generate' | 'compare',
    querySearch?: string,
  ): Promise<TestLogListResult> {
    const skip = (page - 1) * limit;

    const where: Record<string, unknown> = {};

    if (testType) {
      const typeMap: Record<string, LabTestLogType> = {
        search: LabTestLogType.SEARCH,
        generate: LabTestLogType.GENERATE,
        compare: LabTestLogType.COMPARE,
      };
      where.testType = typeMap[testType];
    }

    if (querySearch) {
      where.query = ILike(`%${querySearch}%`);
    }

    const [logs, total] = await this.testLogRepository.findAndCount({
      where,
      order: { createdAt: 'DESC' },
      skip,
      take: limit,
    });

    const items: TestLogItem[] = logs.map((log) => ({
      id: log.id,
      testType: log.testType,
      query: log.query,
      parameters: log.parameters as TestLogParametersType,
      searchLatencyMs: log.searchLatencyMs,
      rerankLatencyMs: log.rerankLatencyMs,
      llmLatencyMs: log.llmLatencyMs,
      totalLatencyMs: log.totalLatencyMs,
      createdAt: log.createdAt.toISOString(),
      // 목록에서는 results 요약만 제공
      resultSummary: this.getResultSummary(log.testType, log.results),
    }));

    return {
      items,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  /**
   * 테스트 로그 상세 조회
   */
  async getTestLogById(id: string): Promise<LabTestLog> {
    const log = await this.testLogRepository.findOne({ where: { id } });

    if (!log) {
      throw new NotFoundException(`Test log not found: ${id}`);
    }

    return log;
  }

  /**
   * 테스트 로그 삭제
   */
  async deleteTestLog(id: string): Promise<{ success: boolean; message: string }> {
    const log = await this.testLogRepository.findOne({ where: { id } });

    if (!log) {
      throw new NotFoundException(`Test log not found: ${id}`);
    }

    await this.testLogRepository.remove(log);
    this.logger.log(`Test log deleted: ${id}`);

    return { success: true, message: 'Test log deleted successfully' };
  }

  /**
   * 피드백 통계 조회
   */
  async getFeedbackStats(): Promise<{
    total: number;
    byRating: { good: number; bad: number };
    byTestType: { search: number; generate: number };
    recentFeedbacks: Array<{
      id: string;
      testType: string;
      query: string;
      rating: string;
      createdAt: string;
    }>;
  }> {
    // 전체 개수
    const total = await this.feedbackRepository.count();

    // 평점별 개수
    const goodCount = await this.feedbackRepository.count({
      where: { rating: FeedbackRating.GOOD },
    });
    const badCount = await this.feedbackRepository.count({
      where: { rating: FeedbackRating.BAD },
    });

    // 테스트 유형별 개수
    const searchCount = await this.feedbackRepository.count({
      where: { testType: LabTestType.SEARCH },
    });
    const generateCount = await this.feedbackRepository.count({
      where: { testType: LabTestType.GENERATE },
    });

    // 최근 피드백 5개
    const recentFeedbacks = await this.feedbackRepository.find({
      order: { createdAt: 'DESC' },
      take: 5,
    });

    return {
      total,
      byRating: { good: goodCount, bad: badCount },
      byTestType: { search: searchCount, generate: generateCount },
      recentFeedbacks: recentFeedbacks.map((f) => ({
        id: f.id,
        testType: f.testType,
        query: f.query,
        rating: f.rating,
        createdAt: f.createdAt.toISOString(),
      })),
    };
  }

  /**
   * 테스트 로그 통계 조회
   */
  async getTestLogStats(): Promise<{
    total: number;
    byTestType: { search: number; generate: number; compare: number };
    avgLatency: {
      search: number | null;
      rerank: number | null;
      llm: number | null;
    };
    todayCount: number;
  }> {
    const total = await this.testLogRepository.count();

    // 테스트 유형별
    const searchCount = await this.testLogRepository.count({
      where: { testType: LabTestLogType.SEARCH },
    });
    const generateCount = await this.testLogRepository.count({
      where: { testType: LabTestLogType.GENERATE },
    });
    const compareCount = await this.testLogRepository.count({
      where: { testType: LabTestLogType.COMPARE },
    });

    // 평균 레이턴시
    const avgResult = await this.testLogRepository
      .createQueryBuilder('log')
      .select('AVG(log.searchLatencyMs)', 'avgSearch')
      .addSelect('AVG(log.rerankLatencyMs)', 'avgRerank')
      .addSelect('AVG(log.llmLatencyMs)', 'avgLlm')
      .getRawOne();

    // 오늘 테스트 수
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayCount = await this.testLogRepository
      .createQueryBuilder('log')
      .where('log.createdAt >= :today', { today })
      .getCount();

    return {
      total,
      byTestType: { search: searchCount, generate: generateCount, compare: compareCount },
      avgLatency: {
        search: avgResult?.avgSearch ? Math.round(Number(avgResult.avgSearch)) : null,
        rerank: avgResult?.avgRerank ? Math.round(Number(avgResult.avgRerank)) : null,
        llm: avgResult?.avgLlm ? Math.round(Number(avgResult.avgLlm)) : null,
      },
      todayCount,
    };
  }

  /**
   * results에서 요약 정보 추출
   */
  private getResultSummary(testType: LabTestLogType, results: TestLogResults): Record<string, unknown> {
    if (testType === LabTestLogType.SEARCH) {
      const searchResults = results as { chunks: unknown[]; totalChunks: number };
      return {
        totalChunks: searchResults.totalChunks,
      };
    }

    if (testType === LabTestLogType.GENERATE) {
      const generateResults = results as { answer: string; references: unknown[]; model: string };
      return {
        answerLength: generateResults.answer?.length || 0,
        referencesCount: generateResults.references?.length || 0,
        model: generateResults.model,
      };
    }

    if (testType === LabTestLogType.COMPARE) {
      const compareResults = results as {
        withReranker: { totalChunks: number };
        withoutReranker: { totalChunks: number };
      };
      return {
        withRerankerChunks: compareResults.withReranker?.totalChunks || 0,
        withoutRerankerChunks: compareResults.withoutReranker?.totalChunks || 0,
      };
    }

    return {};
  }
}
