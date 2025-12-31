"""Auth 스키마"""

from pydantic import BaseModel

from .user import UserResponse


class TokenResponse(BaseModel):
    """토큰 응답"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
