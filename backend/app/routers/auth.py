import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import create_jwt, get_current_user
from app.models import User
from app.schemas import (
    AuthCallbackRequest,
    AuthCallbackResponse,
    AuthLoginResponse,
    UserInfo,
)
from app.services.quota import get_or_create_today, user_limits

router = APIRouter()
logger = logging.getLogger("app.auth")

_states: dict[str, bool] = {}


def _build_user_info(user: User, image_count: int, video_count: int) -> UserInfo:
    img, vid = user_limits(user)
    return UserInfo(
        id=user.id,
        linuxdo_id=user.linuxdo_id,
        username=user.username,
        avatar_url=user.avatar_url,
        trust_level=user.trust_level,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
        daily_image_limit=img,
        daily_video_limit=vid,
        used_today_images=image_count,
        used_today_videos=video_count,
    )


@router.get("/login", response_model=AuthLoginResponse)
async def login():
    if not settings.LINUXDO_CLIENT_ID:
        raise HTTPException(status_code=500, detail="LinuxDo OAuth 未配置")

    state = secrets.token_urlsafe(32)
    _states[state] = True
    if len(_states) > 200:
        for k in list(_states.keys())[:-100]:
            _states.pop(k, None)

    url = (
        f"{settings.LINUXDO_AUTHORIZE_URL}"
        f"?client_id={settings.LINUXDO_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={settings.LINUXDO_REDIRECT_URI}"
        f"&state={state}"
    )
    return AuthLoginResponse(url=url)


@router.post("/callback", response_model=AuthCallbackResponse)
async def callback(body: AuthCallbackRequest, db: AsyncSession = Depends(get_db)):
    if body.state and body.state in _states:
        _states.pop(body.state, None)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            token_resp = await client.post(
                settings.LINUXDO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": body.code,
                    "redirect_uri": settings.LINUXDO_REDIRECT_URI,
                },
                auth=(settings.LINUXDO_CLIENT_ID, settings.LINUXDO_CLIENT_SECRET),
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
        except Exception as e:
            logger.error("token exchange failed: %s", e)
            raise HTTPException(status_code=400, detail="OAuth 授权失败")

        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="未获取到 access_token")

        try:
            user_resp = await client.get(
                settings.LINUXDO_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_resp.raise_for_status()
            ud = user_resp.json()
        except Exception as e:
            logger.error("fetch user failed: %s", e)
            raise HTTPException(status_code=400, detail="获取 LinuxDo 用户信息失败")

    linuxdo_id = ud.get("id")
    username = ud.get("username", "")
    avatar_url = ud.get("avatar_url", "")
    trust_level = int(ud.get("trust_level", 0) or 0)

    if not linuxdo_id:
        raise HTTPException(status_code=400, detail="LinuxDo 返回数据无效")

    if trust_level < settings.MIN_TRUST_LEVEL:
        raise HTTPException(
            status_code=403,
            detail=f"需要 LinuxDo 信任等级 >= {settings.MIN_TRUST_LEVEL}，当前为 {trust_level}",
        )

    result = await db.execute(select(User).where(User.linuxdo_id == linuxdo_id))
    user = result.scalar_one_or_none()
    is_admin = int(linuxdo_id) in settings.admin_linuxdo_ids_set

    if user:
        user.username = username
        user.avatar_url = avatar_url
        user.trust_level = trust_level
        user.is_admin = is_admin or user.is_admin
    else:
        user = User(
            linuxdo_id=linuxdo_id,
            username=username,
            avatar_url=avatar_url,
            trust_level=trust_level,
            is_admin=is_admin,
        )
        db.add(user)
    await db.commit()
    await db.refresh(user)

    if user.is_banned:
        raise HTTPException(status_code=403, detail="账号已被封禁")

    du = await get_or_create_today(db, user.id)
    await db.commit()

    return AuthCallbackResponse(
        token=create_jwt(user.id),
        user=_build_user_info(user, du.image_count, du.video_count),
    )


@router.get("/me", response_model=UserInfo)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    du = await get_or_create_today(db, user.id)
    await db.commit()
    return _build_user_info(user, du.image_count, du.video_count)
