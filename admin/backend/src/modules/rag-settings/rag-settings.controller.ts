import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Param,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { RAGSettingsService } from './rag-settings.service';
import { CreateRAGSettingsDto, UpdateRAGSettingsDto } from './dto';
import { RAGSettings } from '../../entities';

@ApiTags('RAG Settings')
@Controller('rag-settings')
export class RAGSettingsController {
  constructor(private readonly ragSettingsService: RAGSettingsService) {}

  @Get()
  @ApiOperation({ summary: '모든 RAG 설정 조회' })
  @ApiResponse({ status: 200, description: 'RAG 설정 목록' })
  async findAll(): Promise<RAGSettings[]> {
    return this.ragSettingsService.findAll();
  }

  @Get('active')
  @ApiOperation({ summary: '활성화된 RAG 설정 조회' })
  @ApiResponse({ status: 200, description: '활성 RAG 설정' })
  async findActive(): Promise<RAGSettings | null> {
    return this.ragSettingsService.findActive();
  }

  @Get(':id')
  @ApiOperation({ summary: 'RAG 설정 상세 조회' })
  @ApiResponse({ status: 200, description: 'RAG 설정 상세' })
  async findOne(@Param('id') id: string): Promise<RAGSettings> {
    return this.ragSettingsService.findOne(id);
  }

  @Post()
  @ApiOperation({ summary: '새 RAG 설정 생성' })
  @ApiResponse({ status: 201, description: '생성된 RAG 설정' })
  async create(@Body() dto: CreateRAGSettingsDto): Promise<RAGSettings> {
    return this.ragSettingsService.create(dto);
  }

  @Put(':id')
  @ApiOperation({ summary: 'RAG 설정 수정' })
  @ApiResponse({ status: 200, description: '수정된 RAG 설정' })
  async update(
    @Param('id') id: string,
    @Body() dto: UpdateRAGSettingsDto,
  ): Promise<RAGSettings> {
    return this.ragSettingsService.update(id, dto);
  }

  @Post(':id/activate')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'RAG 설정 활성화 (적용)' })
  @ApiResponse({ status: 200, description: '활성화된 RAG 설정' })
  async activate(@Param('id') id: string): Promise<RAGSettings> {
    return this.ragSettingsService.activate(id);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'RAG 설정 삭제' })
  @ApiResponse({ status: 204, description: '삭제 완료' })
  async delete(@Param('id') id: string): Promise<void> {
    return this.ragSettingsService.delete(id);
  }
}
