import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { CollectionJob } from '../../entities/collection-job.entity';
import { ArticleError } from '../../entities/article-error.entity';
import { CollectionJobsController } from './collection-jobs.controller';
import { CollectionJobsService } from './collection-jobs.service';

@Module({
  imports: [TypeOrmModule.forFeature([CollectionJob, ArticleError])],
  controllers: [CollectionJobsController],
  providers: [CollectionJobsService],
  exports: [CollectionJobsService],
})
export class CollectionJobsModule {}
