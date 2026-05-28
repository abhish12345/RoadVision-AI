"""
Image gallery and serving API routes.
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from bson import ObjectId

from database import get_db
from config import settings

router = APIRouter(prefix="/api/images", tags=["images"])
logger = logging.getLogger(__name__)


@router.get("/task/{task_id}")
async def get_task_images(
    task_id: str,
    camera_type: Optional[str] = None,
    class_filter: Optional[str] = None,
    min_confidence: float = 0.0,
    chainage_from: Optional[float] = None,
    chainage_to: Optional[float] = None,
    annotated_only: bool = False,
    skip: int = 0,
    limit: int = 50,
):
    """
    Get detected images for a task with filtering.
    Returns image metadata + URLs.
    """
    db = get_db()
    query = {"task_id": task_id}

    if camera_type:
        query["camera_type"] = camera_type
    if chainage_from is not None:
        query["chainage"] = {"$gte": chainage_from}
    if chainage_to is not None:
        query.setdefault("chainage", {})["$lte"] = chainage_to
    if annotated_only:
        query["annotated_path"] = {"$ne": None}

    # Only frames that have detections
    if class_filter or min_confidence > 0 or annotated_only:
        query["detections.0"] = {"$exists": True}

    cursor = db.detections.find(query).sort("frame_number", 1).skip(skip).limit(limit)
    images = []
    async for doc in cursor:
        # Filter detections
        dets = doc.get('detections', [])
        if class_filter:
            dets = [d for d in dets if d.get('normalized_class') == class_filter]
        if min_confidence > 0:
            dets = [d for d in dets if d.get('confidence', 0) >= min_confidence]

        if (class_filter or min_confidence > 0) and not dets:
            continue

        img_path = doc.get('image_path', '')
        ann_path = doc.get('annotated_path')

        images.append({
            "id": str(doc['_id']),
            "frame_number": doc.get('frame_number'),
            "timestamp_sec": doc.get('timestamp_sec'),
            "chainage": doc.get('chainage'),
            "latitude": doc.get('latitude'),
            "longitude": doc.get('longitude'),
            "speed": doc.get('speed'),
            "survey_date": doc.get('survey_date'),
            "camera_type": doc.get('camera_type'),
            "quality_score": doc.get('quality_score'),
            "detections": dets,
            "detection_count": len(dets),
            "image_url": f"/api/images/serve/{str(doc['_id'])}",
            "annotated_url": f"/api/images/serve/{str(doc['_id'])}?annotated=true" if ann_path else None,
            "has_annotated": ann_path is not None,
        })

    total = await db.detections.count_documents(query)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "images": images,
    }


@router.get("/serve/{detection_id}")
async def serve_image(detection_id: str, annotated: bool = False):
    """Serve a detected frame image."""
    db = get_db()
    try:
        doc = await db.detections.find_one({"_id": ObjectId(detection_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid detection ID")
    if not doc:
        raise HTTPException(status_code=404, detail="Detection not found")

    if annotated and doc.get('annotated_path'):
        img_path = doc['annotated_path']
    else:
        img_path = doc.get('image_path', '')

    if not img_path or not Path(img_path).exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(img_path, media_type="image/jpeg")


@router.get("/task/{task_id}/map-data")
async def get_map_data(task_id: str, camera_type: Optional[str] = None):
    """
    Get GPS coordinates + detection data for map visualization.
    Returns lightweight data suitable for Leaflet markers.
    """
    db = get_db()
    query = {
        "task_id": task_id,
        "latitude": {"$ne": None},
        "longitude": {"$ne": None},
    }
    if camera_type:
        query["camera_type"] = camera_type

    # Only get frames with detections for map markers
    query["detections.0"] = {"$exists": True}

    cursor = db.detections.find(
        query,
        {"latitude": 1, "longitude": 1, "chainage": 1, "detections": 1,
         "camera_type": 1, "image_path": 1, "frame_number": 1, "quality_score": 1}
    ).limit(2000)

    markers = []
    async for doc in cursor:
        dets = doc.get('detections', [])
        if not dets:
            continue
        # Get primary detection (highest confidence)
        primary = max(dets, key=lambda d: d.get('confidence', 0))
        markers.append({
            "id": str(doc['_id']),
            "lat": doc['latitude'],
            "lon": doc['longitude'],
            "chainage": doc.get('chainage'),
            "camera_type": doc.get('camera_type'),
            "primary_class": primary.get('normalized_class', primary.get('class_name')),
            "confidence": round(primary.get('confidence', 0) * 100, 1),
            "detection_count": len(dets),
            "frame_number": doc.get('frame_number'),
            "image_url": f"/api/images/serve/{str(doc['_id'])}",
            "annotated_url": f"/api/images/serve/{str(doc['_id'])}?annotated=true",
        })

    return {"markers": markers, "total": len(markers)}


@router.get("/task/{task_id}/heatmap")
async def get_heatmap_data(task_id: str):
    """
    Get chainage-wise condition data for heatmap visualization.
    Returns segments with severity scores.
    """
    db = get_db()
    pipeline = [
        {"$match": {"task_id": task_id, "chainage": {"$ne": None}}},
        {"$group": {
            "_id": {"$round": [{"$multiply": ["$chainage", 10]}, 0]},
            "detection_count": {"$sum": {"$size": "$detections"}},
            "frame_count": {"$sum": 1},
            "avg_lat": {"$avg": "$latitude"},
            "avg_lon": {"$avg": "$longitude"},
            "avg_quality": {"$avg": "$quality_score"},
        }},
        {"$sort": {"_id": 1}}
    ]

    segments = []
    async for doc in db.detections.aggregate(pipeline):
        ch = doc['_id'] / 10
        det_count = doc['detection_count']
        # Severity: 0=good, 1=fair, 2=poor, 3=very poor
        if det_count == 0:
            severity = 0
            color = "#00B050"
        elif det_count <= 3:
            severity = 1
            color = "#FFFF00"
        elif det_count <= 8:
            severity = 2
            color = "#FF9900"
        else:
            severity = 3
            color = "#FF0000"

        segments.append({
            "chainage_from": ch,
            "chainage_to": round(ch + 0.1, 3),
            "detection_count": det_count,
            "frame_count": doc['frame_count'],
            "severity": severity,
            "color": color,
            "lat": doc.get('avg_lat'),
            "lon": doc.get('avg_lon'),
            "quality": round(doc.get('avg_quality', 0), 1),
        })

    return {"segments": segments}


@router.delete("/task/{task_id}/camera/{camera_type}")
async def delete_camera_images(task_id: str, camera_type: str):
    """Delete all images for a specific camera type in a task."""
    import shutil
    db = get_db()

    # Delete from filesystem
    img_dir = Path(settings.BASE_DIR) / settings.DETECTED_IMAGES_DIR / task_id / camera_type
    if img_dir.exists():
        shutil.rmtree(img_dir, ignore_errors=True)

    # Delete from DB
    result = await db.detections.delete_many({"task_id": task_id, "camera_type": camera_type})

    return {"deleted_count": result.deleted_count}
