import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Paper } from '../../entities/paper.entity';
import { PaperAuthor } from '../../entities/paper-author.entity';
import { PapersController } from './papers.controller';
import { PapersService } from './papers.service';

@Module({
  imports: [TypeOrmModule.forFeature([Paper, PaperAuthor])],
  controllers: [PapersController],
  providers: [PapersService],
  exports: [PapersService],
})
export class PapersModule {}
