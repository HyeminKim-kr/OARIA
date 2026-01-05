import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ScheduleModule } from '@nestjs/schedule';
import { APP_GUARD } from '@nestjs/core';
import { SearchQueriesModule } from './modules/search-queries/search-queries.module';
import { CollectionJobsModule } from './modules/collection-jobs/collection-jobs.module';
import { PapersModule } from './modules/papers/papers.module';
import { SchedulerModule } from './modules/scheduler/scheduler.module';
import { AuthModule } from './modules/auth/auth.module';
import { AdminUsersModule } from './modules/admin-users/admin-users.module';
import { SystemModule } from './modules/system/system.module';
import { JwtAuthGuard } from './modules/auth/guards';
import { RolesGuard } from './modules/auth/guards';
import { validate } from './config';

@Module({
  imports: [
    // Config - 환경변수 검증 포함
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
      validate,
    }),

    // Schedule
    ScheduleModule.forRoot(),

    // TypeORM
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        type: 'postgres',
        host: configService.get('DB_HOST', 'localhost'),
        port: configService.get('DB_PORT', 15432),
        username: configService.get('DB_USER', 'oaria'),
        password: configService.get('DB_PASSWORD', 'oaria_dev_2024'),
        database: configService.get('DB_NAME', 'oaria'),
        entities: [__dirname + '/entities/*.entity{.ts,.js}'],
        synchronize: false, // 기존 스키마 사용
        logging: configService.get('NODE_ENV') === 'development',
      }),
    }),

    // Auth
    AuthModule,
    AdminUsersModule,

    // Feature Modules
    SearchQueriesModule,
    CollectionJobsModule,
    PapersModule,
    SchedulerModule,

    // System Monitoring
    SystemModule,
  ],
  providers: [
    // Global JWT Guard - 모든 엔드포인트에 적용
    {
      provide: APP_GUARD,
      useClass: JwtAuthGuard,
    },
    // Global Roles Guard
    {
      provide: APP_GUARD,
      useClass: RolesGuard,
    },
  ],
})
export class AppModule {}
