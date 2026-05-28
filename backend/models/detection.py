from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_name: str
    class_id: int

class FrameDetection(BaseModel):
    task_id: str
    video_id: str
    camera_type: str          # pave / row
    frame_number: int
    timestamp_sec: float
    chainage: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None
    survey_date: Optional[str] = None
    image_path: str           # relative path to saved frame
    detections: List[BoundingBox] = []
    ocr_data: Optional[Dict[str, Any]] = {}
    quality_score: Optional[float] = None   # frame quality 0-100
    is_duplicate: bool = False
    created_at: datetime = datetime.utcnow()

# PAVE specific metrics per segment
class PaveSegmentMetrics(BaseModel):
    task_id: str
    video_id: str
    chainage_from: float
    chainage_to: float
    iri: Optional[float] = None
    mpd: Optional[float] = None
    roughness_score: Optional[float] = None
    texture_score: Optional[float] = None
    lane_marking_width: Optional[float] = None
    alligator_cracks: int = 0
    longitudinal_cracks: int = 0
    transverse_cracks: int = 0
    potholes: int = 0
    patching: int = 0
    bleeding_ravelling: int = 0
    severity: str = "Good"    # Good/Fair/Poor/Very Poor
    condition_score: float = 5.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None

# ROW specific asset per detection
class RowAssetRecord(BaseModel):
    task_id: str
    video_id: str
    chainage: float
    asset_type: str
    sub_type: Optional[str] = None
    condition: Optional[str] = None
    side: Optional[str] = None      # LHS / RHS / Median
    remarks: Optional[str] = None
    confidence: float
    image_path: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    survey_date: Optional[str] = None
