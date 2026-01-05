import { IsString, IsNumber, IsNotEmpty } from 'class-validator';
import { Transform } from 'class-transformer';

export class RedisConfig {
  @IsString()
  @IsNotEmpty({ message: 'REDIS_HOST is required' })
  REDIS_HOST: string;

  @Transform(({ value }) => parseInt(value, 10))
  @IsNumber({}, { message: 'REDIS_PORT must be a number' })
  @IsNotEmpty({ message: 'REDIS_PORT is required' })
  REDIS_PORT: number;
}

export const REDIS_DEFAULTS = {
  REDIS_HOST: 'localhost',
  REDIS_PORT: 16379,
};
