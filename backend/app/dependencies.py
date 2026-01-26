"""FastAPI 의존성"""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .core.security import verify_token
from .database import get_db
from .models.user import User
from .services.user_service import UserService

# Bearer token 인증 스킴
security = HTTPBearer(auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ] = None,
    token: Annotated[str | None, Query()] = None,
) -> User:
    """현재 인증된 사용자 반환

    Authorization 헤더 또는 Query 파라미터 ?token=...으로 인증합니다.
    SSE 연결 시 EventSource API가 헤더를 설정할 수 없어서 Query 파라미터 지원이 필요합니다.

    Raises:
        HTTPException: 인증 실패 시
    """
    # Authorization 헤더 또는 Query 파라미터에서 토큰 추출
    access_token: str | None = None
    if credentials:
        access_token = credentials.credentials
    elif token:
        access_token = token

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_payload = verify_token(access_token, token_type="access")
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_service = UserService(db)
    user = await user_service.get_by_id(token_payload.sub)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """현재 인증된 슈퍼유저 반환"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


# 타입 별칭
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]
