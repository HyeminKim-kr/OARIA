import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsString, IsEnum, IsOptional } from 'class-validator';
import { AdminRole, AdminStatus } from '../../../entities';

export class ApproveAdminDto {
  @ApiPropertyOptional({ description: 'Role to assign', enum: AdminRole })
  @IsEnum(AdminRole)
  @IsOptional()
  role?: AdminRole;
}

export class RejectAdminDto {
  @ApiPropertyOptional({ description: 'Rejection reason' })
  @IsString()
  @IsOptional()
  reason?: string;
}

export class UpdateRoleDto {
  @ApiProperty({ description: 'New role', enum: AdminRole })
  @IsEnum(AdminRole)
  role: AdminRole;
}

export class AdminUserListItemDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  email: string;

  @ApiProperty()
  name: string;

  @ApiProperty()
  picture: string;

  @ApiProperty({ enum: AdminStatus })
  status: AdminStatus;

  @ApiProperty({ enum: AdminRole })
  role: AdminRole;

  @ApiProperty()
  isActive: boolean;

  @ApiProperty()
  createdAt: Date;

  @ApiPropertyOptional()
  lastLoginAt?: Date;

  @ApiPropertyOptional()
  approvedAt?: Date | null;

  @ApiPropertyOptional({ description: 'Approver info' })
  approvedBy?: {
    id: string;
    email: string;
    name: string;
  };

  @ApiPropertyOptional()
  rejectedReason?: string | null;

  @ApiPropertyOptional()
  deactivatedAt?: Date | null;

  @ApiPropertyOptional({ description: 'Deactivator info' })
  deactivatedBy?: {
    id: string;
    email: string;
    name: string;
  };
}

export class AdminListResponseDto {
  @ApiProperty({ type: [AdminUserListItemDto] })
  items: AdminUserListItemDto[];

  @ApiProperty()
  total: number;

  @ApiProperty()
  pendingCount: number;
}
