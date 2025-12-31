import {
  Injectable,
  NotFoundException,
  ForbiddenException,
  BadRequestException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import {
  AdminUser,
  AdminStatus,
  AdminRole,
  AdminRefreshToken,
} from '../../entities';

@Injectable()
export class AdminUsersService {
  constructor(
    @InjectRepository(AdminUser)
    private adminUserRepository: Repository<AdminUser>,
    @InjectRepository(AdminRefreshToken)
    private refreshTokenRepository: Repository<AdminRefreshToken>,
  ) {}

  /**
   * 모든 관리자 목록 조회
   */
  async findAll(): Promise<{
    items: AdminUser[];
    total: number;
    pendingCount: number;
  }> {
    const [items, total] = await this.adminUserRepository.findAndCount({
      relations: ['approvedBy', 'deactivatedBy'],
      order: {
        createdAt: 'DESC',
      },
    });

    const pendingCount = items.filter(
      (admin) => admin.status === AdminStatus.PENDING,
    ).length;

    return { items, total, pendingCount };
  }

  /**
   * 승인 대기 관리자 목록
   */
  async findPending(): Promise<AdminUser[]> {
    return this.adminUserRepository.find({
      where: { status: AdminStatus.PENDING },
      order: { createdAt: 'ASC' },
    });
  }

  /**
   * 관리자 조회
   */
  async findById(id: string): Promise<AdminUser> {
    const admin = await this.adminUserRepository.findOne({
      where: { id },
      relations: ['approvedBy'],
    });

    if (!admin) {
      throw new NotFoundException('Admin not found');
    }

    return admin;
  }

  /**
   * 관리자 승인
   */
  async approve(
    id: string,
    approver: AdminUser,
    role?: AdminRole,
  ): Promise<AdminUser> {
    if (!approver.canApproveUsers()) {
      throw new ForbiddenException('Only super admin can approve users');
    }

    const admin = await this.findById(id);

    if (admin.status !== AdminStatus.PENDING) {
      throw new BadRequestException('Admin is not pending approval');
    }

    admin.status = AdminStatus.APPROVED;
    admin.role = role || AdminRole.ADMIN;
    admin.approvedById = approver.id;
    admin.approvedAt = new Date();
    admin.rejectedReason = null;

    return this.adminUserRepository.save(admin);
  }

  /**
   * 관리자 거절
   */
  async reject(
    id: string,
    approver: AdminUser,
    reason?: string,
  ): Promise<AdminUser> {
    if (!approver.canApproveUsers()) {
      throw new ForbiddenException('Only super admin can reject users');
    }

    const admin = await this.findById(id);

    if (admin.status !== AdminStatus.PENDING) {
      throw new BadRequestException('Admin is not pending approval');
    }

    admin.status = AdminStatus.REJECTED;
    admin.approvedById = approver.id;
    admin.approvedAt = new Date();
    admin.rejectedReason = reason || 'No reason provided';

    return this.adminUserRepository.save(admin);
  }

  /**
   * 역할 변경
   */
  async updateRole(
    id: string,
    actor: AdminUser,
    newRole: AdminRole,
  ): Promise<AdminUser> {
    if (!actor.isSuperAdmin()) {
      throw new ForbiddenException('Only super admin can change roles');
    }

    const admin = await this.findById(id);

    if (admin.id === actor.id) {
      throw new BadRequestException('Cannot change own role');
    }

    admin.role = newRole;
    return this.adminUserRepository.save(admin);
  }

  /**
   * 관리자 비활성화
   */
  async deactivate(id: string, actor: AdminUser): Promise<AdminUser> {
    if (!actor.isSuperAdmin()) {
      throw new ForbiddenException('Only super admin can deactivate users');
    }

    const admin = await this.findById(id);

    if (admin.id === actor.id) {
      throw new BadRequestException('Cannot deactivate yourself');
    }

    if (admin.isSuperAdmin()) {
      throw new BadRequestException('Cannot deactivate a super admin');
    }

    admin.isActive = false;
    admin.deactivatedById = actor.id;
    admin.deactivatedAt = new Date();

    // 모든 토큰 폐기
    await this.refreshTokenRepository.update(
      { adminId: id, revokedAt: null as any },
      { revokedAt: new Date(), revokedReason: 'deactivated' },
    );

    const saved = await this.adminUserRepository.save(admin);
    // deactivatedBy relation 로드
    return (await this.adminUserRepository.findOne({
      where: { id: saved.id },
      relations: ['approvedBy', 'deactivatedBy'],
    }))!;
  }

  /**
   * 관리자 재활성화
   */
  async reactivate(id: string, actor: AdminUser): Promise<AdminUser> {
    if (!actor.isSuperAdmin()) {
      throw new ForbiddenException('Only super admin can reactivate users');
    }

    const admin = await this.findById(id);
    admin.isActive = true;
    admin.deactivatedById = null;
    admin.deactivatedAt = null;

    const saved = await this.adminUserRepository.save(admin);
    return (await this.adminUserRepository.findOne({
      where: { id: saved.id },
      relations: ['approvedBy', 'deactivatedBy'],
    }))!;
  }
}
