from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class CameraType(str, Enum):
    PAVE = "pave"
    ROW = "row"

class CaptureMode(str, Enum):
    INTERVAL = "interval"   # every N meters
    FPS = "fps"             # every N frames per second

class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    nh_number: Optional[str] = "NH-033"
    section_code: Optional[str] = ""
    survey_date: Optional[str] = ""
    notification_email: Optional[str] = ""

class TaskResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    nh_number: Optional[str] = ""
    section_code: Optional[str] = ""
    survey_date: Optional[str] = ""
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    videos: Optional[List[dict]] = []
    road_health_score: Optional[float] = None
    notification_email: Optional[str] = ""

class VideoCreate(BaseModel):
    task_id: str
    camera_type: CameraType
    capture_mode: CaptureMode = CaptureMode.INTERVAL
    capture_interval: float = 10.0   # meters or fps value
    notification_email: Optional[str] = ""
