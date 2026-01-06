import { plainToInstance } from 'class-transformer';
import { validateSync } from 'class-validator';

import {
  NodeEnv,
  AppConfig,
  APP_DEFAULTS,
  DatabaseConfig,
  DATABASE_DEFAULTS,
  RedisConfig,
  REDIS_DEFAULTS,
  S3Config,
  S3_DEFAULTS,
  AuthConfig,
  AUTH_DEFAULTS,
  WeaviateConfig,
  WEAVIATE_DEFAULTS,
  FlowerConfig,
  FLOWER_DEFAULTS,
  UserBackendConfig,
  USER_BACKEND_DEFAULTS,
} from './env';

/**
 * 로컬 환경인지 확인
 */
function isLocalEnvironment(nodeEnv: string | undefined): boolean {
  return !nodeEnv || nodeEnv === NodeEnv.Development || nodeEnv === NodeEnv.Test;
}

/**
 * 로컬 환경 디폴트 값 (중앙 관리)
 */
const LOCAL_DEFAULTS: Record<string, string | number> = {
  ...APP_DEFAULTS,
  ...DATABASE_DEFAULTS,
  ...REDIS_DEFAULTS,
  ...S3_DEFAULTS,
  ...AUTH_DEFAULTS,
  ...WEAVIATE_DEFAULTS,
  ...FLOWER_DEFAULTS,
  ...USER_BACKEND_DEFAULTS,
};

/**
 * 환경변수 검증 스키마
 * - 모든 필드 필수 (IsOptional 사용 안함)
 * - 로컬 환경: LOCAL_DEFAULTS 적용 후 검증
 * - 프로덕션/스테이징: 디폴트 없이 검증 (누락 시 에러)
 */
export class EnvironmentVariables
  implements AppConfig, DatabaseConfig, RedisConfig, S3Config, AuthConfig, WeaviateConfig, FlowerConfig, UserBackendConfig
{
  // App
  NODE_ENV: NodeEnv;
  PORT: number;

  // Database
  DB_HOST: string;
  DB_PORT: number;
  DB_USER: string;
  DB_PASSWORD: string;
  DB_NAME: string;

  // Redis
  REDIS_HOST: string;
  REDIS_PORT: number;

  // S3
  S3_ENDPOINT: string;
  S3_ACCESS_KEY: string;
  S3_SECRET_KEY: string;
  S3_BUCKET: string;

  // Auth
  JWT_SECRET: string;
  JWT_ACCESS_EXPIRES: string;
  JWT_REFRESH_EXPIRES_DAYS: string;
  GOOGLE_CLIENT_ID: string;
  GOOGLE_CLIENT_SECRET: string;
  GOOGLE_CALLBACK_URL: string;
  SUPER_ADMIN_EMAIL: string;
  ADMIN_FRONTEND_URL: string;

  // Weaviate
  WEAVIATE_HOST: string;
  WEAVIATE_PORT: number;

  // Flower
  FLOWER_HOST: string;
  FLOWER_PORT: number;
  FLOWER_USER: string;
  FLOWER_PASSWORD: string;

  // User Backend
  USER_BACKEND_URL: string;
}

/**
 * 로컬 환경에서 디폴트 값 적용
 */
function applyLocalDefaults(config: Record<string, unknown>): Record<string, unknown> {
  const nodeEnv = config.NODE_ENV as string | undefined;

  // 프로덕션/스테이징에서는 디폴트 적용 안함
  if (!isLocalEnvironment(nodeEnv)) {
    return config;
  }

  // 로컬 환경: 디폴트 값 적용 (사용자 값이 우선)
  const merged: Record<string, unknown> = { ...LOCAL_DEFAULTS };

  for (const [key, value] of Object.entries(config)) {
    if (value !== undefined && value !== '') {
      merged[key] = value;
    }
  }

  return merged;
}

/**
 * 개별 Config 클래스 검증
 */
function validateConfig<T extends object>(
  ConfigClass: new () => T,
  config: Record<string, unknown>,
): string[] {
  const instance = plainToInstance(ConfigClass, config, {
    enableImplicitConversion: true,
  });

  const errors = validateSync(instance, {
    skipMissingProperties: false,
  });

  return errors.flatMap((error) => {
    const constraints = error.constraints ? Object.values(error.constraints) : ['validation failed'];
    return constraints.map((c) => `  - ${error.property}: ${c}`);
  });
}

/**
 * 환경변수 검증 함수
 * ConfigModule.forRoot({ validate }) 에 전달
 */
export function validate(config: Record<string, unknown>): EnvironmentVariables {
  // 1. 로컬 환경이면 디폴트 적용
  const configWithDefaults = applyLocalDefaults(config);

  // 2. 각 Config 클래스별 검증
  const allErrors: string[] = [
    ...validateConfig(AppConfig, configWithDefaults),
    ...validateConfig(DatabaseConfig, configWithDefaults),
    ...validateConfig(RedisConfig, configWithDefaults),
    ...validateConfig(S3Config, configWithDefaults),
    ...validateConfig(AuthConfig, configWithDefaults),
    ...validateConfig(WeaviateConfig, configWithDefaults),
    ...validateConfig(FlowerConfig, configWithDefaults),
    ...validateConfig(UserBackendConfig, configWithDefaults),
  ];

  // 3. 에러가 있으면 throw
  if (allErrors.length > 0) {
    const nodeEnv = configWithDefaults.NODE_ENV || 'unknown';
    const isLocal = isLocalEnvironment(nodeEnv as string);

    const hint = isLocal
      ? 'Check LOCAL_DEFAULTS in env/*.config.ts or your .env file.'
      : 'All environment variables must be explicitly set in production/staging.';

    throw new Error(
      `\n` +
        `========================================\n` +
        `  Environment Validation Failed\n` +
        `========================================\n` +
        `\n` +
        `NODE_ENV: ${nodeEnv}\n` +
        `\n` +
        `Missing or invalid environment variables:\n` +
        `${allErrors.join('\n')}\n` +
        `\n` +
        `${hint}\n` +
        `========================================\n`,
    );
  }

  // 4. 검증된 설정 반환
  return plainToInstance(EnvironmentVariables, configWithDefaults, {
    enableImplicitConversion: true,
  });
}

// Re-export
export { NodeEnv };
