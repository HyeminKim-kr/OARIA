import { Module, Global, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

export const REDIS_CLIENT = 'REDIS_CLIENT';

@Global()
@Module({
  providers: [
    {
      provide: REDIS_CLIENT,
      useFactory: (configService: ConfigService) => {
        const redis = new Redis({
          host: configService.get('REDIS_HOST', 'localhost'),
          port: configService.get('REDIS_PORT', 16379),
          db: 0,
          lazyConnect: true,
          maxRetriesPerRequest: 3,
          retryStrategy: (times) => {
            if (times > 3) {
              return null; // 연결 재시도 중단
            }
            return Math.min(times * 200, 2000);
          },
        });

        redis.on('connect', () => {
          console.log('[Redis] Connected to Redis server');
        });

        redis.on('error', (error) => {
          console.error('[Redis] Connection error:', error.message);
        });

        return redis;
      },
      inject: [ConfigService],
    },
  ],
  exports: [REDIS_CLIENT],
})
export class RedisModule implements OnModuleDestroy {
  constructor(private readonly configService: ConfigService) {}

  async onModuleDestroy() {
    // Redis 연결 정리는 앱 종료 시 자동으로 처리됨
    console.log('[Redis] Module destroyed');
  }
}
