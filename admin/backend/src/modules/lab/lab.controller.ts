import {
  Controller,
  Get,
  Post,
  Delete,
  Body,
  Query,
  Param,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { LabService } from './lab.service';
import { SearchTestDto, GenerateTestDto, CompareTestDto, FeedbackDto, TestLogQueryDto } from './dto';
import {
  ApiLabStatus,
  ApiLabSearch,
  ApiLabGenerate,
  ApiLabCompare,
  ApiLabFeedback,
  ApiLabTestLogList,
  ApiLabTestLogDetail,
  ApiLabTestLogDelete,
} from './swagger';
import {
  SearchTestResult,
  GenerateTestResult,
  FeedbackResult,
  UserBackendStatus,
  TestLogListResult,
  StrategiesResponse,
  StrategiesDetailResponse,
  DBStrategiesResponse,
} from './types';
import { LabTestLog } from '../../entities';

@ApiTags('Lab')
@Controller('lab')
export class LabController {
  constructor(private readonly labService: LabService) {}

  @Get('status')
  @ApiLabStatus()
  async getStatus(): Promise<UserBackendStatus> {
    return this.labService.checkUserBackendStatus();
  }

  @Get('strategies')
  async getStrategies(): Promise<StrategiesResponse> {
    return this.labService.getStrategies();
  }

  @Get('strategies/detail')
  async getStrategiesDetail(): Promise<StrategiesDetailResponse> {
    return this.labService.getStrategiesDetail();
  }

  @Get('strategies/db')
  async getStrategiesFromDB(
    @Query('active_only') activeOnly?: string,
  ): Promise<DBStrategiesResponse> {
    const isActiveOnly = activeOnly !== 'false';
    return this.labService.getStrategiesFromDB(isActiveOnly);
  }

  @Post('search')
  @HttpCode(HttpStatus.OK)
  @ApiLabSearch()
  async testSearch(@Body() dto: SearchTestDto): Promise<SearchTestResult> {
    return this.labService.testSearch(
      dto.query,
      dto.limit,
      dto.alpha,
      dto.useReranker,
      dto.reranker,
      dto.minRerankScore,
      dto.collectionName,
      false, // skipLog
      dto.classifier,
    );
  }

  @Post('generate')
  @HttpCode(HttpStatus.OK)
  @ApiLabGenerate()
  async testGenerate(@Body() dto: GenerateTestDto): Promise<GenerateTestResult> {
    return this.labService.testGenerate(
      dto.query,
      dto.limit,
      dto.alpha,
      dto.useReranker,
      dto.reranker,
      dto.collectionName,
      dto.classifier,
    );
  }

  @Post('compare')
  @HttpCode(HttpStatus.OK)
  @ApiLabCompare()
  async testCompare(@Body() dto: CompareTestDto): Promise<{
    configA: SearchTestResult;
    configB: SearchTestResult;
  }> {
    return this.labService.testCompare(
      dto.query,
      dto.configA,
      dto.configB,
    );
  }

  @Post('feedback')
  @HttpCode(HttpStatus.OK)
  @ApiLabFeedback()
  async saveFeedback(@Body() dto: FeedbackDto): Promise<FeedbackResult> {
    return this.labService.saveFeedback(
      dto.type,
      dto.query,
      dto.rating,
      dto.parameters,
      {
        comment: dto.comment,
        resultSummary: dto.resultSummary,
        searchLatencyMs: dto.searchLatencyMs,
        rerankLatencyMs: dto.rerankLatencyMs,
        llmLatencyMs: dto.llmLatencyMs,
      },
    );
  }

  // ===== Stats Endpoints =====

  @Get('stats/feedback')
  async getFeedbackStats() {
    return this.labService.getFeedbackStats();
  }

  @Get('stats/logs')
  async getTestLogStats() {
    return this.labService.getTestLogStats();
  }

  // ===== Test Logs Endpoints =====

  @Get('logs')
  @ApiLabTestLogList()
  async getTestLogs(@Query() query: TestLogQueryDto): Promise<TestLogListResult> {
    return this.labService.getTestLogs(
      query.page,
      query.limit,
      query.testType,
      query.query,
    );
  }

  @Get('logs/:id')
  @ApiLabTestLogDetail()
  async getTestLogById(@Param('id') id: string): Promise<LabTestLog> {
    return this.labService.getTestLogById(id);
  }

  @Delete('logs/:id')
  @HttpCode(HttpStatus.OK)
  @ApiLabTestLogDelete()
  async deleteTestLog(@Param('id') id: string): Promise<{ success: boolean; message: string }> {
    return this.labService.deleteTestLog(id);
  }
}
