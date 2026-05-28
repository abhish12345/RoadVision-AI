"""
Road Identification System — FastAPI Backend
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import connect_db, close_db
from config import settings
from api.tasks import router as tasks_router
from api.videos import router as videos_router
from api.images import router as images_router
from api.reports import router as reports_router
from api.models import router as models_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_db()
    # Ensure directories exist
    for d in [settings.UPLOAD_DIR, settings.DETECTED_IMAGES_DIR, settings.MODELS_DIR, "reports"]:
        Path(settings.BASE_DIR / d).mkdir(parents=True, exist_ok=True)
    logger.info("Road Identification System started")
    yield
    # Shutdown
    await close_db()
    logger.info("Road Identification System stopped")


app = FastAPI(
    title="Road Identification System",
    description="AI-powered road survey analysis system for PAVE and ROW cameras",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(tasks_router)
app.include_router(videos_router)
app.include_router(images_router)
app.include_router(reports_router)
app.include_router(models_router)

# Serve detected images as static files
detected_dir = Path(settings.BASE_DIR) / settings.DETECTED_IMAGES_DIR
detected_dir.mkdir(exist_ok=True)
app.mount("/detected", StaticFiles(directory=str(detected_dir)), name="detected")

# Serve reports
reports_dir = Path(settings.BASE_DIR) / "reports"
reports_dir.mkdir(exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(reports_dir)), name="reports")


@app.get("/")
async def root():
    return {
        "name": "Road Identification System API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    from database import db
    try:
        await db.command("ping")
        mongo_status = "connected"
    except Exception:
        mongo_status = "disconnected"

    return {
        "status": "healthy",
        "mongodb": mongo_status,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level="info",
    )
