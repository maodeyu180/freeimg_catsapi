"""
每日配额计算工具。按 QUOTA_TIMEZONE 划分自然日。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DailyUsage, User


def today_str() -> str:
    """按配置时区返回 YYYY-MM-DD。"""
    try:
        # Python 3.9+ zoneinfo
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(settings.QUOTA_TIMEZONE)
    except Exception:
        # fallback: UTC+8
        tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d")


def user_limits(user: User) -> tuple[int, int]:
    """返回 (image_limit, video_limit)。"""
    img = user.daily_image_limit if user.daily_image_limit is not None else settings.DAILY_IMAGE_LIMIT
    vid = user.daily_video_limit if user.daily_video_limit is not None else settings.DAILY_VIDEO_LIMIT
    return img, vid


async def get_or_create_today(db: AsyncSession, user_id: int) -> DailyUsage:
    date_str = today_str()
    result = await db.execute(
        select(DailyUsage).where(DailyUsage.user_id == user_id, DailyUsage.usage_date == date_str)
    )
    du = result.scalar_one_or_none()
    if du is None:
        du = DailyUsage(user_id=user_id, usage_date=date_str, image_count=0, video_count=0)
        db.add(du)
        await db.flush()
    return du


async def check_quota(db: AsyncSession, user: User, task_type: str) -> None:
    """配额不足时抛 ValueError。"""
    du = await get_or_create_today(db, user.id)
    img_limit, vid_limit = user_limits(user)
    if task_type == "image":
        if du.image_count >= img_limit:
            raise ValueError(f"今日图片配额已用完（{du.image_count}/{img_limit}），请明天再来")
    elif task_type == "video":
        if du.video_count >= vid_limit:
            raise ValueError(f"今日视频配额已用完（{du.video_count}/{vid_limit}），请明天再来")


async def consume(db: AsyncSession, user_id: int, task_type: str) -> None:
    du = await get_or_create_today(db, user_id)
    if task_type == "image":
        du.image_count += 1
    elif task_type == "video":
        du.video_count += 1
    await db.flush()
