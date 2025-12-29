import {
  Controller,
  Get,
  Param,
  Query,
  ParseUUIDPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery } from '@nestjs/swagger';
import { PapersService } from './papers.service';
import { PaperStatus } from '../../entities/paper.entity';

@ApiTags('Papers')
@Controller('papers')
export class PapersController {
  constructor(private readonly service: PapersService) {}

  @Get()
  @ApiOperation({ summary: '논문 목록' })
  @ApiQuery({ name: 'search', required: false })
  @ApiQuery({ name: 'status', required: false, enum: ['collected', 'chunked', 'indexed'] })
  @ApiQuery({ name: 'yearFrom', required: false, type: Number })
  @ApiQuery({ name: 'yearTo', required: false, type: Number })
  @ApiQuery({ name: 'page', required: false, type: Number })
  @ApiQuery({ name: 'limit', required: false, type: Number })
  findAll(
    @Query('search') search?: string,
    @Query('status') status?: PaperStatus,
    @Query('yearFrom') yearFrom?: string,
    @Query('yearTo') yearTo?: string,
    @Query('page') page?: string,
    @Query('limit') limit?: string,
  ) {
    return this.service.findAll({
      search,
      status,
      yearFrom: yearFrom ? +yearFrom : undefined,
      yearTo: yearTo ? +yearTo : undefined,
      page: page ? +page : 1,
      limit: limit ? +limit : 20,
    });
  }

  @Get('stats')
  @ApiOperation({ summary: '논문 통계' })
  getStats() {
    return this.service.getStats();
  }

  @Get('recent')
  @ApiOperation({ summary: '최근 수집된 논문' })
  @ApiQuery({ name: 'limit', required: false, type: Number })
  getRecent(@Query('limit') limit?: string) {
    return this.service.getRecentPapers(limit ? +limit : 10);
  }

  @Get(':id/fulltext')
  @ApiOperation({ summary: '논문 전문 조회' })
  getFulltext(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.getFulltext(id);
  }

  @Get(':id')
  @ApiOperation({ summary: '논문 상세' })
  findOne(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.findOne(id);
  }
}
