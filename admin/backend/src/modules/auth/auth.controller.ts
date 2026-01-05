import {
  Controller,
  Get,
  Post,
  Body,
  Req,
  Res,
  UseGuards,
  UnauthorizedException,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { ApiTags } from '@nestjs/swagger';
import { Request, Response } from 'express';
import { ConfigService } from '@nestjs/config';
import { AuthService } from './auth.service';
import { Public, CurrentAdmin } from './decorators';
import { GoogleProfile } from './strategies/google.strategy';
import {
  RefreshTokenDto,
  TokenResponseDto,
  AdminUserDto,
} from './dto';
import { AdminUser } from '../../entities';
import {
  ApiAuthGoogleLogin,
  ApiAuthGoogleCallback,
  ApiAuthRefresh,
  ApiAuthLogout,
  ApiAuthLogoutAll,
  ApiAuthGetMe,
} from './swagger';

@ApiTags('Auth')
@Controller('auth')
export class AuthController {
  constructor(
    private authService: AuthService,
    private configService: ConfigService,
  ) {}

  @Public()
  @Get('google')
  @UseGuards(AuthGuard('google'))
  @ApiAuthGoogleLogin()
  async googleLogin() {
    // Guard가 Google로 리다이렉트
  }

  @Public()
  @Get('google/callback')
  @UseGuards(AuthGuard('google'))
  @ApiAuthGoogleCallback()
  async googleCallback(@Req() req: Request, @Res() res: Response) {
    const profile = req.user as GoogleProfile;
    const deviceInfo = req.headers['user-agent']?.slice(0, 255);
    const ipAddress = req.ip;

    const result = await this.authService.handleGoogleLogin(
      profile,
      deviceInfo,
      ipAddress,
    );

    const frontendUrl = this.configService.get<string>(
      'ADMIN_FRONTEND_URL',
      'http://localhost:13001',
    );

    // 승인 대기 상태
    if (result.isPending) {
      return res.redirect(
        `${frontendUrl}/auth/pending?email=${encodeURIComponent(result.admin.email)}`,
      );
    }

    // 거절됨
    if (result.isRejected) {
      return res.redirect(
        `${frontendUrl}/auth/rejected?email=${encodeURIComponent(result.admin.email)}`,
      );
    }

    // 비활성화됨
    if (result.isDeactivated) {
      return res.redirect(
        `${frontendUrl}/auth/deactivated?email=${encodeURIComponent(result.admin.email)}`,
      );
    }

    // 승인됨 - 토큰 전달
    return res.redirect(
      `${frontendUrl}/auth/callback?access_token=${result.accessToken}&refresh_token=${result.refreshToken}`,
    );
  }

  @Public()
  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  @ApiAuthRefresh()
  async refresh(
    @Body() dto: RefreshTokenDto,
    @Req() req: Request,
  ): Promise<TokenResponseDto> {
    const token = await this.authService.verifyRefreshToken(dto.refreshToken);

    if (!token) {
      throw new UnauthorizedException('Invalid or expired refresh token');
    }

    const admin = await this.authService.getAdminById(token.adminId);
    if (!admin || !admin.isApproved()) {
      throw new UnauthorizedException('Admin not approved');
    }

    if (!admin.isActive) {
      throw new UnauthorizedException('Admin account is deactivated');
    }

    const deviceInfo = req.headers['user-agent']?.slice(0, 255);
    const ipAddress = req.ip;

    const { accessToken, refreshToken } = await this.authService.rotateToken(
      token,
      deviceInfo,
      ipAddress,
    );

    return {
      accessToken,
      refreshToken,
      user: this.toAdminUserDto(admin),
    };
  }

  @Post('logout')
  @HttpCode(HttpStatus.OK)
  @ApiAuthLogout()
  async logout(@Body() dto: RefreshTokenDto) {
    await this.authService.revokeToken(dto.refreshToken);
    return { message: 'Successfully logged out' };
  }

  @Post('logout/all')
  @HttpCode(HttpStatus.OK)
  @ApiAuthLogoutAll()
  async logoutAll(@CurrentAdmin() admin: AdminUser) {
    const count = await this.authService.revokeAllTokens(admin.id);
    return { message: `Successfully logged out from ${count} sessions` };
  }

  @Get('me')
  @ApiAuthGetMe()
  async getMe(@CurrentAdmin() admin: AdminUser): Promise<AdminUserDto> {
    return this.toAdminUserDto(admin);
  }

  private toAdminUserDto(admin: AdminUser): AdminUserDto {
    return {
      id: admin.id,
      email: admin.email,
      name: admin.name,
      picture: admin.picture,
      status: admin.status,
      role: admin.role,
      createdAt: admin.createdAt,
      lastLoginAt: admin.lastLoginAt,
    };
  }
}
