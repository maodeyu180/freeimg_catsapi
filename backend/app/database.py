import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger("app.database")


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, future=True)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# (table, column, sql_type) — create_all 只能建新表，已有表加列靠这里
_ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    ("tasks", "start_frame", "TEXT"),
    ("works", "like_count", "INTEGER NOT NULL DEFAULT 0"),
    ("works", "view_count", "INTEGER NOT NULL DEFAULT 0"),
]


async def _apply_additive_migrations(conn) -> None:
    """对已有 SQLite 表做幂等的 ALTER TABLE ADD COLUMN。"""
    for table, column, sql_type in _ADDITIVE_COLUMNS:
        try:
            existing = await conn.execute(text(f"PRAGMA table_info({table})"))
            cols = {row[1] for row in existing.fetchall()}
            if column in cols:
                continue
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
            logger.info("migrated: added column %s.%s", table, column)
        except Exception:
            logger.exception("failed to add column %s.%s", table, column)


async def init_db():
    from app import models  # noqa: F401  ensure model registration

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_additive_migrations(conn)
