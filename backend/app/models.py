from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    linuxdo_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(128), default="")
    avatar_url: Mapped[str] = mapped_column(String(512), default="")
    trust_level: Mapped[int] = mapped_column(Integer, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    # 单独配置的每日配额，null 表示使用全局默认
    daily_image_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_video_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(16))  # image | video
    model: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    # 用户参数（提交给上游的 params 原样），不含 base64 图片
    params: Mapped[str] = mapped_column(Text, default="{}")
    num_images: Mapped[int] = mapped_column(Integer, default=1)
    # 参考图 base64 数组，仅提交期间使用，完成后清空
    reference_images: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 视频首帧图 base64（可选），仅提交期间使用，完成后清空
    start_frame: Mapped[str | None] = mapped_column(Text, nullable=True)
    # queued | running | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    upstream_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_images: Mapped[str] = mapped_column(Text, default="[]")
    result_video: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class Work(Base):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), index=True)
    media_type: Mapped[str] = mapped_column(String(16))  # image | video
    media_url: Mapped[str] = mapped_column(String(1024))
    prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(64))
    # 完整参数（含 num_images、aspectRatio 等），用于"一键同款"
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # 互动计数（画廊排序用）
    like_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user = relationship("User")


class WorkLike(Base):
    __tablename__ = "work_likes"
    __table_args__ = (UniqueConstraint("work_id", "user_id", name="uq_work_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (UniqueConstraint("user_id", "usage_date", name="uq_daily_usage_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    usage_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD (QUOTA_TIMEZONE)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
