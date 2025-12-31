import {
  Controller,
  Get,
  Patch,
  Param,
  Body,
  ParseUUIDPipe,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { AdminUsersService } from './admin-users.service';
import { Roles, CurrentAdmin } from '../auth/decorators';
import {
  ApproveAdminDto,
  RejectAdminDto,
  UpdateRoleDto,
  AdminUserListItemDto,
  AdminListResponseDto,
} from './dto';
import { AdminUser, AdminRole } from '../../entities';
import {
  ApiAdminUsersFindAll,
  ApiAdminUsersFindPending,
  ApiAdminUsersFindOne,
  ApiAdminUsersApprove,
  ApiAdminUsersReject,
  ApiAdminUsersUpdateRole,
  ApiAdminUsersDeactivate,
  ApiAdminUsersReactivate,
} from './swagger';

@ApiTags('Admin Users')
@Controller('admin/users')
export class AdminUsersController {
  constructor(private adminUsersService: AdminUsersService) {}

  @Get()
  @Roles(AdminRole.SUPER_ADMIN)
  @ApiAdminUsersFindAll()
  async findAll(): Promise<AdminListResponseDto> {
    const { items, total, pendingCount } =
      await this.adminUsersService.findAll();

    return {
      items: items.map(this.toListItemDto),
      total,
      pendingCount,
    };
  }

  @Get('pending')
  @Roles(AdminRole.SUPER_ADMIN)
  @ApiAdminUsersFindPending()
  async findPending(): Promise<AdminUserListItemDto[]> {
    const admins = await this.adminUsersService.findPending();
    return admins.map(this.toListItemDto);
  }

  @Get(':id')
  @Roles(AdminRole.SUPER_ADMIN)
  @ApiAdminUsersFindOne()
  async findOne(
    @Param('id', ParseUUIDPipe) id: string,
  ): Promise<AdminUserListItemDto> {
    const admin = await this.adminUsersService.findById(id);
    return this.toListItemDto(admin);
  }

  @Patch(':id/approve')
  @Roles(AdminRole.SUPER_ADMIN)
  @ApiAdminUsersApprove()
  async approve(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: ApproveAdminDto,
    @CurrentAdmin() currentAdmin: AdminUser,
  ): Promise<AdminUserListItemDto> {
    const admin = await this.adminUsersService.approve(
      id,
      currentAdmin,
      dto.role,
    );
    return this.toListItemDto(admin);
  }

  @Patch(':id/reject')
  @Roles(AdminRole.SUPER_ADMIN)
  @ApiAdminUsersReject()
  async reject(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: RejectAdminDto,
    @CurrentAdmin() currentAdmin: AdminUser,
  ): Promise<AdminUserListItemDto> {
    const admin = await this.adminUsersService.reject(
      id,
      currentAdmin,
      dto.reason,
    );
    return this.toListItemDto(admin);
  }

  @Patch(':id/role')
  @Roles(AdminRole.SUPER_ADMIN)
  @ApiAdminUsersUpdateRole()
  async updateRole(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateRoleDto,
    @CurrentAdmin() currentAdmin: AdminUser,
  ): Promise<AdminUserListItemDto> {
    const admin = await this.adminUsersService.updateRole(
      id,
      currentAdmin,
      dto.role,
    );
    return this.toListItemDto(admin);
  }

  @Patch(':id/deactivate')
  @Roles(AdminRole.SUPER_ADMIN)
  @ApiAdminUsersDeactivate()
  async deactivate(
    @Param('id', ParseUUIDPipe) id: string,
    @CurrentAdmin() currentAdmin: AdminUser,
  ): Promise<AdminUserListItemDto> {
    const admin = await this.adminUsersService.deactivate(id, currentAdmin);
    return this.toListItemDto(admin);
  }

  @Patch(':id/reactivate')
  @Roles(AdminRole.SUPER_ADMIN)
  @ApiAdminUsersReactivate()
  async reactivate(
    @Param('id', ParseUUIDPipe) id: string,
    @CurrentAdmin() currentAdmin: AdminUser,
  ): Promise<AdminUserListItemDto> {
    const admin = await this.adminUsersService.reactivate(id, currentAdmin);
    return this.toListItemDto(admin);
  }

  private toListItemDto(admin: AdminUser): AdminUserListItemDto {
    return {
      id: admin.id,
      email: admin.email,
      name: admin.name,
      picture: admin.picture,
      status: admin.status,
      role: admin.role,
      isActive: admin.isActive,
      createdAt: admin.createdAt,
      lastLoginAt: admin.lastLoginAt,
      approvedAt: admin.approvedAt,
      approvedBy: admin.approvedBy
        ? {
            id: admin.approvedBy.id,
            email: admin.approvedBy.email,
            name: admin.approvedBy.name,
          }
        : undefined,
      rejectedReason: admin.rejectedReason,
      deactivatedAt: admin.deactivatedAt,
      deactivatedBy: admin.deactivatedBy
        ? {
            id: admin.deactivatedBy.id,
            email: admin.deactivatedBy.email,
            name: admin.deactivatedBy.name,
          }
        : undefined,
    };
  }
}
