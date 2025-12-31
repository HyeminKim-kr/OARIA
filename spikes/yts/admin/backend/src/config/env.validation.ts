import { plainToInstance, Transform } from 'class-transformer';
import {
  IsString,
  IsNumber,
  IsOptional,
  IsEnum,
  validateSync,
  IsNotEmpty,
  ValidateIf,
} from 'class-validator';

/**
 * 환경 타입
 */
export enum NodeEnv {
  Development = 'development',
  Production = 'production',
  Staging = 'staging',
  Test = 'test',
}

/**
 * 로컬 환경인지 확인
 */
function isLocalEnvironment(nodeEnv: string | undefined): boolean {
  return !nodeEnv || nodeEnv === NodeEnv.Development || nodeEnv === NodeEnv.Test;
}

/**
 * 환경변수 검증 스키마
 *
 * - development/test: 디폴트 값 사용 가능
 * - production/staging: 모든 필수 값 명시 필요
 */
export class EnvironmentVariables {
  // ─────────────────────────────────────────────────────────────
  // App
  // ─────────────────────────────────────────────────────────────

  @IsEnum(NodeEnv)
  @IsOptional()
  NODE_ENV: NodeEnv = NodeEnv.Development;

  @Transform(({ value }) => parseInt(value, 10))
  @IsNumber()
  @IsOptional()
  PORT: number = 13000;

  // ─────────────────────────────────────────────────────────────
  // Database - 프로덕션에서 필수
  // ─────────────────────────────────────────────────────────────

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'DB_HOST is required in production/staging' })
  DB_HOST?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @Transform(({ value }) => (value ? parseInt(value, 10) : undefined))
  @IsNumber({}, { message: 'DB_PORT must be a number' })
  DB_PORT?: number;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'DB_USER is required in production/staging' })
  DB_USER?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'DB_PASSWORD is required in production/staging' })
  DB_PASSWORD?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'DB_NAME is required in production/staging' })
  DB_NAME?: string;

  // ─────────────────────────────────────────────────────────────
  // Redis - 프로덕션에서 필수
  // ─────────────────────────────────────────────────────────────

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'REDIS_HOST is required in production/staging' })
  REDIS_HOST?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @Transform(({ value }) => (value ? parseInt(value, 10) : undefined))
  @IsNumber({}, { message: 'REDIS_PORT must be a number' })
  REDIS_PORT?: number;

  // ─────────────────────────────────────────────────────────────
  // S3/MinIO - 프로덕션에서 필수
  // ─────────────────────────────────────────────────────────────

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'S3_ENDPOINT is required in production/staging' })
  S3_ENDPOINT?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'S3_ACCESS_KEY is required in production/staging' })
  S3_ACCESS_KEY?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'S3_SECRET_KEY is required in production/staging' })
  S3_SECRET_KEY?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'S3_BUCKET is required in production/staging' })
  S3_BUCKET?: string;

  // ─────────────────────────────────────────────────────────────
  // Auth - JWT (모든 환경에서 필수)
  // ─────────────────────────────────────────────────────────────

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'JWT_SECRET is required in production/staging' })
  JWT_SECRET?: string;

  @IsString()
  @IsOptional()
  JWT_ACCESS_EXPIRES?: string;

  @IsString()
  @IsOptional()
  JWT_REFRESH_EXPIRES_DAYS?: string;

  // ─────────────────────────────────────────────────────────────
  // Auth - Google OAuth (프로덕션에서 필수)
  // ─────────────────────────────────────────────────────────────

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'GOOGLE_CLIENT_ID is required in production/staging' })
  GOOGLE_CLIENT_ID?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'GOOGLE_CLIENT_SECRET is required in production/staging' })
  GOOGLE_CLIENT_SECRET?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'GOOGLE_CALLBACK_URL is required in production/staging' })
  GOOGLE_CALLBACK_URL?: string;

  @IsString()
  @IsOptional()
  SUPER_ADMIN_EMAIL?: string;

  // ─────────────────────────────────────────────────────────────
  // Frontend URL - 프로덕션에서 필수
  // ─────────────────────────────────────────────────────────────

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'ADMIN_FRONTEND_URL is required in production/staging' })
  ADMIN_FRONTEND_URL?: string;

  // ─────────────────────────────────────────────────────────────
  // Weaviate - 프로덕션에서 필수
  // ─────────────────────────────────────────────────────────────

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'WEAVIATE_HOST is required in production/staging' })
  WEAVIATE_HOST?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @Transform(({ value }) => (value ? parseInt(value, 10) : undefined))
  @IsNumber({}, { message: 'WEAVIATE_PORT must be a number' })
  WEAVIATE_PORT?: number;

  // ─────────────────────────────────────────────────────────────
  // Flower (Celery Monitoring) - 프로덕션에서 필수
  // ─────────────────────────────────────────────────────────────

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'FLOWER_HOST is required in production/staging' })
  FLOWER_HOST?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @Transform(({ value }) => (value ? parseInt(value, 10) : undefined))
  @IsNumber({}, { message: 'FLOWER_PORT must be a number' })
  FLOWER_PORT?: number;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'FLOWER_USER is required in production/staging' })
  FLOWER_USER?: string;

  @ValidateIf((o) => !isLocalEnvironment(o.NODE_ENV))
  @IsString()
  @IsNotEmpty({ message: 'FLOWER_PASSWORD is required in production/staging' })
  FLOWER_PASSWORD?: string;
}

/**
 * 환경변수 검증 함수
 *
 * ConfigModule.forRoot({ validate }) 에 전달
 */
export function validate(config: Record<string, unknown>): EnvironmentVariables {
  const validatedConfig = plainToInstance(EnvironmentVariables, config, {
    enableImplicitConversion: true,
  });

  const errors = validateSync(validatedConfig, {
    skipMissingProperties: false,
  });

  if (errors.length > 0) {
    const nodeEnv = config.NODE_ENV || 'development';
    const errorMessages = errors
      .map((error) => {
        const constraints = error.constraints
          ? Object.values(error.constraints).join(', ')
          : 'validation failed';
        return `  - ${error.property}: ${constraints}`;
      })
      .join('\n');

    throw new Error(
      `\n` +
        `========================================\n` +
        `  Environment Validation Failed\n` +
        `========================================\n` +
        `\n` +
        `NODE_ENV: ${nodeEnv}\n` +
        `\n` +
        `Missing or invalid environment variables:\n` +
        `${errorMessages}\n` +
        `\n` +
        `Please check your .env file or environment configuration.\n` +
        `========================================\n`,
    );
  }

  return validatedConfig;
}
