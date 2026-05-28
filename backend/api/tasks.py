"""
Task management API routes.
"""
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from bson import ObjectId

from database import get_db
from config import settings
from models.task import TaskCreate, TaskResponse, TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)


def _serialize(doc) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    if doc is None:
        return None
    doc = dict(doc)
    doc['id'] = str(doc.pop('_id'))
    for k, v in doc.items():
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
        elif isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


@router.post("/", response_model=dict)
async def create_task(task: TaskCreate):
    """Create a new survey task."""
    db = get_db()
    now = datetime.utcnow()
    doc = {
        "name": task.name,
        "description": task.description,
        "nh_number": task.nh_number,
        "section_code": task.section_code,
        "survey_date": task.survey_date,
        "notification_email": task.notification_email,
        "status": TaskStatus.CREATED,
        "road_health_score": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.tasks.insert_one(doc)
    doc['id'] = str(result.inserted_id)
    doc['_id'] = result.inserted_id
    return _serialize(doc)


@router.get("/", response_model=List[dict])
async def list_tasks(skip: int = 0, limit: int = 50):
    """List all tasks, newest first."""
    db = get_db()
    cursor = db.tasks.find().sort("created_at", -1).skip(skip).limit(limit)
    tasks = []
    async for doc in cursor:
        t = _serialize(doc)
        # Attach video count
        video_count = await db.videos.count_documents({"task_id": str(doc['_id'])})
        t['video_count'] = video_count
        tasks.append(t)
    return tasks


@router.get("/{task_id}", response_model=dict)
async def get_task(task_id: str):
    """Get a single task with its videos."""
    db = get_db()
    try:
        doc = await db.tasks.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")

    task = _serialize(doc)

    # Attach videos
    videos = []
    async for v in db.videos.find({"task_id": task_id}):
        videos.append(_serialize(v))
    task['videos'] = videos

    return task


@router.put("/{task_id}", response_model=dict)
async def update_task(task_id: str, task: TaskCreate):
    """Update task metadata."""
    db = get_db()
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    update = {
        "name": task.name,
        "description": task.description,
        "nh_number": task.nh_number,
        "section_code": task.section_code,
        "survey_date": task.survey_date,
        "notification_email": task.notification_email,
        "updated_at": datetime.utcnow(),
    }
    result = await db.tasks.update_one({"_id": oid}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")

    doc = await db.tasks.find_one({"_id": oid})
    return _serialize(doc)


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """
    Delete a task and ALL associated data:
    - Videos (files + DB records)
    - Detected images folder
    - Reports
    - Detection records
    """
    db = get_db()
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await db.tasks.find_one({"_id": oid})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Delete video files
    async for video in db.videos.find({"task_id": task_id}):
        file_path = video.get('file_path')
        if file_path and Path(file_path).exists():
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not delete video file {file_path}: {e}")

    # Delete detected images folder
    detected_dir = Path(settings.BASE_DIR) / settings.DETECTED_IMAGES_DIR / task_id
    if detected_dir.exists():
        shutil.rmtree(detected_dir, ignore_errors=True)

    # Delete reports folder
    reports_dir = Path(settings.BASE_DIR) / "reports" / task_id
    if reports_dir.exists():
        shutil.rmtree(reports_dir, ignore_errors=True)

    # Delete DB records
    await db.videos.delete_many({"task_id": task_id})
    await db.detections.delete_many({"task_id": task_id})
    await db.tasks.delete_one({"_id": oid})

    return {"message": f"Task {task_id} and all associated data deleted successfully"}


@router.get("/{task_id}/stats", response_model=dict)
async def get_task_stats(task_id: str):
    """Get aggregated statistics for a task."""
    db = get_db()
    try:
        ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    # Detection counts by class
    pipeline = [
        {"$match": {"task_id": task_id}},
        {"$unwind": "$detections"},
        {"$group": {
            "_id": "$detections.normalized_class",
            "count": {"$sum": 1},
            "avg_confidence": {"$avg": "$detections.confidence"}
        }},
        {"$sort": {"count": -1}}
    ]
    class_counts = []
    async for doc in db.detections.aggregate(pipeline):
        class_counts.append({
            "class": doc['_id'],
            "count": doc['count'],
            "avg_confidence": round(doc['avg_confidence'] * 100, 1)
        })

    # Chainage-wise detection counts
    ch_pipeline = [
        {"$match": {"task_id": task_id, "chainage": {"$ne": None}}},
        {"$group": {
            "_id": {"$round": [{"$multiply": ["$chainage", 10]}, 0]},
            "detection_count": {"$sum": {"$size": "$detections"}},
            "frame_count": {"$sum": 1},
            "avg_quality": {"$avg": "$quality_score"},
        }},
        {"$sort": {"_id": 1}}
    ]
    chainage_data = []
    async for doc in db.detections.aggregate(ch_pipeline):
        chainage_data.append({
            "chainage": doc['_id'] / 10,
            "detections": doc['detection_count'],
            "frames": doc['frame_count'],
            "quality": round(doc.get('avg_quality', 0), 1),
        })

    # Total counts
    total_frames = await db.detections.count_documents({"task_id": task_id})
    total_det_pipeline = [
        {"$match": {"task_id": task_id}},
        {"$group": {"_id": None, "total": {"$sum": {"$size": "$detections"}}}}
    ]
    total_detections = 0
    async for doc in db.detections.aggregate(total_det_pipeline):
        total_detections = doc['total']

    task = await db.tasks.find_one({"_id": ObjectId(task_id)})

    return {
        "task_id": task_id,
        "total_frames": total_frames,
        "total_detections": total_detections,
        "road_health_score": task.get('road_health_score') if task else None,
        "class_distribution": class_counts,
        "chainage_data": chainage_data,
    }
