from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    # MongoDB
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB: str = "road_identification"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "3mr.jackal@gmail.com"
    SMTP_PASSWORD: str = "njtr xvik usxm lqiv"
    EMAIL_FROM: str = "3mr.jackal@gmail.com"

    # Storage paths (relative names, resolved against BASE_DIR)
    UPLOAD_DIR: str = "uploads"
    DETECTED_IMAGES_DIR: str = "detected_images"
    MODELS_DIR: str = "ml_models"

    # HuggingFace
    HF_TOKEN: str = ""

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"

    # BASE_DIR is always the backend/ folder — not a pydantic field
    @property
    def BASE_DIR(self) -> Path:
        return Path(__file__).parent

    def get_upload_path(self) -> Path:
        p = self.BASE_DIR / self.UPLOAD_DIR
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_detected_images_path(self, task_id: str = "", camera: str = "") -> Path:
        p = self.BASE_DIR / self.DETECTED_IMAGES_DIR
        if task_id:
            p = p / task_id
        if camera:
            p = p / camera
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_models_path(self) -> Path:
        p = self.BASE_DIR / self.MODELS_DIR
        p.mkdir(parents=True, exist_ok=True)
        return p

settings = Settings()
