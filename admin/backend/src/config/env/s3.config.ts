import { IsString, IsNotEmpty } from 'class-validator';

export class S3Config {
  @IsString()
  @IsNotEmpty({ message: 'S3_ENDPOINT is required' })
  S3_ENDPOINT: string;

  @IsString()
  @IsNotEmpty({ message: 'S3_ACCESS_KEY is required' })
  S3_ACCESS_KEY: string;

  @IsString()
  @IsNotEmpty({ message: 'S3_SECRET_KEY is required' })
  S3_SECRET_KEY: string;

  @IsString()
  @IsNotEmpty({ message: 'S3_BUCKET is required' })
  S3_BUCKET: string;
}

export const S3_DEFAULTS = {
  S3_ENDPOINT: 'http://localhost:19000',
  S3_ACCESS_KEY: 'minioadmin',
  S3_SECRET_KEY: 'minioadmin_2024',
  S3_BUCKET: 'oaria-papers',
};
