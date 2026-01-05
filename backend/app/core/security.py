"""JWT 토큰 생성 및 검증"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel

from ..config import settings


class TokenPayload(BaseModel):
    """JWT 페이로드"""

    sub: str  # subject (user_id)
    exp: datetime
    type: str  # "access" or "refresh"


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Access Token 생성

    Args:
        subject: 토큰 주체 (보통 user_id)
        expires_delta: 만료 시간 (기본값: 설정에서 가져옴)
        extra_claims: 추가 클레임

    Returns:
        JWT 토큰 문자열
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Refresh Token 생성

    Args:
        subject: 토큰 주체 (보통 user_id)
        expires_delta: 만료 시간 (기본값: 설정에서 가져옴)

    Returns:
        JWT 토큰 문자열
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str, token_type: str = "access") -> TokenPayload | None:
    """토큰 검증

    Args:
        token: JWT 토큰
        token_type: 토큰 타입 ("access" or "refresh")

    Returns:
        TokenPayload if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # 토큰 타입 검증
        if payload.get("type") != token_type:
            return None

        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            type=payload["type"],
        )
    except JWTError:
        return None
