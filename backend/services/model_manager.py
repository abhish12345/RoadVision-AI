"""
Model Manager — ALL models integrated in parallel automatically.

PAVE Camera — runs ALL 4 models in parallel, merges results:
  1. rdd2022_yolov8m.pt      D00/D10/D20/D40 (longitudinal/transverse/alligator/pothole)
  2. crack_seg_yolov8m.pt    crack (segmentation, high accuracy for thin cracks)
  3. pothole_seg_yolov8m.pt  pothole (segmentation, best for pothole shape)
  4. pothole_finetune.pt     pothole (fine-tuned, catches missed potholes)

ROW Camera — runs ALL 2 models in parallel, merges results:
  1. row_road_objects_yolov8s.pt  traffic sign, traffic light, vehicles, pedestrian
  2. yolov8m.pt (COCO 80)        stop sign, bench, person, car, truck + 74 more

False positive filter applied after merge:
  - Removes white road markings (lane lines, zebra crossings) detected as cracks
  - Removes duplicate detections (NMS across models)
"""
import shutil
import logging
from pathlib import Path
from typing import List, Optional
from ultralytics import YOLO

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "ml_models"
MODELS_DIR.mkdir(exist_ok=True)

# ── PAVE class mapping ────────────────────────────────────────────────────────
PAVE_CLASS_MAP = {
    # RDD2022 codes
    "D00": "longitudinal_crack",
    "D10": "transverse_crack",
    "D20": "alligator_crack",
    "D40": "pothole",
    "D43": "pothole",
    "D44": "pothole",
    # Plain English
    "longitudinal crack":  "longitudinal_crack",
    "transverse crack":    "transverse_crack",
    "alligator crack":     "alligator_crack",
    "crocodile crack":     "alligator_crack",
    "pothole":             "pothole",
    "crack":               "alligator_crack",
    "patching":            "patching",
    "patch":               "patching",
    "bleeding":            "bleeding_ravelling",
    "ravelling":           "bleeding_ravelling",
    "raveling":            "bleeding_ravelling",
    "rutting":             "rutting",
    "lane marking":        "lane_marking",
    "lane_marking":        "lane_marking",
}

# ── ROW class mapping ─────────────────────────────────────────────────────────
ROW_ASSET_MAP = {
    # row_road_objects model
    "traffic sign":   "road_sign",
    "traffic light":  "road_sign",
    "pedestrian":     "encroachment",
    "rider":          "encroachment",
    "bicycle":        "encroachment",
    "motorcycle":     "vehicle",
    "car":            "vehicle",
    "bus":            "vehicle",
    "truck":          "vehicle",
    "train":          "vehicle",
    # COCO classes
    "stop sign":      "road_sign",
    "fire hydrant":   "roadside_feature",
    "bench":          "wayside_amenity",
    "person":         "encroachment",
    "parking meter":  "roadside_feature",
    # Custom road-survey classes
    "road_sign":      "road_sign",
    "road sign":      "road_sign",
    "sign":           "road_sign",
    "crash_barrier":  "crash_barrier",
    "crash barrier":  "crash_barrier",
    "guard rail":     "crash_barrier",
    "guardrail":      "crash_barrier",
    "barrier":        "crash_barrier",
    "km_stone":       "km_stone",
    "km stone":       "km_stone",
    "milestone":      "km_stone",
    "street_light":   "street_light",
    "street light":   "street_light",
    "lamp post":      "street_light",
    "utility pole":   "utility_lines",
    "power pole":     "utility_lines",
    "pole":           "utility_lines",
    "bus_shelter":    "wayside_amenity",
    "bus shelter":    "wayside_amenity",
    "bus stop":       "wayside_amenity",
    "culvert":        "culvert_bridge",
    "bridge":         "culvert_bridge",
    "drain":          "drain",
    "drainage":       "drain",
    "retaining_wall": "retaining_wall",
    "retaining wall": "retaining_wall",
    "median":         "median_divider",
    "divider":        "median_divider",
    "service_road":   "service_road",
    "service road":   "service_road",
    "encroachment":   "encroachment",
    "hazard_marker":  "hazard_marker",
    "hazard marker":  "hazard_marker",
    "delineator":     "hazard_marker",
}

# ── COCO classes to SKIP for ROW (irrelevant to road survey) ─────────────────
ROW_COCO_SKIP = {
    "airplane", "boat", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana",
    "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
    "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table",
    "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock",
    "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
}

