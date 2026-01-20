"""User 서비스"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.user import User
from ..models.social_account import SocialAccount
from ..schemas.user import UserCreate


class UserService:
    """User CRUD 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        """ID로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_social_account(self, provider: str, provider_id: str) -> User | None:
        """소셜 계정으로 사용자 조회"""
        result = await self.db.execute(
            select(User)
            .join(SocialAccount)
            .where(
                SocialAccount.provider == provider,
                SocialAccount.provider_id == provider_id,
            )
            .options(selectinload(User.social_accounts))
        )
        return result.scalar_one_or_none()

    async def create(self, user_in: UserCreate) -> User:
        """사용자 생성"""
        user = User(
            email=user_in.email,
            name=user_in.name,
            picture=user_in.picture,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def add_social_account(
        self,
        user: User,
        provider: str,
        provider_id: str,
        provider_email: str | None = None,
        provider_name: str | None = None,
        provider_picture: str | None = None,
    ) -> SocialAccount:
        """사용자에게 소셜 계정 연동 추가"""
        social_account = SocialAccount(
            user_id=user.id,
            provider=provider,
            provider_id=provider_id,
            provider_email=provider_email,
            provider_name=provider_name,
            provider_picture=provider_picture,
        )
        self.db.add(social_account)
        await self.db.commit()
        await self.db.refresh(social_account)
        return social_account

    async def get_or_create_by_social(
        self,
        provider: str,
        provider_id: str,
        email: str,
        name: str | None = None,
        picture: str | None = None,
    ) -> tuple[User, bool]:
        """소셜 정보로 사용자 조회 또는 생성

        Returns:
            (User, created): 사용자와 새로 생성되었는지 여부
        """
        # 먼저 소셜 계정으로 조회
        user = await self.get_by_social_account(provider, provider_id)
        if user:
            # 기존 유저 - 정보 업데이트
            user.name = name or user.name
            user.picture = picture or user.picture
            user.last_login_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(user)
            return user, False

        # email로 조회 (기존 유저가 소셜 연동 추가하는 경우)
        user = await self.get_by_email(email)
        if user:
            # 소셜 계정 연동 추가
            await self.add_social_account(
                user=user,
                provider=provider,
                provider_id=provider_id,
                provider_email=email,
                provider_name=name,
                provider_picture=picture,
            )
            user.name = name or user.name
            user.picture = picture or user.picture
            user.last_login_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(user)
            return user, False

        # 새 유저 생성
        user_in = UserCreate(
            email=email,
            name=name,
            picture=picture,
        )
        user = await self.create(user_in)

        # 소셜 계정 연동 추가
        await self.add_social_account(
            user=user,
            provider=provider,
            provider_id=provider_id,
            provider_email=email,
            provider_name=name,
            provider_picture=picture,
        )

        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        return user, True
