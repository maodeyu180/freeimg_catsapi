import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import admin, auth, gallery, models, tasks
from app.services.task_worker import start_worker, stop_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_worker()
    logger.info("%s backend started", settings.APP_NAME)
    logger.info(
        "config: LinuxDo OAuth=%s, CATSAPI=%s (key=%s), admin_ids=%s",
        "configured" if settings.LINUXDO_CLIENT_ID else "MISSING!",
        settings.CATSAPI_URL,
        "configured" if settings.CATSAPI_KEY else "MISSING!",
        sorted(settings.admin_linuxdo_ids_set) or "none",
    )
    try:
        yield
    finally:
        await stop_worker()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan, docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(gallery.router, prefix="/api/gallery", tags=["gallery"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"ok": True, "app": settings.APP_NAME}
