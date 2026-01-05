import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { HttpModule } from '@nestjs/axios';
import { SearchQuery } from '../../entities/search-query.entity';
import { SearchQueriesController } from './search-queries.controller';
import { SearchQueriesService } from './search-queries.service';
import { CollectionJobsModule } from '../collection-jobs/collection-jobs.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([SearchQuery]),
    CollectionJobsModule,
    HttpModule.register({
      timeout: 10000,
      maxRedirects: 3,
    }),
  ],
  controllers: [SearchQueriesController],
  providers: [SearchQueriesService],
  exports: [SearchQueriesService],
})
export class SearchQueriesModule {}
