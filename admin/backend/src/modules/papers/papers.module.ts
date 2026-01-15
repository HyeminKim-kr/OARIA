import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Paper } from '../../entities/paper.entity';
import { PaperAuthor } from '../../entities/paper-author.entity';
import { PaperCitation } from '../../entities/paper-citation.entity';
import { PapersController } from './papers.controller';
import { PapersService } from './papers.service';
import { JobManagerModule } from '../job-manager/job-manager.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([Paper, PaperAuthor, PaperCitation]),
    JobManagerModule,
  ],
  controllers: [PapersController],
  providers: [PapersService],
  exports: [PapersService],
})
export class PapersModule {}
