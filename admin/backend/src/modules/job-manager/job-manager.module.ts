import { Module } from '@nestjs/common';
import { RedisModule } from '../redis/redis.module';
import { JobManagerService } from './job-manager.service';

@Module({
  imports: [RedisModule],
  providers: [JobManagerService],
  exports: [JobManagerService],
})
export class JobManagerModule {}
