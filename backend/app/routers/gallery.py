import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_current_user_optional
from app.models import User, Work, WorkLike
from app.schemas import (
    GalleryResponse,
    LikeResponse,
    PublishRequest,
    ViewResponse,
    WorkInfo,
)

router = APIRouter()


def _to_info(
    w: Work,
    user: User | None,
    mine_user_id: int | None,
    liked_by_me: bool = False,
) -> WorkInfo:
    return WorkInfo(
        id=w.id,
        user_id=w.user_id,
        username=user.username if user else "",
        user_avatar=user.avatar_url if user else "",
        task_id=w.task_id,
        media_type=w.media_type,
        media_url=w.media_url,
        prompt=w.prompt,
        model=w.model,
        params=json.loads(w.params_json) if w.params_json else {},
        is_public=w.is_public,
        is_mine=mine_user_id is not None and w.user_id == mine_user_id,
        like_count=int(w.like_count or 0),
        view_count=int(w.view_count or 0),
        liked_by_me=liked_by_me,
        created_at=w.created_at,
    )


async def _liked_set(db: AsyncSession, user_id: int | None, work_ids: list[int]) -> set[int]:
    """返回当前用户已点赞过的 work_id 集合。"""
    if not user_id or not work_ids:
        return set()
    rows = await db.execute(
        select(WorkLike.work_id).where(
            WorkLike.user_id == user_id, WorkLike.work_id.in_(work_ids)
        )
    )
    return {int(r[0]) for r in rows.all()}


_SORT_OPTIONS = {
    "latest": lambda: Work.created_at.desc(),
    "likes": lambda: Work.like_count.desc(),
    "views": lambda: Work.view_count.desc(),
}


@router.get("/mine", response_model=GalleryResponse)
async def my_works(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    total_r = await db.execute(
        select(func.count()).select_from(Work).where(Work.user_id == user.id)
    )
    total = int(total_r.scalar() or 0)

    result = await db.execute(
        select(Work)
        .where(Work.user_id == user.id)
        .order_by(Work.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    works = list(result.scalars().all())
    liked = await _liked_set(db, user.id, [w.id for w in works])
    items = [_to_info(w, user, user.id, w.id in liked) for w in works]
    return GalleryResponse(items=items, total=total)


@router.get("/public", response_model=GalleryResponse)
async def public_gallery(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    limit: int = Query(24, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("latest", pattern="^(latest|likes|views)$"),
):
    total_r = await db.execute(
        select(func.count()).select_from(Work).where(Work.is_public.is_(True))
    )
    total = int(total_r.scalar() or 0)

    primary_order = _SORT_OPTIONS[sort]()
    # 二级排序统一回落到最新创建时间，保证榜单稳定
    secondary_order = Work.created_at.desc()

    result = await db.execute(
        select(Work, User)
        .join(User, Work.user_id == User.id)
        .where(Work.is_public.is_(True))
        .order_by(primary_order, secondary_order)
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()
    mine_id = user.id if user else None
    liked = await _liked_set(db, mine_id, [w.id for w, _ in rows])
    items = [_to_info(w, u, mine_id, w.id in liked) for w, u in rows]
    return GalleryResponse(items=items, total=total)


@router.put("/{work_id}/publish", response_model=WorkInfo)
async def toggle_publish(
    work_id: int,
    body: PublishRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Work).where(Work.id == work_id))
    w = result.scalar_one_or_none()
    if not w or w.user_id != user.id:
        raise HTTPException(404, "作品不存在")
    w.is_public = body.is_public
    await db.commit()
    await db.refresh(w)
    liked = await _liked_set(db, user.id, [w.id])
    return _to_info(w, user, user.id, w.id in liked)


@router.delete("/{work_id}")
async def delete_work(
    work_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Work).where(Work.id == work_id))
    w = result.scalar_one_or_none()
    if not w or (w.user_id != user.id and not user.is_admin):
        raise HTTPException(404, "作品不存在")
    # 关联的点赞记录一并清理
    await db.execute(
        WorkLike.__table__.delete().where(WorkLike.work_id == w.id)
    )
    await db.delete(w)
    await db.commit()
    return {"success": True}


@router.get("/{work_id}/remix", response_model=WorkInfo)
async def get_remix(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """一键同款：返回该作品的模型 + 参数 + prompt，前端把这些灌到表单里。"""
    result = await db.execute(select(Work, User).join(User, Work.user_id == User.id).where(Work.id == work_id))
    row = result.first()
    if not row:
        raise HTTPException(404, "作品不存在")
    w, u = row
    if not w.is_public and w.user_id != user.id:
        raise HTTPException(403, "该作品未公开")
    liked = await _liked_set(db, user.id, [w.id])
    return _to_info(w, u, user.id, w.id in liked)


@router.post("/{work_id}/like", response_model=LikeResponse)
async def toggle_like(
    work_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切换点赞状态。仅对已公开（或自己）作品生效。"""
    result = await db.execute(select(Work).where(Work.id == work_id))
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(404, "作品不存在")
    if not w.is_public and w.user_id != user.id:
        raise HTTPException(403, "该作品未公开")

    existing = await db.execute(
        select(WorkLike).where(WorkLike.work_id == work_id, WorkLike.user_id == user.id)
    )
    like_row = existing.scalar_one_or_none()

    if like_row:
        await db.delete(like_row)
        # 计数同步（避免负数）
        w.like_count = max(0, int(w.like_count or 0) - 1)
        liked_by_me = False
    else:
        try:
            db.add(WorkLike(work_id=work_id, user_id=user.id))
            await db.flush()
        except IntegrityError:
            await db.rollback()
            # 并发重复点赞，按已点赞返回
            again = await db.execute(select(Work).where(Work.id == work_id))
            w = again.scalar_one()
            return LikeResponse(work_id=w.id, liked_by_me=True, like_count=int(w.like_count or 0))
        w.like_count = int(w.like_count or 0) + 1
        liked_by_me = True

    await db.commit()
    await db.refresh(w)
    return LikeResponse(work_id=w.id, liked_by_me=liked_by_me, like_count=int(w.like_count or 0))


@router.post("/{work_id}/view", response_model=ViewResponse)
async def increment_view(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """记录一次详情查看。匿名也可以触发，仅做简单累加。"""
    result = await db.execute(select(Work).where(Work.id == work_id))
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(404, "作品不存在")
    if not w.is_public and (not user or (w.user_id != user.id and not user.is_admin)):
        raise HTTPException(403, "该作品未公开")

    w.view_count = int(w.view_count or 0) + 1
    await db.commit()
    await db.refresh(w)
    return ViewResponse(work_id=w.id, view_count=int(w.view_count or 0))
