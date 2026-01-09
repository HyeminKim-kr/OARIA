import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { RAGSettings } from '../../entities';
import { CreateRAGSettingsDto, UpdateRAGSettingsDto } from './dto';

@Injectable()
export class RAGSettingsService {
  constructor(
    @InjectRepository(RAGSettings)
    private readonly ragSettingsRepository: Repository<RAGSettings>,
  ) {}

  async findAll(): Promise<RAGSettings[]> {
    return this.ragSettingsRepository.find({
      order: { isActive: 'DESC', createdAt: 'DESC' },
    });
  }

  async findOne(id: string): Promise<RAGSettings> {
    const settings = await this.ragSettingsRepository.findOne({ where: { id } });
    if (!settings) {
      throw new NotFoundException(`RAG 설정을 찾을 수 없습니다: ${id}`);
    }
    return settings;
  }

  async findActive(): Promise<RAGSettings | null> {
    return this.ragSettingsRepository.findOne({ where: { isActive: true } });
  }

  async create(dto: CreateRAGSettingsDto): Promise<RAGSettings> {
    // Check for duplicate name
    const existing = await this.ragSettingsRepository.findOne({
      where: { name: dto.name },
    });
    if (existing) {
      throw new ConflictException(`이미 존재하는 설정 이름입니다: ${dto.name}`);
    }

    const settings = this.ragSettingsRepository.create({
      ...dto,
      isActive: false, // New settings are not active by default
    });
    return this.ragSettingsRepository.save(settings);
  }

  async update(id: string, dto: UpdateRAGSettingsDto): Promise<RAGSettings> {
    const settings = await this.findOne(id);

    // Check for duplicate name if name is being changed
    if (dto.name && dto.name !== settings.name) {
      const existing = await this.ragSettingsRepository.findOne({
        where: { name: dto.name },
      });
      if (existing) {
        throw new ConflictException(`이미 존재하는 설정 이름입니다: ${dto.name}`);
      }
    }

    // If activating this setting, deactivate others
    if (dto.isActive === true && !settings.isActive) {
      await this.ragSettingsRepository.update(
        { isActive: true },
        { isActive: false },
      );
    }

    Object.assign(settings, dto);
    return this.ragSettingsRepository.save(settings);
  }

  async activate(id: string): Promise<RAGSettings> {
    const settings = await this.findOne(id);

    // Deactivate all other settings
    await this.ragSettingsRepository.update(
      { isActive: true },
      { isActive: false },
    );

    // Activate this setting
    settings.isActive = true;
    return this.ragSettingsRepository.save(settings);
  }

  async delete(id: string): Promise<void> {
    const settings = await this.findOne(id);

    if (settings.isActive) {
      throw new ConflictException('활성화된 설정은 삭제할 수 없습니다');
    }

    await this.ragSettingsRepository.delete(id);
  }
}
