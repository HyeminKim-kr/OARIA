import { NestFactory } from '@nestjs/core';
import { ValidationPipe, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const configService = app.get(ConfigService);
  const logger = new Logger('Bootstrap');

  const nodeEnv = configService.get<string>('NODE_ENV', 'development');
  const isProduction = nodeEnv === 'production';

  // CORS
  const frontendUrl = configService.get<string>('ADMIN_FRONTEND_URL', 'http://localhost:13001');
  app.enableCors({
    origin: [frontendUrl, 'http://localhost:3000'],
    credentials: true,
  });

  // Validation
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    }),
  );

  // Swagger - 프로덕션 환경에서는 비활성화
  if (!isProduction) {
    const config = new DocumentBuilder()
      .setTitle('OARIA Admin API')
      .setDescription('암 논문 수집 서비스 어드민 API')
      .setVersion('1.0')
      .addBearerAuth(
        {
          type: 'http',
          scheme: 'bearer',
          bearerFormat: 'JWT',
          name: 'Authorization',
          description: 'JWT Access Token 입력',
          in: 'header',
        },
        'access-token',
      )
      .addTag('Auth', '인증 관련 API')
      .addTag('Admin Users', '관리자 계정 관리')
      .addTag('Papers', '논문 관리')
      .addTag('Search Queries', '검색 쿼리 관리')
      .addTag('Collection Jobs', '수집 작업 관리')
      .addTag('System', '시스템 모니터링')
      .build();

    const document = SwaggerModule.createDocument(app, config);
    SwaggerModule.setup('api', app, document, {
      swaggerOptions: {
        persistAuthorization: true,
        tagsSorter: 'alpha',
        operationsSorter: 'alpha',
      },
    });

    logger.log('Swagger UI enabled at /api');
  } else {
    logger.log('Swagger UI disabled in production');
  }

  const port = configService.get<number>('PORT', 13000);
  await app.listen(port);

  logger.log(`Admin API running on http://localhost:${port}`);
  if (!isProduction) {
    logger.log(`Swagger UI: http://localhost:${port}/api`);
  }
}

bootstrap();
