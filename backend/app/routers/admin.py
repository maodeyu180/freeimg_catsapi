import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_admin_user
from app.models import Task, User, Work
from app.schemas import (
    AdminUpdateUserRequest,
    AdminUserInfo,
    AdminUserListResponse,
    TaskInfo,
    TaskListResponse,
    WorkBrief,
)
from app.services.quota import user_limits

router = APIRouter()


def _to_admin_user(u: User) -> AdminUserInfo:
    img, vid = user_limits(u)
    return AdminUserInfo(
        id=u.id,
        linuxdo_id=u.linuxdo_id,
        username=u.username,
        avatar_url=u.avatar_url,
        trust_level=u.trust_level,
        is_admin=u.is_admin,
        is_banned=u.is_banned,
        daily_image_limit=img,
        daily_video_limit=vid,
        created_at=u.created_at,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(default=None, max_length=128),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)
    keyword = q.strip() if q else ""
    if keyword:
        condition = User.username.ilike(f"%{keyword}%")
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total_r = await db.execute(count_stmt)
    total = int(total_r.scalar() or 0)
    result = await db.execute(
        stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    items = [_to_admin_user(u) for u in result.scalars().all()]
    return AdminUserListResponse(items=items, total=total)


@router.put("/users/{user_id}", response_model=AdminUserInfo)
async def update_user(
    user_id: int,
    body: AdminUpdateUserRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "用户不存在")
    if body.is_banned is not None:
        u.is_banned = body.is_banned
    if body.daily_image_limit is not None:
        u.daily_image_limit = body.daily_image_limit
    if body.daily_video_limit is not None:
        u.daily_video_limit = body.daily_video_limit
    await db.commit()
    await db.refresh(u)
    return _to_admin_user(u)


@router.get("/tasks", response_model=TaskListResponse)
async def list_all_tasks(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(default=None),
    user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(Task, User).join(User, Task.user_id == User.id)
    count_stmt = select(func.count()).select_from(Task)
    if status:
        stmt = stmt.where(Task.status == status)
        count_stmt = count_stmt.where(Task.status == status)
    if user_id is not None:
        stmt = stmt.where(Task.user_id == user_id)
        count_stmt = count_stmt.where(Task.user_id == user_id)
    stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)

    total = int((await db.execute(count_stmt)).scalar() or 0)
    rows = (await db.execute(stmt)).all()

    # 批量加载作品（已完成任务的弹窗预览要用）
    task_ids = [t.id for t, _ in rows]
    works_by_tid: dict[str, list[Work]] = {}
    if task_ids:
        works_result = await db.execute(
            select(Work).where(Work.task_id.in_(task_ids)).order_by(Work.id.asc())
        )
        for w in works_result.scalars().all():
            works_by_tid.setdefault(w.task_id, []).append(w)

    items: list[TaskInfo] = []
    for t, u in rows:
        works = works_by_tid.get(t.id, [])
        items.append(
            TaskInfo(
                id=t.id,
                user_id=t.user_id,
                username=u.username,
                task_type=t.task_type,
                model=t.model,
                prompt=t.prompt,
                params=json.loads(t.params) if t.params else {},
                num_images=t.num_images,
                status=t.status,
                queue_position=0,
                result_images=json.loads(t.result_images) if t.result_images else [],
                result_video=json.loads(t.result_video) if t.result_video else None,
                works=[
                    WorkBrief(
                        id=w.id,
                        media_type=w.media_type,
                        media_url=w.media_url,
                        is_public=w.is_public,
                    )
                    for w in works
                ],
                error_message=t.error_message or "",
                created_at=t.created_at,
                started_at=t.started_at,
                completed_at=t.completed_at,
            )
        )
    return TaskListResponse(items=items, total=total)


@router.post("/tasks/{task_id}/force-cancel")
async def force_cancel_task(
    task_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "任务不存在")
    if t.status in ("completed", "failed", "cancelled"):
        return {"success": True, "message": "任务已结束"}
    t.status = "cancelled"
    t.error_message = "被管理员强制取消"
    t.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True}
