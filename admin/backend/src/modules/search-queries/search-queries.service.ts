import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { HttpService } from '@nestjs/axios';
import { Repository } from 'typeorm';
import { firstValueFrom } from 'rxjs';
import { AxiosResponse } from 'axios';
import { SearchQuery } from '../../entities/search-query.entity';
import { CreateSearchQueryDto, UpdateSearchQueryDto, PreviewQueryDto } from './dto';

interface EuropePmcResponse {
  hitCount: number;
  resultList?: {
    result: unknown[];
  };
}

const EUROPE_PMC_API = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search';

@Injectable()
export class SearchQueriesService {
  constructor(
    @InjectRepository(SearchQuery)
    private readonly repository: Repository<SearchQuery>,
    private readonly httpService: HttpService,
  ) {}

  async findAll(): Promise<SearchQuery[]> {
    return this.repository.find({
      order: { priority: 'ASC', createdAt: 'DESC' },
    });
  }

  async findActive(): Promise<SearchQuery[]> {
    return this.repository.find({
      where: { isActive: true },
      order: { priority: 'ASC' },
    });
  }

  async findOne(id: string): Promise<SearchQuery> {
    const query = await this.repository.findOne({
      where: { id },
      relations: ['jobs'],
    });
    if (!query) {
      throw new NotFoundException(`SearchQuery #${id} not found`);
    }
    return query;
  }

  async create(dto: CreateSearchQueryDto): Promise<SearchQuery> {
    const entity = this.repository.create(dto);
    return this.repository.save(entity);
  }

  async update(id: string, dto: UpdateSearchQueryDto): Promise<SearchQuery> {
    const entity = await this.findOne(id);
    Object.assign(entity, dto);
    return this.repository.save(entity);
  }

  async toggleActive(id: string): Promise<SearchQuery> {
    const entity = await this.findOne(id);
    entity.isActive = !entity.isActive;
    return this.repository.save(entity);
  }

  async remove(id: string): Promise<void> {
    const entity = await this.findOne(id);
    await this.repository.remove(entity);
  }

  async getStats(): Promise<{
    total: number;
    active: number;
    totalCollected: number;
  }> {
    const [total, active, stats] = await Promise.all([
      this.repository.count(),
      this.repository.count({ where: { isActive: true } }),
      this.repository
        .createQueryBuilder('sq')
        .select('SUM(sq.total_collected)', 'totalCollected')
        .getRawOne(),
    ]);

    return {
      total,
      active,
      totalCollected: parseInt(stats?.totalCollected || '0', 10),
    };
  }

  async preview(dto: PreviewQueryDto): Promise<{ hitCount: number; fullQuery: string }> {
    // Europe PMC 검색 쿼리 구성
    let fullQuery = dto.query;

    // OA 필터
    if (dto.openAccessOnly !== false) {
      fullQuery += ' AND OPEN_ACCESS:Y';
    }

    // 연도 필터
    if (dto.yearFrom || dto.yearTo) {
      const yFrom = dto.yearFrom || 1900;
      const yTo = dto.yearTo || 2099;
      fullQuery += ` AND FIRST_PDATE:[${yFrom} TO ${yTo}]`;
    }

    // Europe PMC API 호출 (pageSize=1, 총 개수만 확인)
    const response = await firstValueFrom(
      this.httpService.get<EuropePmcResponse>(EUROPE_PMC_API, {
        params: {
          query: fullQuery,
          format: 'json',
          pageSize: 1,
        },
      }),
    );

    const hitCount = response.data.hitCount || 0;

    return {
      hitCount,
      fullQuery,
    };
  }
}
