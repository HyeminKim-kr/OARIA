"""User 스키마"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """User 기본 스키마"""

    email: EmailStr
    name: str | None = None
    picture: str | None = None


class UserCreate(UserBase):
    """User 생성 스키마"""

    pass


class UserUpdate(BaseModel):
    """User 수정 스키마"""

    name: str | None = None
    picture: str | None = None


class UserResponse(UserBase):
    """User 응답 스키마"""

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class SocialAccountCreate(BaseModel):
    """SocialAccount 생성 스키마"""

    provider: str
    provider_id: str
    provider_email: str | None = None
    provider_name: str | None = None
    provider_picture: str | None = None


class SocialAccountResponse(BaseModel):
    """SocialAccount 응답 스키마"""

    id: UUID
    provider: str
    provider_id: str
    provider_email: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
