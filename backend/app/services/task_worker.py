"""
任务队列 worker（方案 B：自己维护全局 2 并发）。

规则：
- 全局 MAX_CONCURRENT_TASKS 个运行中任务上限。
- 每个用户同时只允许一个活跃任务（queued 或 running）。
- worker 周期性扫 queued 任务，按 created_at 升序，若运行中数未达上限则启动，
  并在同一个 asyncio 任务里轮询上游直到完成。
- 任务超时 TASK_TIMEOUT_MINUTES 后标记失败。
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SessionLocal
from app.models import Task, Work
from app.services import ldc_client

logger = logging.getLogger("app.task_worker")

_worker_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
# 当前正在处理的任务 id -> asyncio.Task
_running: dict[str, asyncio.Task] = {}
# 上游报"并发已达上限"时的冷却时刻；在此之前 scheduler 不再尝试新建
_upstream_busy_until: datetime | None = None
# 上游并发上限错误触发的冷却时长（秒）
_UPSTREAM_BUSY_COOLDOWN_SECONDS = 10


def _is_upstream_busy_error(msg: str) -> bool:
    """识别上游返回的"并发已达上限"类瞬态错误。"""
    if not msg:
        return False
    keywords = ("已达上限", "并发", "concurrent", "rate limit", "too many", "任务数")
    low = msg.lower()
    return any(k.lower() in low for k in keywords)


def _set_upstream_busy():
    global _upstream_busy_until
    _upstream_busy_until = datetime.now(timezone.utc) + timedelta(seconds=_UPSTREAM_BUSY_COOLDOWN_SECONDS)


def _is_upstream_cooling_down() -> bool:
    return _upstream_busy_until is not None and datetime.now(timezone.utc) < _upstream_busy_until


def start_worker():
    global _worker_task, _stop_event
    if _worker_task is not None:
        return
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_startup_then_loop())
    logger.info("task worker started, max_concurrent=%d", settings.MAX_CONCURRENT_TASKS)


async def _startup_then_loop():
    await _recover_orphaned()
    await _scheduler_loop()


async def _recover_orphaned():
    """进程重启后恢复悬空的 running 任务：
    - 已提交到上游（有 upstream_task_id）→ 保持 running，直接恢复轮询，避免重复提交把上游槽位吃满。
    - 还没提交到上游（无 upstream_task_id）→ 回退到 queued，下一轮 tick 正常调度。
    """
    to_resume: list[str] = []
    reverted = 0
    async with SessionLocal() as db:
        result = await db.execute(select(Task).where(Task.status == "running"))
        rows = list(result.scalars().all())
        for t in rows:
            if t.upstream_task_id:
                to_resume.append(t.id)
            else:
                t.status = "queued"
                t.started_at = None
                reverted += 1
        if rows:
            await db.commit()

    for tid in to_resume:
        _running[tid] = asyncio.create_task(_process_task(tid))

    if reverted:
        logger.info("reverted %d orphaned running task(s) (no upstream_id) back to queued", reverted)
    if to_resume:
        logger.info("resumed polling for %d running task(s) with existing upstream_id", len(to_resume))


async def stop_worker():
    global _worker_task, _stop_event
    if _stop_event:
        _stop_event.set()
    if _worker_task:
        try:
            await asyncio.wait_for(_worker_task, timeout=5)
        except asyncio.TimeoutError:
            _worker_task.cancel()
    # 取消所有运行中任务
    for t in list(_running.values()):
        t.cancel()
    _worker_task = None
    _stop_event = None


async def _scheduler_loop():
    assert _stop_event is not None
    while not _stop_event.is_set():
        try:
            await _tick()
        except Exception:
            logger.exception("scheduler tick failed")
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=settings.WORKER_POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass


async def _tick():
    # 清掉已结束的 asyncio 任务引用
    done = [tid for tid, t in _running.items() if t.done()]
    for tid in done:
        _running.pop(tid, None)

    if len(_running) >= settings.MAX_CONCURRENT_TASKS:
        return

    # 上游并发满过的冷却期内，不再尝试提交新任务
    if _is_upstream_cooling_down():
        return

    async with SessionLocal() as db:
        slots = settings.MAX_CONCURRENT_TASKS - len(_running)
        result = await db.execute(
            select(Task)
            .where(Task.status == "queued")
            .order_by(Task.created_at.asc())
            .limit(slots + 5)  # 多拿一点，避开已被挑走的
        )
        candidates = result.scalars().all()
        for task in candidates:
            if len(_running) >= settings.MAX_CONCURRENT_TASKS:
                break
            if task.id in _running:
                continue
            # 启动
            task.status = "running"
            task.started_at = datetime.now(timezone.utc)
            await db.commit()
            _running[task.id] = asyncio.create_task(_process_task(task.id))
            logger.info("[task=%s] started (running=%d)", task.id, len(_running))


async def _process_task(task_id: str):
    """读取任务、调上游、轮询直到完成，最终更新 DB。

    重启恢复场景：如果 DB 里已有 upstream_task_id，跳过提交直接续命轮询，
    避免把上游槽位重复占用（触发 400"并发已达上限"）。
    """
    try:
        # 1) 读任务
        async with SessionLocal() as db:
            task = await _get_task(db, task_id)
            if task is None or task.status != "running":
                return
            model = task.model
            task_type = task.task_type
            prompt = task.prompt
            num_images = task.num_images
            params = json.loads(task.params) if task.params else {}
            ref_images = json.loads(task.reference_images) if task.reference_images else None
            start_frame = json.loads(task.start_frame) if task.start_frame else None
            upstream_id = task.upstream_task_id  # 可能已有（重启恢复）

        # 2) 提交上游（没有 upstream_id 才提交）
        if not upstream_id:
            try:
                upstream_id = await ldc_client.create_task(
                    model=model,
                    prompt=prompt,
                    task_type=task_type,
                    params=params,
                    num_images=num_images,
                    reference_images=ref_images,
                    start_frame=start_frame,
                )
            except ldc_client.LdcError as e:
                msg = str(e)
                # 上游并发已满：当作瞬态错误，回退到 queued 等下次重试，并设置冷却
                if _is_upstream_busy_error(msg):
                    _set_upstream_busy()
                    await _requeue(task_id)
                    logger.info("[task=%s] upstream busy, requeued: %s", task_id, msg)
                    return
                await _mark_failed(task_id, f"上游提交失败: {e}")
                return

            # 清理 base64 并保存 upstream_id
            async with SessionLocal() as db:
                task = await _get_task(db, task_id)
                if task is None:
                    return
                # 已被取消
                if task.status == "cancelled":
                    return
                task.upstream_task_id = upstream_id
                task.reference_images = None
                task.start_frame = None
                await db.commit()

        # 3) 轮询上游
        deadline = datetime.now(timezone.utc) + timedelta(minutes=settings.TASK_TIMEOUT_MINUTES)
        while datetime.now(timezone.utc) < deadline:
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
            # 检查是否被取消
            async with SessionLocal() as db:
                task = await _get_task(db, task_id)
                if task is None or task.status == "cancelled":
                    return

            try:
                info = await ldc_client.get_task(upstream_id)
            except ldc_client.LdcError as e:
                logger.warning("[task=%s] poll upstream failed: %s", task_id, e)
                continue

            status = info.get("status")
            if status == "completed":
                await _mark_completed(task_id, info)
                return
            if status == "failed":
                err = info.get("error_message") or "上游失败"
                await _mark_failed(task_id, err)
                return
            # queued / running → 继续等

        await _mark_failed(task_id, "任务超时")

    except Exception as e:
        logger.exception("[task=%s] worker crashed", task_id)
        await _mark_failed(task_id, f"内部错误: {e}")


async def _get_task(db: AsyncSession, task_id: str) -> Task | None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def _mark_failed(task_id: str, err: str):
    async with SessionLocal() as db:
        task = await _get_task(db, task_id)
        if task is None or task.status in ("completed", "failed", "cancelled"):
            return
        task.status = "failed"
        task.error_message = err[:1000]
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("[task=%s] failed: %s", task_id, err)


async def _requeue(task_id: str):
    """把任务从 running 回退到 queued，供瞬态错误重试使用。"""
    async with SessionLocal() as db:
        task = await _get_task(db, task_id)
        if task is None or task.status != "running":
            return
        task.status = "queued"
        task.started_at = None
        await db.commit()


async def _mark_completed(task_id: str, info: dict):
    async with SessionLocal() as db:
        task = await _get_task(db, task_id)
        if task is None or task.status in ("completed", "failed", "cancelled"):
            return
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)

        if task.task_type == "image":
            image_urls = info.get("result_images") or []
            task.result_images = json.dumps(image_urls)
            for url in image_urls:
                db.add(
                    Work(
                        user_id=task.user_id,
                        task_id=task.id,
                        media_type="image",
                        media_url=url,
                        prompt=task.prompt,
                        model=task.model,
                        params_json=task.params,
                        is_public=False,
                    )
                )
        else:
            video = info.get("result_video") or {}
            # result_video 可能为 {"url": "..."} 或直接 "..." 字符串，兼容处理
            video_url = video.get("url") if isinstance(video, dict) else str(video)
            task.result_video = json.dumps({"url": video_url} if video_url else {})
            if video_url:
                db.add(
                    Work(
                        user_id=task.user_id,
                        task_id=task.id,
                        media_type="video",
                        media_url=video_url,
                        prompt=task.prompt,
                        model=task.model,
                        params_json=task.params,
                        is_public=False,
                    )
                )
        await db.commit()
        logger.info("[task=%s] completed", task_id)
