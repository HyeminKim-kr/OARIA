import { IsString, IsNumber, IsNotEmpty } from 'class-validator';
import { Transform } from 'class-transformer';

export class FlowerConfig {
  @IsString()
  @IsNotEmpty({ message: 'FLOWER_HOST is required' })
  FLOWER_HOST: string;

  @Transform(({ value }) => parseInt(value, 10))
  @IsNumber({}, { message: 'FLOWER_PORT must be a number' })
  @IsNotEmpty({ message: 'FLOWER_PORT is required' })
  FLOWER_PORT: number;

  @IsString()
  @IsNotEmpty({ message: 'FLOWER_USER is required' })
  FLOWER_USER: string;

  @IsString()
  @IsNotEmpty({ message: 'FLOWER_PASSWORD is required' })
  FLOWER_PASSWORD: string;
}

export const FLOWER_DEFAULTS = {
  FLOWER_HOST: 'localhost',
  FLOWER_PORT: 15555,
  FLOWER_USER: 'admin',
  FLOWER_PASSWORD: 'flower_dev_2024',
};
