"""
Models API — status and management of AI model files.
"""
from fastapi import APIRouter
from services.model_manager import list_available_models

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/status")
async def get_model_status():
    """
    Returns availability and size of all AI model files.
    Used by frontend to show which models are loaded.
    """
    status = list_available_models()

    # Determine active PAVE model
    pave_priority = [
        "rdd2022_yolov8m",
        "pothole_seg_yolov8m",
        "pothole_seg_yolov8n",
        "pothole_finetune",
        "road_damage",
    ]
    active_pave = next(
        (name for name in pave_priority if status.get(name, {}).get("available")),
        "yolov8s_coco"
    )

    row_priority = ["row_road_objects_yolov8s", "yolov8m_coco"]
    active_row = next(
        (name for name in row_priority if status.get(name, {}).get("available")),
        "yolov8m_coco"
    )

    return {
        "models": status,
        "active_pave_model": active_pave,
        "active_row_model": active_row,
        "crack_seg_available": status.get("crack_seg_yolov8m", {}).get("available", False),
        "row_secondary_available": status.get("yolov8m_coco", {}).get("available", False)
                                   and status.get("row_road_objects_yolov8s", {}).get("available", False),
        "summary": {
            "total_available": sum(1 for m in status.values() if m["available"]),
            "total_models": len(status),
        }
    }
