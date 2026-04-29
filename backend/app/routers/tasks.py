import base64
import binascii
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.model_config import MODELS, validate_and_normalize_params
from app.models import Task, User, Work
from app.schemas import TaskCreateRequest, TaskInfo, TaskListResponse, WorkBrief
from app.services.quota import check_quota, consume

router = APIRouter()

MAX_REFERENCE_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB/张


def _validate_base64(b64: str, field: str) -> int:
    """返回解码后字节数；失败抛 HTTPException。"""
    raw = b64.strip()
    # 容忍 dataURL 前缀
    if raw.startswith("data:"):
        idx = raw.find(",")
        if idx < 0:
            raise HTTPException(400, f"{field}: dataURL 格式错误")
        raw = raw[idx + 1:]
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, f"{field}: base64 无法解码")
    if len(data) > MAX_REFERENCE_IMAGE_BYTES:
        raise HTTPException(400, f"{field}: 单张图片不得超过 5MB")
    return len(data)


def _task_to_info(
    task: Task,
    queue_position: int = 0,
    username: str = "",
    works: list[Work] | None = None,
) -> TaskInfo:
    return TaskInfo(
        id=task.id,
        user_id=task.user_id,
        username=username,
        task_type=task.task_type,
        model=task.model,
        prompt=task.prompt,
        params=json.loads(task.params) if task.params else {},
        num_images=task.num_images,
        status=task.status,
        queue_position=queue_position,
        result_images=json.loads(task.result_images) if task.result_images else [],
        result_video=json.loads(task.result_video) if task.result_video else None,
        works=[
            WorkBrief(id=w.id, media_type=w.media_type, media_url=w.media_url, is_public=w.is_public)
            for w in (works or [])
        ],
        error_message=task.error_message or "",
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


async def _load_works_by_task_ids(db: AsyncSession, task_ids: list[str]) -> dict[str, list[Work]]:
    """批量加载 task_id -> [Work]，用于 TaskInfo.works 字段。"""
    if not task_ids:
        return {}
    result = await db.execute(
        select(Work).where(Work.task_id.in_(task_ids)).order_by(Work.id.asc())
    )
    bucket: dict[str, list[Work]] = {}
    for w in result.scalars().all():
        bucket.setdefault(w.task_id, []).append(w)
    return bucket


async def _queue_position(db: AsyncSession, task: Task) -> int:
    """对 queued 任务计算排队位次（1 = 下一个将被执行）。"""
    if task.status != "queued":
        return 0
    result = await db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.status == "queued", Task.created_at <= task.created_at, Task.id != task.id)
    )
    ahead = result.scalar() or 0
    return int(ahead) + 1


@router.post("", response_model=TaskInfo)
async def create_task(
    body: TaskCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = MODELS.get(body.model)
    if not cfg:
        raise HTTPException(400, f"不支持的模型: {body.model}")

    task_type = cfg["task_type"]

    # 每用户同时只能有一个活跃任务
    result = await db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.user_id == user.id, Task.status.in_(["queued", "running"]))
    )
    if (result.scalar() or 0) >= 1:
        raise HTTPException(429, "你当前已有任务在运行或排队中，完成后再提交新任务")

    # 每日配额
    try:
        await check_quota(db, user, task_type)
    except ValueError as e:
        raise HTTPException(429, str(e))

    # 参数校验
    try:
        params = validate_and_normalize_params(body.model, body.params, body.num_images)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not body.prompt.strip():
        raise HTTPException(400, "提示词不能为空")
    if len(body.prompt) > 4000:
        raise HTTPException(400, "提示词过长（上限 4000 字符）")

    # 参考图校验
    max_refs = cfg["max_reference_images"]
    if len(body.reference_images) > max_refs:
        raise HTTPException(400, f"该模型最多上传 {max_refs} 张参考图")
    ref_list = None
    if body.reference_images:
        ref_list = []
        for i, img in enumerate(body.reference_images):
            _validate_base64(img.base64, f"reference_images[{i}].base64")
            if not img.name or not img.name.strip():
                raise HTTPException(400, f"reference_images[{i}].name 不能为空")
            ref_list.append({"base64": img.base64, "name": img.name})

    # 视频首帧图校验（可选，仅 video 任务支持）
    start_frame_json = None
    if body.start_frame is not None:
        if task_type != "video":
            raise HTTPException(400, "仅视频模型支持首帧图")
        _validate_base64(body.start_frame.base64, "start_frame.base64")
        if not body.start_frame.name or not body.start_frame.name.strip():
            raise HTTPException(400, "start_frame.name 不能为空")
        start_frame_json = json.dumps(
            {"base64": body.start_frame.base64, "name": body.start_frame.name},
            ensure_ascii=False,
        )

    # 扣配额（即使后续失败也不退还，避免刷配额；保持简单）
    await consume(db, user.id, task_type)

    task = Task(
        id=str(uuid.uuid4()),
        user_id=user.id,
        task_type=task_type,
        model=body.model,
        prompt=body.prompt.strip(),
        params=json.dumps(params, ensure_ascii=False),
        num_images=body.num_images,
        reference_images=json.dumps(ref_list, ensure_ascii=False) if ref_list else None,
        start_frame=start_frame_json,
        status="queued",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    pos = await _queue_position(db, task)
    return _task_to_info(task, queue_position=pos, username=user.username)


@router.get("", response_model=TaskListResponse)
async def list_my_tasks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await db.execute(
        select(Task)
        .where(Task.user_id == user.id)
        .order_by(Task.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    tasks = list(result.scalars().all())

    total_result = await db.execute(
        select(func.count()).select_from(Task).where(Task.user_id == user.id)
    )
    total = int(total_result.scalar() or 0)

    works_by_tid = await _load_works_by_task_ids(db, [t.id for t in tasks])
    items = []
    for t in tasks:
        pos = await _queue_position(db, t)
        items.append(
            _task_to_info(
                t,
                queue_position=pos,
                username=user.username,
                works=works_by_tid.get(t.id, []),
            )
        )
    return TaskListResponse(items=items, total=total)


@router.get("/{task_id}", response_model=TaskInfo)
async def get_my_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    t = result.scalar_one_or_none()
    if not t or (t.user_id != user.id and not user.is_admin):
        raise HTTPException(404, "任务不存在")
    pos = await _queue_position(db, t)
    works_by_tid = await _load_works_by_task_ids(db, [t.id])
    return _task_to_info(
        t, queue_position=pos, username=user.username, works=works_by_tid.get(t.id, [])
    )


@router.post("/{task_id}/cancel", response_model=TaskInfo)
async def cancel_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    t = result.scalar_one_or_none()
    if not t or t.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    if t.status != "queued":
        raise HTTPException(400, "只能取消排队中的任务（运行中的任务已交给上游，无法中断）")
    t.status = "cancelled"
    t.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(t)
    return _task_to_info(t, queue_position=0, username=user.username)
