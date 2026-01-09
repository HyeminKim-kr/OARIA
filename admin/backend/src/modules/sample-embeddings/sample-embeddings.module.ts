import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { SampleEmbedding, SearchQuery } from '../../entities';
import { SampleEmbeddingsController } from './sample-embeddings.controller';
import { SampleEmbeddingsService } from './sample-embeddings.service';

@Module({
  imports: [TypeOrmModule.forFeature([SampleEmbedding, SearchQuery])],
  controllers: [SampleEmbeddingsController],
  providers: [SampleEmbeddingsService],
  exports: [SampleEmbeddingsService],
})
export class SampleEmbeddingsModule {}
