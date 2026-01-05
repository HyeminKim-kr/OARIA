import {
  Controller,
  Get,
  Post,
  Body,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import {
  SystemService,
  SystemHealth,
  CeleryWorkerInfo,
  CeleryQueueInfo,
  TaskTriggerResult,
} from './system.service';
import { Public } from '../auth/decorators';
import { TriggerEmbeddingDto, TriggerReembeddingDto } from './dto';
import {
  ApiSystemHealth,
  ApiSystemWorkers,
  ApiSystemQueues,
  ApiSystemTriggerEmbedding,
  ApiSystemTriggerReembedding,
} from './swagger';

@ApiTags('System')
@Controller('system')
export class SystemController {
  constructor(private readonly systemService: SystemService) {}

  @Get('health')
  @Public() // Health check는 인증 없이 접근 가능
  @ApiSystemHealth()
  async getHealth(): Promise<SystemHealth> {
    return this.systemService.getSystemHealth();
  }

  @Get('workers')
  @ApiSystemWorkers()
  async getWorkers(): Promise<{ workers: CeleryWorkerInfo[] }> {
    const workers = await this.systemService.getCeleryWorkers();
    return { workers };
  }

  @Get('queues')
  @ApiSystemQueues()
  async getQueues(): Promise<{ queues: CeleryQueueInfo[] }> {
    const queues = await this.systemService.getCeleryQueues();
    return { queues };
  }

  @Post('trigger/embedding')
  @HttpCode(HttpStatus.OK)
  @ApiSystemTriggerEmbedding()
  async triggerEmbedding(@Body() dto: TriggerEmbeddingDto): Promise<TaskTriggerResult> {
    return this.systemService.triggerEmbedding(dto.limit ?? 50);
  }

  @Post('trigger/reembedding')
  @HttpCode(HttpStatus.OK)
  @ApiSystemTriggerReembedding()
  async triggerReembedding(@Body() dto: TriggerReembeddingDto): Promise<TaskTriggerResult> {
    return this.systemService.triggerReembedding(dto.limit);
  }
}
