"""
封装对上游 cataspi.com 的 HTTP 调用。
以内部账号的 API Key 认证，所有 freeimage_linuxdo 的用户任务都以这一个账号提交。
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger("app.ldc_client")

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)


class LdcError(Exception):
    pass


def _headers() -> dict:
    if not settings.CATSAPI_KEY:
        raise LdcError("CATSAPI_KEY 未配置，无法调用上游服务")
    return {
        "Authorization": f"Bearer {settings.CATSAPI_KEY}",
        "Content-Type": "application/json",
    }


async def create_task(
    *,
    model: str,
    prompt: str,
    task_type: str,
    params: dict,
    num_images: int,
    reference_images: list[dict] | None = None,
    start_frame: dict | None = None,
) -> str:
    """创建上游任务，返回上游 task_id。"""
    body: dict = {
        "model": model,
        "prompt": prompt,
        "task_type": task_type,
        "params": params,
        "num_images": num_images,
    }
    if task_type == "image" and reference_images:
        body["images"] = reference_images
    # 视频：可选首帧图（图生视频），通过 files.startFrame 传给上游
    if task_type == "video" and start_frame:
        body["files"] = {"startFrame": start_frame}

    url = settings.CATSAPI_URL.rstrip("/") + "/api/tasks"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=body, headers=_headers())
        if resp.status_code >= 400:
            detail = _safe_detail(resp)
            logger.warning("ldc create_task failed: status=%s detail=%s", resp.status_code, detail)
            raise LdcError(f"上游创建任务失败: {detail}")
        data = resp.json()
        tid = data.get("id") or data.get("task_id")
        if not tid:
            raise LdcError(f"上游未返回任务 ID: {data}")
        return str(tid)


async def get_task(upstream_task_id: str) -> dict:
    """查询上游任务详情。"""
    url = settings.CATSAPI_URL.rstrip("/") + f"/api/tasks/{upstream_task_id}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_headers())
        if resp.status_code >= 400:
            detail = _safe_detail(resp)
            raise LdcError(f"上游查询任务失败: {detail}")
        return resp.json()


def _safe_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            return str(data.get("detail") or data)
        return str(data)
    except Exception:
        return resp.text[:500]
