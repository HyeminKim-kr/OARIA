"""Google OAuth 클라이언트"""

from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel

from ..config import settings

# OAuth 클라이언트 설정
oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


class GoogleUserInfo(BaseModel):
    """Google 사용자 정보"""

    sub: str  # Google ID
    email: str
    name: str | None = None
    picture: str | None = None
    email_verified: bool = False


async def get_google_user_info(token: dict) -> GoogleUserInfo:
    """토큰에서 Google 사용자 정보 추출

    Args:
        token: OAuth 토큰 (access_token, id_token 등 포함)

    Returns:
        GoogleUserInfo
    """
    userinfo = token.get("userinfo", {})

    return GoogleUserInfo(
        sub=userinfo.get("sub", ""),
        email=userinfo.get("email", ""),
        name=userinfo.get("name"),
        picture=userinfo.get("picture"),
        email_verified=userinfo.get("email_verified", False),
    )
