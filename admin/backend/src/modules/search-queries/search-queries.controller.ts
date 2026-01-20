import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Body,
  Param,
  Query,
  ParseUUIDPipe,
  Logger,
} from '@nestjs/common';
import { ApiTags, ApiQuery } from '@nestjs/swagger';
import { SearchQueriesService } from './search-queries.service';
import { CollectionJobsService } from '../collection-jobs/collection-jobs.service';
import { CreateSearchQueryDto, UpdateSearchQueryDto, PreviewQueryDto, ListSearchQueriesQueryDto } from './dto';
import {
  ApiQueriesFindAll,
  ApiQueriesFindActive,
  ApiQueriesGetStats,
  ApiQueriesFindOne,
  ApiQueriesPreview,
  ApiQueriesCreate,
  ApiQueriesUpdate,
  ApiQueriesToggle,
  ApiQueriesRemove,
  ApiQueriesTriggerBackfill,
} from './swagger';

@ApiTags('Search Queries')
@Controller('search-queries')
export class SearchQueriesController {
  private readonly logger = new Logger(SearchQueriesController.name);

  constructor(
    private readonly service: SearchQueriesService,
    private readonly collectionJobsService: CollectionJobsService,
  ) {}

  @Get()
  @ApiQueriesFindAll()
  @ApiQuery({ name: 'queryType', required: false, enum: ['production', 'sample'], description: '쿼리 타입으로 필터링' })
  findAll(@Query() query: ListSearchQueriesQueryDto) {
    return this.service.findAll(query);
  }

  @Get('active')
  @ApiQueriesFindActive()
  findActive() {
    return this.service.findActive();
  }

  @Get('stats')
  @ApiQueriesGetStats()
  getStats() {
    return this.service.getStats();
  }

  @Post('preview')
  @ApiQueriesPreview()
  preview(@Body() dto: PreviewQueryDto) {
    return this.service.preview(dto);
  }

  @Get(':id')
  @ApiQueriesFindOne()
  findOne(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.findOne(id);
  }

  @Post()
  @ApiQueriesCreate()
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
  @ApiQueriesUpdate()
  update(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateSearchQueryDto,
  ) {
    return this.service.update(id, dto);
  }

  @Patch(':id/toggle')
  @ApiQueriesToggle()
  toggleActive(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.toggleActive(id);
  }

  @Delete(':id')
  @ApiQueriesRemove()
  remove(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.remove(id);
  }

  @Post(':id/backfill')
  @ApiQueriesTriggerBackfill()
  async triggerBackfill(@Param('id', ParseUUIDPipe) id: string) {
    // 쿼리 존재 확인
    await this.service.findOne(id);
    return this.collectionJobsService.triggerBackfill(id);
  }
}
