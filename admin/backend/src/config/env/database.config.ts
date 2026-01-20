import { IsString, IsNumber, IsNotEmpty } from 'class-validator';
import { Transform } from 'class-transformer';

export class DatabaseConfig {
  @IsString()
  @IsNotEmpty({ message: 'DB_HOST is required' })
  DB_HOST: string;

  @Transform(({ value }) => parseInt(value, 10))
  @IsNumber({}, { message: 'DB_PORT must be a number' })
  @IsNotEmpty({ message: 'DB_PORT is required' })
  DB_PORT: number;

  @IsString()
  @IsNotEmpty({ message: 'DB_USER is required' })
  DB_USER: string;

  @IsString()
  @IsNotEmpty({ message: 'DB_PASSWORD is required' })
  DB_PASSWORD: string;

  @IsString()
  @IsNotEmpty({ message: 'DB_NAME is required' })
  DB_NAME: string;
}

export const DATABASE_DEFAULTS = {
  DB_HOST: 'localhost',
  DB_PORT: 15432,
  DB_USER: 'oaria',
  DB_PASSWORD: 'oaria_dev_2024',
  DB_NAME: 'oaria',
};
