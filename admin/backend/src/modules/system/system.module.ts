import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { SystemController } from './system.controller';
import { SystemService } from './system.service';

@Module({
  imports: [
    HttpModule.register({
      timeout: 5000,
      maxRedirects: 5,
    }),
  ],
  controllers: [SystemController],
  providers: [SystemService],
  exports: [SystemService],
})
export class SystemModule {}
