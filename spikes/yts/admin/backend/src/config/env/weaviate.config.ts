import { IsString, IsNumber, IsNotEmpty } from 'class-validator';
import { Transform } from 'class-transformer';

export class WeaviateConfig {
  @IsString()
  @IsNotEmpty({ message: 'WEAVIATE_HOST is required' })
  WEAVIATE_HOST: string;

  @Transform(({ value }) => parseInt(value, 10))
  @IsNumber({}, { message: 'WEAVIATE_PORT must be a number' })
  @IsNotEmpty({ message: 'WEAVIATE_PORT is required' })
  WEAVIATE_PORT: number;
}

export const WEAVIATE_DEFAULTS = {
  WEAVIATE_HOST: 'localhost',
  WEAVIATE_PORT: 18080,
};
