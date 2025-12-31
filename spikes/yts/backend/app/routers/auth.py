"""인증 라우터"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from ..config import settings
from ..core.oauth import get_google_user_info, oauth
from ..core.security import create_access_token
from ..database import get_db
from ..dependencies import CurrentUser
from ..schemas.auth import TokenResponse
from ..schemas.user import UserResponse
from ..services.user_service import UserService
from ..services.token_service import TokenService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_client_info(request: Request) -> tuple[str | None, str | None]:
    """클라이언트 정보 추출"""
    device_info = request.headers.get("user-agent", "")[:255] if request.headers.get("user-agent") else None
    ip_address = request.client.host if request.client else None
    return device_info, ip_address


@router.get("/google")
async def google_login(request: Request):
    """Google OAuth 로그인 시작

    브라우저를 Google 로그인 페이지로 리다이렉트
    """
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Google OAuth 콜백 처리

    Google에서 인증 후 리다이렉트되는 엔드포인트
    JWT 토큰을 발급하고 프론트엔드로 리다이렉트
    """
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to authorize: {str(e)}",
        )

    user_info = await get_google_user_info(token)

    if not user_info.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided by Google",
        )

    # 사용자 생성 또는 조회
    user_service = UserService(db)
    user, created = await user_service.get_or_create_by_social(
        provider="google",
        provider_id=user_info.sub,
        email=user_info.email,
        name=user_info.name,
        picture=user_info.picture,
    )

    # JWT Access Token 생성
    access_token = create_access_token(subject=str(user.id))

    # Refresh Token 생성 및 DB 저장
    device_info, ip_address = get_client_info(request)
    token_service = TokenService(db)
    refresh_token, _ = await token_service.create_refresh_token(
        user_id=user.id,
        device_info=device_info,
        ip_address=ip_address,
    )

    # 프론트엔드로 리다이렉트 (토큰을 쿼리 파라미터로 전달)
    # 실제 프로덕션에서는 httpOnly 쿠키 사용 권장
    redirect_url = (
        f"{settings.frontend_url}/auth/callback"
        f"?access_token={access_token}"
        f"&refresh_token={refresh_token}"
    )

    return RedirectResponse(url=redirect_url)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Refresh Token으로 새 Access Token 발급

    Body:
        refresh_token: Refresh Token

    Token Rotation 적용:
    - 기존 refresh token 폐기
    - 새 refresh token 발급
    """
    body = await request.json()
    refresh_token_str = body.get("refresh_token")

    if not refresh_token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required",
        )

    # DB에서 토큰 검증
    token_service = TokenService(db)
    token_record = await token_service.verify_refresh_token(refresh_token_str)

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # 사용자 조회
    user_service = UserService(db)
    user = await user_service.get_by_id(token_record.user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Token Rotation: 기존 토큰 폐기 + 새 토큰 발급
    device_info, ip_address = get_client_info(request)
    new_refresh_token, _ = await token_service.rotate_token(
        old_token_record=token_record,
        device_info=device_info,
        ip_address=ip_address,
    )

    # 새 Access Token 발급
    access_token = create_access_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """로그아웃

    현재 세션의 refresh token 폐기
    """
    # Body에서 refresh token 가져오기
    try:
        body = await request.json()
        refresh_token_str = body.get("refresh_token")
    except Exception:
        refresh_token_str = None

    if refresh_token_str:
        token_service = TokenService(db)
        token_record = await token_service.verify_refresh_token(refresh_token_str)
        if token_record:
            await token_service.revoke_token(token_record, reason="logout")

    # 쿠키 사용 시 삭제
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return {"message": "Successfully logged out"}


@router.post("/logout/all")
async def logout_all(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """모든 세션 로그아웃

    현재 사용자의 모든 refresh token 폐기
    """
    token_service = TokenService(db)
    revoked_count = await token_service.revoke_all_user_tokens(
        user_id=current_user.id,
        reason="logout_all",
    )

    return {"message": f"Successfully logged out from {revoked_count} sessions"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """현재 로그인한 사용자 정보 반환"""
    return current_user
