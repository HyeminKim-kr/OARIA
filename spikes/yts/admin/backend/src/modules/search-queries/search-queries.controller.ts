import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Body,
  Param,
  ParseUUIDPipe,
  Logger,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { SearchQueriesService } from './search-queries.service';
import { CollectionJobsService } from '../collection-jobs/collection-jobs.service';
import { CreateSearchQueryDto, UpdateSearchQueryDto, SearchQueryResponseDto, PreviewQueryDto, PreviewResponseDto } from './dto';

@ApiTags('Search Queries')
@Controller('search-queries')
export class SearchQueriesController {
  private readonly logger = new Logger(SearchQueriesController.name);

  constructor(
    private readonly service: SearchQueriesService,
    private readonly collectionJobsService: CollectionJobsService,
  ) {}

  @Get()
  @ApiOperation({ summary: '검색 쿼리 목록 조회' })
  @ApiResponse({ status: 200, type: [SearchQueryResponseDto] })
  findAll() {
    return this.service.findAll();
  }

  @Get('active')
  @ApiOperation({ summary: '활성 검색 쿼리 목록' })
  findActive() {
    return this.service.findActive();
  }

  @Get('stats')
  @ApiOperation({ summary: '검색 쿼리 통계' })
  getStats() {
    return this.service.getStats();
  }

  @Post('preview')
  @ApiOperation({ summary: 'Europe PMC 검색 결과 미리보기' })
  @ApiResponse({ status: 200, type: PreviewResponseDto })
  preview(@Body() dto: PreviewQueryDto) {
    return this.service.preview(dto);
  }

  @Get(':id')
  @ApiOperation({ summary: '검색 쿼리 상세 조회' })
  findOne(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.findOne(id);
  }

  @Post()
  @ApiOperation({ summary: '검색 쿼리 생성' })
  @ApiResponse({ status: 201, type: SearchQueryResponseDto })
  async create(@Body() dto: CreateSearchQueryDto) {
    const query = await this.service.create(dto);

    // autoBackfill이 true면 자동으로 백필 트리거
    if (dto.autoBackfill) {
      try {
        const result = await this.collectionJobsService.triggerBackfill(query.id);
        this.logger.log(`Auto backfill triggered for query ${query.id}, taskId: ${result.taskId}`);
      } catch (error) {
        this.logger.error(`Failed to trigger auto backfill for query ${query.id}: ${error.message}`);
        // 백필 실패해도 쿼리 생성은 성공으로 처리
      }
    }

    return query;
  }

  @Patch(':id')
  @ApiOperation({ summary: '검색 쿼리 수정' })
  update(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateSearchQueryDto,
  ) {
    return this.service.update(id, dto);
  }

  @Patch(':id/toggle')
  @ApiOperation({ summary: '활성/비활성 토글' })
  toggleActive(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.toggleActive(id);
  }

  @Delete(':id')
  @ApiOperation({ summary: '검색 쿼리 삭제' })
  remove(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.remove(id);
  }

  @Post(':id/backfill')
  @ApiOperation({ summary: 'Backfill 실행 트리거' })
  async triggerBackfill(@Param('id', ParseUUIDPipe) id: string) {
    // 쿼리 존재 확인
    await this.service.findOne(id);
    return this.collectionJobsService.triggerBackfill(id);
  }
}
