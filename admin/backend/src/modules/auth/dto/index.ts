import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsString, IsNotEmpty } from 'class-validator';
import { AdminStatus, AdminRole } from '../../../entities';

export class RefreshTokenDto {
  @ApiProperty({ description: 'Refresh token' })
  @IsString()
  @IsNotEmpty()
  refreshToken: string;
}

export class AdminUserDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  email: string;

  @ApiProperty()
  name: string;

  @ApiProperty()
  picture: string;

  @ApiProperty({ enum: AdminStatus, description: '관리자 상태' })
  status: AdminStatus;

  @ApiProperty({ enum: AdminRole, description: '관리자 역할' })
  role: AdminRole;

  @ApiProperty()
  createdAt: Date;

  @ApiPropertyOptional({ nullable: true })
  lastLoginAt: Date | null;
}

export class TokenResponseDto {
  @ApiProperty({ description: 'Access token' })
  accessToken: string;

  @ApiProperty({ description: 'Refresh token' })
  refreshToken: string;

  @ApiProperty({ description: 'Admin user info', type: AdminUserDto })
  user: AdminUserDto;
}

export class PendingApprovalResponseDto {
  @ApiProperty({ description: 'Message' })
  message: string;

  @ApiProperty({ description: 'Admin status', enum: AdminStatus })
  status: AdminStatus;

  @ApiProperty({ description: 'User email' })
  email: string;
}
