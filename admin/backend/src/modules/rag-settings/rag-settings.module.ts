import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { RAGSettings } from '../../entities';
import { RAGSettingsController } from './rag-settings.controller';
import { RAGSettingsService } from './rag-settings.service';

@Module({
  imports: [TypeOrmModule.forFeature([RAGSettings])],
  controllers: [RAGSettingsController],
  providers: [RAGSettingsService],
  exports: [RAGSettingsService],
})
export class RAGSettingsModule {}
