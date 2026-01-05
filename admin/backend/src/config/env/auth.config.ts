import { IsString, IsNotEmpty } from 'class-validator';

export class AuthConfig {
  // JWT
  @IsString()
  @IsNotEmpty({ message: 'JWT_SECRET is required' })
  JWT_SECRET: string;

  @IsString()
  @IsNotEmpty({ message: 'JWT_ACCESS_EXPIRES is required' })
  JWT_ACCESS_EXPIRES: string;

  @IsString()
  @IsNotEmpty({ message: 'JWT_REFRESH_EXPIRES_DAYS is required' })
  JWT_REFRESH_EXPIRES_DAYS: string;

  // Google OAuth
  @IsString()
  GOOGLE_CLIENT_ID: string;

  @IsString()
  GOOGLE_CLIENT_SECRET: string;

  @IsString()
  @IsNotEmpty({ message: 'GOOGLE_CALLBACK_URL is required' })
  GOOGLE_CALLBACK_URL: string;

  // Super Admin
  @IsString()
  SUPER_ADMIN_EMAIL: string;

  // Frontend URL
  @IsString()
  @IsNotEmpty({ message: 'ADMIN_FRONTEND_URL is required' })
  ADMIN_FRONTEND_URL: string;
}

export const AUTH_DEFAULTS = {
  JWT_SECRET: 'local-dev-secret-key-do-not-use-in-production',
  JWT_ACCESS_EXPIRES: '15m',
  JWT_REFRESH_EXPIRES_DAYS: '7',
  GOOGLE_CLIENT_ID: '',
  GOOGLE_CLIENT_SECRET: '',
  GOOGLE_CALLBACK_URL: 'http://localhost:13000/auth/google/callback',
  SUPER_ADMIN_EMAIL: '',
  ADMIN_FRONTEND_URL: 'http://localhost:13001',
};
