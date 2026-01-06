import { IsString, IsNotEmpty } from 'class-validator';

export class UserBackendConfig {
  @IsString()
  @IsNotEmpty({ message: 'USER_BACKEND_URL is required' })
  USER_BACKEND_URL: string;
}

export const USER_BACKEND_DEFAULTS = {
  USER_BACKEND_URL: 'http://localhost:8000',
};
