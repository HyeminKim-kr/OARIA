import { Injectable, Logger, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, IsNull } from 'typeorm';
import * as crypto from 'crypto';
import {
  AdminUser,
  AdminRefreshToken,
  AdminStatus,
  AdminRole,
} from '../../entities';
import { GoogleProfile } from './strategies/google.strategy';
import { JwtPayload } from './strategies/jwt.strategy';

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);

  constructor(
    @InjectRepository(AdminUser)
    private adminUserRepository: Repository<AdminUser>,
    @InjectRepository(AdminRefreshToken)
    private refreshTokenRepository: Repository<AdminRefreshToken>,
    private jwtService: JwtService,
    private configService: ConfigService,
  ) {}

  /**
   * 서버 시작 시 Super Admin 초기화
   */
  async initializeSuperAdmin(): Promise<void> {
    const superAdminEmail = this.configService.get<string>('SUPER_ADMIN_EMAIL');

    if (!superAdminEmail) {
      this.logger.warn('SUPER_ADMIN_EMAIL not configured');
      return;
    }

    const existing = await this.adminUserRepository.findOne({
      where: { email: superAdminEmail },
    });

    if (existing) {
      // 이미 있으면 super_admin으로 승격
      if (existing.role !== AdminRole.SUPER_ADMIN) {
        existing.role = AdminRole.SUPER_ADMIN;
        existing.status = AdminStatus.APPROVED;
        existing.approvedAt = new Date();
        await this.adminUserRepository.save(existing);
        this.logger.log(`Upgraded ${superAdminEmail} to super_admin`);
      }
      return;
    }

    // 아직 없으면 placeholder 생성 (Google 로그인 시 자동 매칭)
    this.logger.log(
      `Super admin email configured: ${superAdminEmail} (will be activated on first login)`,
    );
  }

  /**
   * Google OAuth 로그인 처리
   */
  async handleGoogleLogin(
    profile: GoogleProfile,
    deviceInfo?: string,
    ipAddress?: string,
  ): Promise<{
    admin: AdminUser;
    accessToken?: string;
    refreshToken?: string;
    isPending: boolean;
    isRejected: boolean;
    isDeactivated: boolean;
  }> {
    const superAdminEmail = this.configService.get<string>('SUPER_ADMIN_EMAIL');
    let admin = await this.adminUserRepository.findOne({
      where: { googleId: profile.googleId },
    });

    if (!admin) {
      // email로도 확인 (super admin용)
      admin = await this.adminUserRepository.findOne({
        where: { email: profile.email },
      });

      if (admin) {
        // Google ID 연결
        admin.googleId = profile.googleId;
        admin.name = profile.name;
        admin.picture = profile.picture;
      }
    }

    const isSuperAdminEmail = profile.email === superAdminEmail;

    if (!admin) {
      // 새 관리자 생성
      admin = this.adminUserRepository.create({
        email: profile.email,
        googleId: profile.googleId,
        name: profile.name,
        picture: profile.picture,
        status: isSuperAdminEmail
          ? AdminStatus.APPROVED
          : AdminStatus.PENDING,
        role: isSuperAdminEmail ? AdminRole.SUPER_ADMIN : AdminRole.ADMIN,
        approvedAt: isSuperAdminEmail ? new Date() : null,
      });
      admin = await this.adminUserRepository.save(admin);
      this.logger.log(
        `New admin created: ${profile.email} (${isSuperAdminEmail ? 'super_admin' : 'pending'})`,
      );
    }

    // 프로필 정보 업데이트
    admin.name = profile.name;
    admin.picture = profile.picture;
    admin.lastLoginAt = new Date();
    await this.adminUserRepository.save(admin);

    // 상태 확인
    if (admin.status === AdminStatus.PENDING) {
      return { admin, isPending: true, isRejected: false, isDeactivated: false };
    }

    if (admin.status === AdminStatus.REJECTED) {
      return { admin, isPending: false, isRejected: true, isDeactivated: false };
    }

    // 비활성화 확인
    if (!admin.isActive) {
      return { admin, isPending: false, isRejected: false, isDeactivated: true };
    }

    // 승인된 관리자만 토큰 발급
    const accessToken = this.createAccessToken(admin);
    const refreshToken = await this.createRefreshToken(
      admin.id,
      deviceInfo,
      ipAddress,
    );

    return {
      admin,
      accessToken,
      refreshToken,
      isPending: false,
      isRejected: false,
      isDeactivated: false,
    };
  }

  /**
   * Access Token 생성
   */
  createAccessToken(admin: AdminUser): string {
    const payload: JwtPayload = {
      sub: admin.id,
      email: admin.email,
      role: admin.role,
    };

    return this.jwtService.sign(payload as unknown as Record<string, unknown>, {
      expiresIn: '15m',
    });
  }

  /**
   * Refresh Token 생성 및 저장
   */
  async createRefreshToken(
    adminId: string,
    deviceInfo?: string,
    ipAddress?: string,
  ): Promise<string> {
    const rawToken = crypto.randomBytes(32).toString('base64url');
    const tokenHash = crypto
      .createHash('sha256')
      .update(rawToken)
      .digest('hex');

    const expiresInDays = parseInt(
      this.configService.get<string>('JWT_REFRESH_EXPIRES_DAYS', '7'),
      10,
    );
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + expiresInDays);

    const token = this.refreshTokenRepository.create({
      adminId,
      tokenHash,
      expiresAt,
      deviceInfo,
      ipAddress,
    });

    await this.refreshTokenRepository.save(token);
    return rawToken;
  }

  /**
   * Refresh Token 검증
   */
  async verifyRefreshToken(rawToken: string): Promise<AdminRefreshToken | null> {
    const tokenHash = crypto
      .createHash('sha256')
      .update(rawToken)
      .digest('hex');

    const token = await this.refreshTokenRepository.findOne({
      where: {
        tokenHash,
        revokedAt: IsNull(),
      },
      relations: ['admin'],
    });

    if (!token || !token.isValid()) {
      return null;
    }

    // 마지막 사용 시간 업데이트
    token.lastUsedAt = new Date();
    await this.refreshTokenRepository.save(token);

    return token;
  }

  /**
   * Token Rotation (기존 토큰 폐기 + 새 토큰 발급)
   */
  async rotateToken(
    oldToken: AdminRefreshToken,
    deviceInfo?: string,
    ipAddress?: string,
  ): Promise<{ accessToken: string; refreshToken: string }> {
    // 기존 토큰 폐기
    oldToken.revoke('token_rotation');
    await this.refreshTokenRepository.save(oldToken);

    // 새 토큰 발급
    const accessToken = this.createAccessToken(oldToken.admin);
    const refreshToken = await this.createRefreshToken(
      oldToken.adminId,
      deviceInfo || oldToken.deviceInfo,
      ipAddress || oldToken.ipAddress,
    );

    return { accessToken, refreshToken };
  }

  /**
   * 토큰 폐기 (로그아웃)
   */
  async revokeToken(rawToken: string): Promise<boolean> {
    const token = await this.verifyRefreshToken(rawToken);
    if (!token) {
      return false;
    }

    token.revoke('logout');
    await this.refreshTokenRepository.save(token);
    return true;
  }

  /**
   * 모든 토큰 폐기 (전체 로그아웃)
   */
  async revokeAllTokens(adminId: string): Promise<number> {
    const tokens = await this.refreshTokenRepository.find({
      where: {
        adminId,
        revokedAt: IsNull(),
      },
    });

    for (const token of tokens) {
      token.revoke('logout_all');
    }

    await this.refreshTokenRepository.save(tokens);
    return tokens.length;
  }

  /**
   * Admin 조회
   */
  async getAdminById(id: string): Promise<AdminUser | null> {
    return this.adminUserRepository.findOne({ where: { id } });
  }
}
