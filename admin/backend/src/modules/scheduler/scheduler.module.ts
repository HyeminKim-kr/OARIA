import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { CollectionJob } from '../../entities/collection-job.entity';
import { CollectionJobsModule } from '../collection-jobs/collection-jobs.module';
import { SchedulerService } from './scheduler.service';

@Module({
  imports: [
    TypeOrmModule.forFeature([CollectionJob]),
    CollectionJobsModule,
  ],
  providers: [SchedulerService],
  exports: [SchedulerService],
})
export class SchedulerModule {}
