import {
  Controller,
  Get,
  Post,
  Patch,
  Param,
  Query,
  ParseUUIDPipe,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery } from '@nestjs/swagger';
import { CollectionJobsService } from './collection-jobs.service';
import { JobStatus, JobType } from '../../entities/collection-job.entity';
import { ErrorStage } from '../../entities/article-error.entity';

@ApiTags('Collection Jobs')
@Controller('collection-jobs')
export class CollectionJobsController {
  constructor(private readonly service: CollectionJobsService) {}

  @Get()
  @ApiOperation({ summary: '배치 작업 목록' })
  @ApiQuery({ name: 'status', required: false, enum: ['pending', 'running', 'completed', 'failed', 'delayed', 'cancelled'] })
  @ApiQuery({ name: 'jobType', required: false, enum: ['backfill', 'incremental', 'repair'] })
  @ApiQuery({ name: 'limit', required: false, type: Number })
  findAll(
    @Query('status') status?: JobStatus,
    @Query('jobType') jobType?: JobType,
    @Query('limit') limit?: number,
  ) {
    return this.service.findAll({ status, jobType, limit: limit ? +limit : 50 });
  }

  @Get('running')
  @ApiOperation({ summary: '실행 중인 작업' })
  getRunningJobs() {
    return this.service.getRunningJobs();
  }

  @Get('stats')
  @ApiOperation({ summary: '배치 작업 통계' })
  getStats() {
    return this.service.getStats();
  }

  @Get(':id')
  @ApiOperation({ summary: '배치 작업 상세' })
  findOne(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.findOne(id);
  }

  @Patch(':id/cancel')
  @ApiOperation({ summary: '작업 취소' })
  cancelJob(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.cancelJob(id);
  }

  @Post(':id/retry')
  @ApiOperation({ summary: 'Failed job 재시도 (새 Job 생성)' })
  retryJob(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.retryJob(id);
  }

  @Post(':id/resume')
  @ApiOperation({ summary: 'Partial/Failed job 재개 (기존 Job 이어서)' })
  resumeJob(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.resumeJob(id);
  }

  // ============================================================
  // Article Errors
  // ============================================================

  @Get(':id/errors')
  @ApiOperation({ summary: 'Job 에러 목록' })
  @ApiQuery({ name: 'stage', required: false, enum: ['search', 'download', 'parse', 'save'] })
  @ApiQuery({ name: 'limit', required: false, type: Number })
  @ApiQuery({ name: 'offset', required: false, type: Number })
  getJobErrors(
    @Param('id', ParseUUIDPipe) id: string,
    @Query('stage') stage?: ErrorStage,
    @Query('limit') limit?: number,
    @Query('offset') offset?: number,
  ) {
    return this.service.getJobErrors(id, {
      stage,
      limit: limit ? +limit : 100,
      offset: offset ? +offset : 0,
    });
  }

  @Get(':id/errors/stats')
  @ApiOperation({ summary: 'Job 에러 통계' })
  getJobErrorStats(@Param('id', ParseUUIDPipe) id: string) {
    return this.service.getJobErrorStats(id);
  }
}
