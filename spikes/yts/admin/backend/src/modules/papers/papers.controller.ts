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
} from './types';
import {
  FindAllPapersQueryDto,
  GetRecentPapersQueryDto,
  TriggerEmbedAllQueryDto,
  TriggerEmbedByQueryQueryDto,
  TriggerReembedQueryDto,
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
}
