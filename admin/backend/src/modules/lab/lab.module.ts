import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { TypeOrmModule } from '@nestjs/typeorm';
import { LabController } from './lab.controller';
import { LabService } from './lab.service';
import { LabFeedback, LabTestLog } from '../../entities';

@Module({
  imports: [
    HttpModule.register({
      timeout: 60000, // 60초 (LLM 생성 시간 고려)
      maxRedirects: 5,
    }),
    TypeOrmModule.forFeature([LabFeedback, LabTestLog]),
  ],
  controllers: [LabController],
  providers: [LabService],
  exports: [LabService],
})
export class LabModule {}
