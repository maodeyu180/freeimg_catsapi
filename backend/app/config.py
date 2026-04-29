import json
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LinuxDo OAuth2
    LINUXDO_CLIENT_ID: str = ""
    LINUXDO_CLIENT_SECRET: str = ""
    LINUXDO_REDIRECT_URI: str = "http://localhost:5174/auth/callback"
    LINUXDO_AUTHORIZE_URL: str = "https://connect.linux.do/oauth2/authorize"
    LINUXDO_TOKEN_URL: str = "https://connect.linux.do/oauth2/token"
    LINUXDO_USER_URL: str = "https://connect.linux.do/api/user"

    # JWT
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7

    # 上游 catsapi.com
    CATSAPI_URL: str = "http://127.0.0.1:8000"
    CATSAPI_KEY: str = ""

    # App
    APP_NAME: str = "喵的公益生图"
    DEBUG: bool = False
    CORS_ORIGINS: str = '["http://localhost:5174"]'
    DATABASE_URL: str = "sqlite+aiosqlite:///./freeimage.db"

    # 访问控制
    MIN_TRUST_LEVEL: int = 1
    ADMIN_LINUXDO_IDS: str = ""

    # 并发 & 配额
    MAX_CONCURRENT_TASKS: int = 2
    DAILY_IMAGE_LIMIT: int = 20
    DAILY_VIDEO_LIMIT: int = 3
    QUOTA_TIMEZONE: str = "Asia/Shanghai"

    # Worker
    WORKER_POLL_INTERVAL_SECONDS: int = 3
    TASK_TIMEOUT_MINUTES: int = 15

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:5174"]

    @property
    def admin_linuxdo_ids_set(self) -> set[int]:
        ids: set[int] = set()
        for part in self.ADMIN_LINUXDO_IDS.split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
        return ids

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
