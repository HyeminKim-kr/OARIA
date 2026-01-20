import { IsEnum, IsNumber, IsNotEmpty } from 'class-validator';
import { Transform } from 'class-transformer';

export enum NodeEnv {
  Development = 'development',
  Production = 'production',
  Staging = 'staging',
  Test = 'test',
}

export class AppConfig {
  @IsEnum(NodeEnv, { message: 'NODE_ENV must be one of: development, production, staging, test' })
  @IsNotEmpty({ message: 'NODE_ENV is required' })
  NODE_ENV: NodeEnv;

  @Transform(({ value }) => parseInt(value, 10))
  @IsNumber({}, { message: 'PORT must be a number' })
  @IsNotEmpty({ message: 'PORT is required' })
  PORT: number;
}

export const APP_DEFAULTS = {
  NODE_ENV: NodeEnv.Development,
  PORT: 13000,
};
