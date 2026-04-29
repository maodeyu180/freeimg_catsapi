from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Auth ──

class AuthLoginResponse(BaseModel):
    url: str


class AuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


class UserInfo(BaseModel):
    id: int
    linuxdo_id: int
    username: str
    avatar_url: str
    trust_level: int
    is_admin: bool
    is_banned: bool
    daily_image_limit: int
    daily_video_limit: int
    used_today_images: int
    used_today_videos: int


class AuthCallbackResponse(BaseModel):
    token: str
    user: UserInfo


# ── Tasks ──

class ImageInput(BaseModel):
    base64: str
    name: str


class TaskCreateRequest(BaseModel):
    model: str
    prompt: str
    num_images: int = Field(default=1, ge=1, le=2)
    params: dict = Field(default_factory=dict)
    reference_images: list[ImageInput] = Field(default_factory=list)
    # 仅视频模型使用：可选的首帧图（图生视频）
    start_frame: Optional[ImageInput] = None


class WorkBrief(BaseModel):
    id: int
    media_type: str  # image | video
    media_url: str
    is_public: bool


class TaskInfo(BaseModel):
    id: str
    user_id: int
    username: str = ""
    task_type: str
    model: str
    prompt: str
    params: dict
    num_images: int
    status: str
    queue_position: int = 0
    result_images: list[str] = []
    result_video: Optional[dict] = None
    # 该任务产出的作品（任务完成后有值，前端用来显示"推到画廊"按钮）
    works: list[WorkBrief] = []
    error_message: str = ""
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskListResponse(BaseModel):
    items: list[TaskInfo]
    total: int


# ── Gallery / Works ──

class WorkInfo(BaseModel):
    id: int
    user_id: int
    username: str = ""
    user_avatar: str = ""
    task_id: str
    media_type: str
    media_url: str
    prompt: str
    model: str
    params: dict = {}
    num_images: int = 1
    is_public: bool
    is_mine: bool = False
    like_count: int = 0
    view_count: int = 0
    liked_by_me: bool = False
    created_at: datetime


class GalleryResponse(BaseModel):
    items: list[WorkInfo]
    total: int


class PublishRequest(BaseModel):
    is_public: bool


class LikeResponse(BaseModel):
    work_id: int
    liked_by_me: bool
    like_count: int


class ViewResponse(BaseModel):
    work_id: int
    view_count: int


# ── Admin ──

class AdminUserInfo(BaseModel):
    id: int
    linuxdo_id: int
    username: str
    avatar_url: str
    trust_level: int
    is_admin: bool
    is_banned: bool
    daily_image_limit: int
    daily_video_limit: int
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserInfo]
    total: int


class AdminUpdateUserRequest(BaseModel):
    is_banned: Optional[bool] = None
    daily_image_limit: Optional[int] = Field(default=None, ge=0, le=1000)
    daily_video_limit: Optional[int] = Field(default=None, ge=0, le=1000)
