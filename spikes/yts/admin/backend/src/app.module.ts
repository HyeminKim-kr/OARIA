import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ScheduleModule } from '@nestjs/schedule';
import { SearchQueriesModule } from './modules/search-queries/search-queries.module';
import { CollectionJobsModule } from './modules/collection-jobs/collection-jobs.module';
import { PapersModule } from './modules/papers/papers.module';
import { SchedulerModule } from './modules/scheduler/scheduler.module';

@Module({
  imports: [
    // Config
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
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

    // Feature Modules
    SearchQueriesModule,
    CollectionJobsModule,
    PapersModule,
    SchedulerModule,
  ],
})
export class AppModule {}
