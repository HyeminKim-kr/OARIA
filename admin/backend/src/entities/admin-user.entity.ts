import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
} from 'typeorm';

export enum AdminStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
}

export enum AdminRole {
  SUPER_ADMIN = 'super_admin',
  ADMIN = 'admin',
  VIEWER = 'viewer',
}

@Entity('admin_users')
export class AdminUser {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255, unique: true })
  email: string;

  @Column({ type: 'varchar', length: 255, unique: true, name: 'google_id' })
  googleId: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  name: string;

  @Column({ type: 'varchar', length: 512, nullable: true })
  picture: string;

  @Column({
    type: 'varchar',
    length: 20,
    default: AdminStatus.PENDING,
  })
  status: AdminStatus;

  @Column({
    type: 'varchar',
    length: 50,
    default: AdminRole.ADMIN,
  })
  role: AdminRole;

  @Column({ type: 'uuid', nullable: true, name: 'approved_by' })
  approvedById: string;

  @ManyToOne(() => AdminUser, { nullable: true })
  @JoinColumn({ name: 'approved_by' })
  approvedBy: AdminUser;

  @Column({ type: 'timestamptz', nullable: true, name: 'approved_at' })
  approvedAt: Date | null;

  @Column({ type: 'text', nullable: true, name: 'rejected_reason' })
  rejectedReason: string | null;

  @Column({ type: 'boolean', default: true, name: 'is_active' })
  isActive: boolean;

  @Column({ type: 'uuid', nullable: true, name: 'deactivated_by' })
  deactivatedById: string | null;

  @ManyToOne(() => AdminUser, { nullable: true })
  @JoinColumn({ name: 'deactivated_by' })
  deactivatedBy: AdminUser;

  @Column({ type: 'timestamptz', nullable: true, name: 'deactivated_at' })
  deactivatedAt: Date | null;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ type: 'timestamptz', name: 'updated_at' })
  updatedAt: Date;

  @Column({ type: 'timestamptz', nullable: true, name: 'last_login_at' })
  lastLoginAt: Date;

  @OneToMany(() => AdminRefreshToken, (token) => token.admin)
  refreshTokens: AdminRefreshToken[];

  // Helper methods
  isPending(): boolean {
    return this.status === AdminStatus.PENDING;
  }

  isApproved(): boolean {
    return this.status === AdminStatus.APPROVED;
  }

  isSuperAdmin(): boolean {
    return this.role === AdminRole.SUPER_ADMIN;
  }

  canApproveUsers(): boolean {
    return this.isSuperAdmin() && this.isApproved();
  }
}

@Entity('admin_refresh_tokens')
export class AdminRefreshToken {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'uuid', name: 'admin_id' })
  adminId: string;

  @ManyToOne(() => AdminUser, (admin) => admin.refreshTokens)
  @JoinColumn({ name: 'admin_id' })
  admin: AdminUser;

  @Column({ type: 'varchar', length: 64, name: 'token_hash' })
  tokenHash: string;

  @Column({ type: 'timestamptz', name: 'expires_at' })
  expiresAt: Date;

  @Column({ type: 'varchar', length: 255, nullable: true, name: 'device_info' })
  deviceInfo: string;

  @Column({ type: 'varchar', length: 45, nullable: true, name: 'ip_address' })
  ipAddress: string;

  @Column({ type: 'timestamptz', nullable: true, name: 'revoked_at' })
  revokedAt: Date;

  @Column({ type: 'varchar', length: 100, nullable: true, name: 'revoked_reason' })
  revokedReason: string;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt: Date;

  @Column({ type: 'timestamptz', nullable: true, name: 'last_used_at' })
  lastUsedAt: Date;

  // Helper methods
  isValid(): boolean {
    return !this.revokedAt && new Date() < this.expiresAt;
  }

  revoke(reason: string = 'logout'): void {
    this.revokedAt = new Date();
    this.revokedReason = reason;
  }
}
