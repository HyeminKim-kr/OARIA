import {
  Controller,
  Get,
  Post,
  Param,
  Query,
  ParseUUIDPipe,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { PapersService } from './papers.service';
import { Paper } from '../../entities/paper.entity';
import {
  PaginatedResult,
  PaperStats,
  EmbedTriggerResult,
  FulltextResult,
  EmbedBatchTriggerResult,
  EmbedJobsResult,
  EmbedBatchCancelResult,
  CitationListResult,
  PdfUrlResult,
  PdfExistsResult,
} from './types';
import {
  FindAllPapersQueryDto,
  GetRecentPapersQueryDto,
  TriggerEmbedAllQueryDto,
  TriggerEmbedByQueryQueryDto,
  TriggerReembedQueryDto,
  TriggerEmbedBatchQueryDto,
} from './dto';
import {
  ApiPapersFindAll,
  ApiPapersGetStats,
  ApiPapersGetRecent,
  ApiPapersFindOne,
  ApiPapersGetFulltext,
  ApiPapersTriggerEmbedAll,
  ApiPapersTriggerEmbedByQuery,
  ApiPapersTriggerEmbedPaper,
  ApiPapersTriggerReembed,
  ApiPapersGetEmbedJobs,
  ApiPapersTriggerEmbedBatch,
  ApiPapersCancelEmbedBatch,
  ApiPapersRetryEmbedJob,
  ApiPapersCancelEmbedJob,
  ApiPapersCheckPdfExists,
  ApiPapersGetPdfUrl,
  ApiPapersGetCitations,
  ApiPapersGetReferences,
} from './swagger';

@ApiTags('Papers')
@Controller('papers')
export class PapersController {
  constructor(private readonly service: PapersService) {}

  @Get()
  @ApiPapersFindAll()
  findAll(@Query() query: FindAllPapersQueryDto): Promise<PaginatedResult<Paper>> {
    return this.service.findAll({
      search: query.search,
      status: query.status,
      embeddingStatus: query.embeddingStatus,
      yearFrom: query.yearFrom,
      yearTo: query.yearTo,
      page: query.page ?? 1,
      limit: query.limit ?? 20,
    });
  }

  @Get('stats')
  @ApiPapersGetStats()
  getStats(): Promise<PaperStats> {
    return this.service.getStats();
  }

  @Get('recent')
  @ApiPapersGetRecent()
  getRecent(@Query() query: GetRecentPapersQueryDto): Promise<Paper[]> {
    return this.service.getRecentPapers(query.limit ?? 10);
  }

  @Get(':id/fulltext')
  @ApiPapersGetFulltext()
  getFulltext(@Param('id', ParseUUIDPipe) id: string): Promise<FulltextResult> {
    return this.service.getFulltext(id);
  }

  @Get(':id')
  @ApiPapersFindOne()
  findOne(@Param('id', ParseUUIDPipe) id: string): Promise<Paper> {
    return this.service.findOne(id);
  }

  // ─────────────────────────────────────────────────────────────
  // 임베딩 관련 엔드포인트
  // ─────────────────────────────────────────────────────────────

  @Post('embed/all')
  @ApiPapersTriggerEmbedAll()
  triggerEmbedAll(@Query() query: TriggerEmbedAllQueryDto): Promise<EmbedTriggerResult> {
    return this.service.triggerEmbedAll(query.limit);
  }

  @Post('embed/query/:queryId')
  @ApiPapersTriggerEmbedByQuery()
  triggerEmbedByQuery(
    @Param('queryId', ParseUUIDPipe) queryId: string,
    @Query() query: TriggerEmbedByQueryQueryDto,
  ): Promise<EmbedTriggerResult> {
    return this.service.triggerEmbedByQuery(queryId, query.limit);
  }

  @Post(':id/embed')
  @ApiPapersTriggerEmbedPaper()
  async triggerEmbedPaper(@Param('id', ParseUUIDPipe) id: string): Promise<EmbedTriggerResult> {
    const paper = await this.service.findOne(id);
    return this.service.triggerEmbedPaper(paper.paperId);
  }

  @Post('embed/retry')
  @ApiPapersTriggerReembed()
  triggerReembed(@Query() query: TriggerReembedQueryDto): Promise<EmbedTriggerResult> {
    return this.service.triggerReembed(query.queryId);
  }

  // ─────────────────────────────────────────────────────────────
  // Job Manager V2 기반 임베딩 엔드포인트
  // ─────────────────────────────────────────────────────────────

  @Get('embedding/jobs')
  @ApiPapersGetEmbedJobs()
  getEmbedJobs(): Promise<EmbedJobsResult> {
    return this.service.getEmbedJobs();
  }

  @Post('embedding/batch-trigger')
  @ApiPapersTriggerEmbedBatch()
  triggerEmbedBatch(@Query() query: TriggerEmbedBatchQueryDto): Promise<EmbedBatchTriggerResult> {
    return this.service.triggerEmbedBatch(query.limit);
  }

  @Post('embedding/batch-cancel')
  @ApiPapersCancelEmbedBatch()
  cancelEmbedBatch(): Promise<EmbedBatchCancelResult> {
    return this.service.cancelEmbedBatch();
  }

  @Post('embedding/jobs/:jobId/retry')
  @ApiPapersRetryEmbedJob()
  retryEmbedJob(@Param('jobId') jobId: string): Promise<{ success: boolean }> {
    return this.service.retryEmbedJob(jobId).then(success => ({ success }));
  }

  @Post('embedding/jobs/:jobId/cancel')
  @ApiPapersCancelEmbedJob()
  cancelEmbedJob(@Param('jobId') jobId: string): Promise<{ success: boolean }> {
    return this.service.cancelEmbedJob(jobId).then(success => ({ success }));
  }

  // ─────────────────────────────────────────────────────────────
  // PDF 관련 엔드포인트
  // ─────────────────────────────────────────────────────────────

  @Get(':id/pdf/exists')
  @ApiPapersCheckPdfExists()
  checkPdfExists(@Param('id', ParseUUIDPipe) id: string): Promise<PdfExistsResult> {
    return this.service.checkPdfExists(id);
  }

  @Get(':id/pdf/url')
  @ApiPapersGetPdfUrl()
  getPdfUrl(@Param('id', ParseUUIDPipe) id: string): Promise<PdfUrlResult> {
    return this.service.getPdfUrl(id);
  }

  // ─────────────────────────────────────────────────────────────
  // Citations/References 관련 엔드포인트
  // ─────────────────────────────────────────────────────────────

  @Get(':id/citations')
  @ApiPapersGetCitations()
  getCitations(@Param('id', ParseUUIDPipe) id: string): Promise<CitationListResult> {
    return this.service.getCitations(id);
  }

  @Get(':id/references')
  @ApiPapersGetReferences()
  getReferences(@Param('id', ParseUUIDPipe) id: string): Promise<CitationListResult> {
    return this.service.getReferences(id);
  }
}