# ── Model cache (loaded once, reused) ────────────────────────────────────────
_model_cache = {}

def _load(filename: str) -> Optional[YOLO]:
    """Load model from ml_models/, return None if not found."""
    if filename in _model_cache:
        return _model_cache[filename]
    path = MODELS_DIR / filename
    if not path.exists():
        logger.warning(f"Model not found: {filename}")
        return None
    logger.info(f"Loading model: {filename}")
    model = YOLO(str(path))
    _model_cache[filename] = model
    return model


def get_all_pave_models() -> List[YOLO]:
    """
    Return ALL available PAVE models for parallel detection.
    Order: best accuracy first.
    """
    candidates = [
        "rdd2022_yolov8m.pt",       # D00/D10/D20/D40 — best multi-class
        "crack_seg_yolov8m.pt",     # crack segmentation — best for thin cracks
        "pothole_seg_yolov8m.pt",   # pothole segmentation — best for pothole shape
        "pothole_finetune_yolov8.pt", # pothole fine-tuned — catches missed potholes
    ]
    models = []
    for f in candidates:
        m = _load(f)
        if m is not None:
            models.append((f, m))
    logger.info(f"PAVE models loaded: {[f for f,_ in models]}")
    return models


def get_all_row_models() -> List[YOLO]:
    """
    Return ALL available ROW models for parallel detection.
    """
    candidates = [
        "row_road_objects_yolov8s.pt",  # traffic sign, light, vehicles (10 classes)
        "yolov8m.pt",                   # COCO 80 classes — general road assets
    ]
    models = []
    for f in candidates:
        m = _load(f)
        if m is not None:
            models.append((f, m))
    logger.info(f"ROW models loaded: {[f for f,_ in models]}")
    return models


def normalize_pave_class(class_name: str) -> str:
    """Map raw YOLO class → standard PAVE defect type."""
    key = class_name.lower().strip()
    return PAVE_CLASS_MAP.get(key, PAVE_CLASS_MAP.get(class_name, "other_defect"))


def normalize_row_class(class_name: str) -> str:
    """Map raw YOLO class → standard ROW asset type."""
    key = class_name.lower().strip()
    # Skip irrelevant COCO classes
    if key in ROW_COCO_SKIP:
        return "skip"
    return ROW_ASSET_MAP.get(key, ROW_ASSET_MAP.get(class_name, "roadside_feature"))


def is_row_class_relevant(class_name: str) -> bool:
    """Return True if this ROW detection is relevant to road survey."""
    return normalize_row_class(class_name) != "skip"


# Keep these for backward compatibility
def get_pave_model() -> YOLO:
    """Get primary PAVE model (RDD2022)."""
    return _load("rdd2022_yolov8m.pt") or _load("yolov8s.pt")

def get_crack_seg_model() -> Optional[YOLO]:
    return _load("crack_seg_yolov8m.pt")

def get_row_model() -> YOLO:
    return _load("row_road_objects_yolov8s.pt") or _load("yolov8m.pt")

def get_row_secondary_model() -> Optional[YOLO]:
    if _load("row_road_objects_yolov8s.pt"):
        return _load("yolov8m.pt")
    return None


def list_available_models() -> dict:
    """Return status of all model files."""
    models = {
        # PAVE
        "rdd2022_yolov8m":           "rdd2022_yolov8m.pt",
        "crack_seg_yolov8m":         "crack_seg_yolov8m.pt",
        "pothole_seg_yolov8m":       "pothole_seg_yolov8m.pt",
        "pothole_seg_yolov8n":       "pothole_seg_yolov8n.pt",
        "pothole_finetune":          "pothole_finetune_yolov8.pt",
        "road_damage":               "road_damage_yolov8.pt",
        # ROW
        "row_road_objects_yolov8s":  "row_road_objects_yolov8s.pt",
        "yolov8m_coco":              "yolov8m.pt",
        # Base
        "yolov8n_coco":              "yolov8n.pt",
        "yolov8s_coco":              "yolov8s.pt",
    }
    status = {}
    for name, filename in models.items():
        path = MODELS_DIR / filename
        if path.exists():
            size_mb = path.stat().st_size // 1024 // 1024
            status[name] = {"available": True, "file": filename, "size_mb": size_mb}
        else:
            status[name] = {"available": False, "file": filename}
    return status
