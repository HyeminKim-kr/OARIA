import {
  Controller,
  Get,
  Post,
  Patch,
  Param,
  Query,
  ParseUUIDPipe,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { CollectionJobsService } from './collection-jobs.service';
import { CollectionJob } from '../../entities/collection-job.entity';
import { ArticleError } from '../../entities/article-error.entity';
import { JobStats, JobErrorStats, TaskTriggerResult } from './types';
import { FindAllJobsQueryDto, GetJobErrorsQueryDto } from './dto';
import {
  ApiJobsFindAll,
  ApiJobsGetRunning,
  ApiJobsGetStats,
  ApiJobsFindOne,
  ApiJobsCancel,
  ApiJobsRetry,
  ApiJobsResume,
  ApiJobsGetErrors,
  ApiJobsGetErrorStats,
} from './swagger';

@ApiTags('Collection Jobs')
@Controller('collection-jobs')
export class CollectionJobsController {
  constructor(private readonly service: CollectionJobsService) {}

  @Get()
  @ApiJobsFindAll()
  findAll(@Query() query: FindAllJobsQueryDto): Promise<CollectionJob[]> {
    return this.service.findAll({
      status: query.status,
      jobType: query.jobType,
      limit: query.limit ?? 50,
    });
  }

  @Get('running')
  @ApiJobsGetRunning()
  getRunningJobs(): Promise<CollectionJob[]> {
    return this.service.getRunningJobs();
  }

  @Get('stats')
  @ApiJobsGetStats()
  getStats(): Promise<JobStats> {
    return this.service.getStats();
  }

  @Get(':id')
  @ApiJobsFindOne()
  findOne(@Param('id', ParseUUIDPipe) id: string): Promise<CollectionJob> {
    return this.service.findOne(id);
  }

  @Patch(':id/cancel')
  @ApiJobsCancel()
  cancelJob(@Param('id', ParseUUIDPipe) id: string): Promise<CollectionJob> {
    return this.service.cancelJob(id);
  }

  @Post(':id/retry')
  @ApiJobsRetry()
  retryJob(@Param('id', ParseUUIDPipe) id: string): Promise<TaskTriggerResult> {
    return this.service.retryJob(id);
  }

  @Post(':id/resume')
  @ApiJobsResume()
  resumeJob(@Param('id', ParseUUIDPipe) id: string): Promise<TaskTriggerResult> {
    return this.service.resumeJob(id);
  }

  // ============================================================
  // Article Errors
  // ============================================================

  @Get(':id/errors')
  @ApiJobsGetErrors()
  getJobErrors(
    @Param('id', ParseUUIDPipe) id: string,
    @Query() query: GetJobErrorsQueryDto,
  ): Promise<{ errors: ArticleError[]; total: number }> {
    return this.service.getJobErrors(id, {
      stage: query.stage,
      limit: query.limit ?? 100,
      offset: query.offset ?? 0,
    });
  }

  @Get(':id/errors/stats')
  @ApiJobsGetErrorStats()
  getJobErrorStats(@Param('id', ParseUUIDPipe) id: string): Promise<JobErrorStats> {
    return this.service.getJobErrorStats(id);
  }
}
