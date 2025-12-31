"""Token 서비스"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.refresh_token import UserRefreshToken


class TokenService:
    """Refresh Token 관리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def generate_token() -> str:
        """랜덤 토큰 생성"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """토큰 해싱 (SHA256)"""
        return hashlib.sha256(token.encode()).hexdigest()

    async def create_refresh_token(
        self,
        user_id: UUID,
        expires_days: int = 7,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[str, UserRefreshToken]:
        """Refresh Token 생성 및 저장

        Returns:
            (raw_token, token_record): 실제 토큰과 DB 레코드
        """
        raw_token = self.generate_token()
        token_hash = self.hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

        token_record = UserRefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        self.db.add(token_record)
        await self.db.commit()
        await self.db.refresh(token_record)

        return raw_token, token_record

    async def verify_refresh_token(self, raw_token: str) -> UserRefreshToken | None:
        """Refresh Token 검증

        Returns:
            유효한 토큰 레코드 또는 None
        """
        token_hash = self.hash_token(raw_token)

        result = await self.db.execute(
            select(UserRefreshToken).where(
                and_(
                    UserRefreshToken.token_hash == token_hash,
                    UserRefreshToken.revoked_at.is_(None),
                    UserRefreshToken.expires_at > datetime.now(timezone.utc),
                )
            )
        )
        token_record = result.scalar_one_or_none()

        if token_record:
            # 마지막 사용 시각 업데이트
            token_record.last_used_at = datetime.now(timezone.utc)
            await self.db.commit()

        return token_record

    async def revoke_token(
        self,
        token_record: UserRefreshToken,
        reason: str = "logout",
    ) -> None:
        """토큰 폐기"""
        token_record.revoked_at = datetime.now(timezone.utc)
        token_record.revoked_reason = reason
        await self.db.commit()

    async def revoke_all_user_tokens(
        self,
        user_id: UUID,
        reason: str = "security",
    ) -> int:
        """사용자의 모든 토큰 폐기 (강제 로그아웃)

        Returns:
            폐기된 토큰 수
        """
        result = await self.db.execute(
            select(UserRefreshToken).where(
                and_(
                    UserRefreshToken.user_id == user_id,
                    UserRefreshToken.revoked_at.is_(None),
                )
            )
        )
        tokens = result.scalars().all()

        now = datetime.now(timezone.utc)
        for token in tokens:
            token.revoked_at = now
            token.revoked_reason = reason

        await self.db.commit()
        return len(tokens)

    async def rotate_token(
        self,
        old_token_record: UserRefreshToken,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[str, UserRefreshToken]:
        """토큰 갱신 (기존 토큰 폐기 + 새 토큰 발급)

        Returns:
            (new_raw_token, new_token_record)
        """
        # 기존 토큰 폐기
        await self.revoke_token(old_token_record, reason="token_rotation")

        # 새 토큰 발급
        return await self.create_refresh_token(
            user_id=old_token_record.user_id,
            device_info=device_info or old_token_record.device_info,
            ip_address=ip_address or old_token_record.ip_address,
        )
