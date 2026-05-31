"""
Video upload and processing API routes.
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from bson import ObjectId
import aiofiles

from database import get_db
from config import settings
from tasks.processing_task import process_video

router = APIRouter(prefix="/api/videos", tags=["videos"])
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB


def _serialize(doc) -> dict:
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


@router.post("/upload")
async def upload_video(
    task_id: str = Form(...),
    camera_type: str = Form(...),
    capture_mode: str = Form("interval"),
    capture_interval: float = Form(10.0),
    notification_email: str = Form(""),
    start_chainage: float = Form(0.0),   # User inputs actual start chainage (km)
    file: UploadFile = File(...),
):
    """
    Upload a video file and start processing.
    Returns video_id and celery task_id for progress tracking.
    """
    db = get_db()

    # Validate task exists
    try:
        task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Validate camera type
    if camera_type not in ("pave", "row"):
        raise HTTPException(status_code=400, detail="camera_type must be 'pave' or 'row'")

    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not supported")

    # Save file
    upload_dir = Path(settings.BASE_DIR) / settings.UPLOAD_DIR / task_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{camera_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{ext}"
    file_path = upload_dir / safe_filename

    async with aiofiles.open(file_path, 'wb') as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await f.write(chunk)

    file_size = file_path.stat().st_size

    # Create video record in DB
    now = datetime.utcnow()
    video_doc = {
        "task_id": task_id,
        "camera_type": camera_type,
        "original_filename": file.filename,
        "file_path": str(file_path),
        "file_size": file_size,
        "capture_mode": capture_mode,
        "capture_interval": capture_interval,
        "notification_email": notification_email,
        "start_chainage": start_chainage,   # user-provided start chainage
        "status": "queued",
        "progress": 0,
        "total_frames_extracted": 0,
        "total_detections": 0,
        "chainage_start": None,
        "chainage_end": None,
        "excel_report_path": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.videos.insert_one(video_doc)
    video_id = str(result.inserted_id)

    # Update task status
    await db.tasks.update_one(
        {"_id": ObjectId(task_id)},
        {"$set": {"status": "processing", "updated_at": now}}
    )

    # Start Celery task
    celery_task = process_video.delay(video_id, task_id)

    # Store celery task id
    await db.videos.update_one(
        {"_id": result.inserted_id},
        {"$set": {"celery_task_id": celery_task.id}}
    )

    return {
        "video_id": video_id,
        "celery_task_id": celery_task.id,
        "status": "queued",
        "message": f"Video uploaded successfully. Processing started.",
        "file_size_mb": round(file_size / 1024 / 1024, 1),
    }


@router.get("/{video_id}/progress")
async def get_video_progress(video_id: str):
    """Get real-time processing progress for a video."""
    db = get_db()
    try:
        video = await db.videos.find_one({"_id": ObjectId(video_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid video ID")
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Also check Celery task state
    celery_task_id = video.get('celery_task_id')
    celery_state = None
    celery_meta = {}
    if celery_task_id:
        from celery_app import celery_app
        task_result = celery_app.AsyncResult(celery_task_id)
        celery_state = task_result.state
        if task_result.info and isinstance(task_result.info, dict):
            celery_meta = task_result.info

    return {
        "video_id": video_id,
        "status": video.get('status', 'unknown'),
        "progress": video.get('progress', 0),
        "frames_processed": video.get('frames_processed', 0),
        "total_detections": video.get('total_detections', 0),
        "celery_state": celery_state,
        "celery_meta": celery_meta,
        "error": video.get('error'),
    }


@router.get("/{video_id}/detections")
async def get_video_detections(
    video_id: str,
    skip: int = 0,
    limit: int = 50,
    camera_type: Optional[str] = None,
    class_filter: Optional[str] = None,
    min_confidence: float = 0.0,
    chainage_from: Optional[float] = None,
    chainage_to: Optional[float] = None,
):
    """Get detections for a video with filtering."""
    db = get_db()
    query = {"video_id": video_id}

    if camera_type:
        query["camera_type"] = camera_type
    if chainage_from is not None:
        query["chainage"] = {"$gte": chainage_from}
    if chainage_to is not None:
        query.setdefault("chainage", {})["$lte"] = chainage_to

    cursor = db.detections.find(query).sort("frame_number", 1).skip(skip).limit(limit)
    detections = []
    async for doc in cursor:
        d = dict(doc)
        d['id'] = str(d.pop('_id'))
        if isinstance(d.get('created_at'), datetime):
            d['created_at'] = d['created_at'].isoformat()
        # Filter by class if requested
        if class_filter:
            d['detections'] = [
                det for det in d.get('detections', [])
                if det.get('normalized_class') == class_filter
            ]
        # Filter by confidence
        if min_confidence > 0:
            d['detections'] = [
                det for det in d.get('detections', [])
                if det.get('confidence', 0) >= min_confidence
            ]
        detections.append(d)

    total = await db.detections.count_documents(query)
    return {"total": total, "skip": skip, "limit": limit, "detections": detections}


@router.post("/{video_id}/pause")
async def pause_video_processing(video_id: str):
    """
    Pause a currently processing video.
    Revokes the Celery task and marks status as 'paused'.
    The progress is saved — resume will continue from last checkpoint.
    """
    db = get_db()
    try:
        video = await db.videos.find_one({"_id": ObjectId(video_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid video ID")
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.get("status") not in ("processing", "queued"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause video with status '{video.get('status')}'. Only processing/queued videos can be paused."
        )

    # Revoke the Celery task
    celery_task_id = video.get("celery_task_id")
    if celery_task_id:
        from celery_app import celery_app
        celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")

    # Save current progress and mark as paused
    await db.videos.update_one(
        {"_id": ObjectId(video_id)},
        {"$set": {
            "status": "paused",
            "paused_at": datetime.utcnow(),
            "paused_progress": video.get("progress", 0),
            "paused_frames": video.get("frames_processed", 0),
        }}
    )

    # Update task status
    task_id = video.get("task_id")
    if task_id:
        await db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "paused", "updated_at": datetime.utcnow()}}
        )

    # ── Auto-start next queued video ──────────────────────────────────────────
    # When a video is paused, automatically start the next queued video
    # so the worker is never idle
    next_queued = await db.videos.find_one(
        {"status": "queued", "_id": {"$ne": ObjectId(video_id)}},
        sort=[("created_at", 1)]  # oldest first
    )
    next_started = None
    if next_queued:
        next_video_id = str(next_queued["_id"])
        next_task_id  = next_queued.get("task_id", "")
        celery_task   = process_video.delay(next_video_id, next_task_id)
        await db.videos.update_one(
            {"_id": next_queued["_id"]},
            {"$set": {"celery_task_id": celery_task.id, "status": "queued"}}
        )
        next_started = next_video_id
        logger.info(f"Auto-started next queued video: {next_video_id}")

    return {
        "message": "Processing paused",
        "video_id": video_id,
        "progress_saved": video.get("progress", 0),
        "frames_processed": video.get("frames_processed", 0),
        "next_video_started": next_started,
    }


@router.post("/{video_id}/resume")
async def resume_video_processing(video_id: str):
    """
    Resume a paused video from where it left off.
    Restarts the Celery task with resume_from_frame parameter.
    """
    db = get_db()
    try:
        video = await db.videos.find_one({"_id": ObjectId(video_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid video ID")
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.get("status") != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume video with status '{video.get('status')}'. Only paused videos can be resumed."
        )

    # Restart Celery task
    celery_task = process_video.delay(video_id, video["task_id"])

    # Update status back to processing
    await db.videos.update_one(
        {"_id": ObjectId(video_id)},
        {"$set": {
            "status": "queued",
            "celery_task_id": celery_task.id,
            "resumed_at": datetime.utcnow(),
        }}
    )

    # Update task status
    task_id = video.get("task_id")
    if task_id:
        await db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "processing", "updated_at": datetime.utcnow()}}
        )

    return {
        "message": "Processing resumed",
        "video_id": video_id,
        "celery_task_id": celery_task.id,
        "resuming_from_progress": video.get("paused_progress", 0),
    }


@router.post("/{video_id}/cancel")
async def cancel_video_processing(video_id: str):
    """
    Cancel processing of a video (pause + mark as cancelled).
    Keeps the video record and any already-detected frames.
    """
    db = get_db()
    try:
        video = await db.videos.find_one({"_id": ObjectId(video_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid video ID")
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.get("status") in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Video is already {video.get('status')}"
        )

    # Revoke Celery task
    celery_task_id = video.get("celery_task_id")
    if celery_task_id:
        from celery_app import celery_app
        celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")

    # Count already-detected frames
    task_id = video.get("task_id")
    detected_count = await db.detections.count_documents({"video_id": video_id})

    await db.videos.update_one(
        {"_id": ObjectId(video_id)},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.utcnow(),
            "total_detections": detected_count,
        }}
    )

    if task_id:
        # Check if any other videos in this task are still processing
        other_active = await db.videos.count_documents({
            "task_id": task_id,
            "status": {"$in": ["processing", "queued", "paused"]},
            "_id": {"$ne": ObjectId(video_id)}
        })
        if other_active == 0:
            await db.tasks.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}}
            )

    # ── Auto-start next queued video ──────────────────────────────────────────
    next_queued = await db.videos.find_one(
        {"status": "queued", "_id": {"$ne": ObjectId(video_id)}},
        sort=[("created_at", 1)]
    )
    next_started = None
    if next_queued:
        next_video_id = str(next_queued["_id"])
        next_task_id  = next_queued.get("task_id", "")
        celery_task   = process_video.delay(next_video_id, next_task_id)
        await db.videos.update_one(
            {"_id": next_queued["_id"]},
            {"$set": {"celery_task_id": celery_task.id}}
        )
        next_started = next_video_id
        logger.info(f"Auto-started next queued video after cancel: {next_video_id}")

    return {
        "message": "Processing cancelled",
        "video_id": video_id,
        "frames_detected_so_far": detected_count,
        "next_video_started": next_started,
        "note": "Detected frames are preserved. You can still view results and download partial reports."
    }


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """Delete a video and its detections."""
    db = get_db()
    try:
        video = await db.videos.find_one({"_id": ObjectId(video_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid video ID")
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Revoke any active Celery task first
    celery_task_id = video.get("celery_task_id")
    if celery_task_id and video.get("status") in ("processing", "queued"):
        from celery_app import celery_app
        celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")

    # Delete video file
    file_path = video.get('file_path')
    if file_path and Path(file_path).exists():
        os.remove(file_path)

    # Delete detections
    await db.detections.delete_many({"video_id": video_id})
    await db.videos.delete_one({"_id": ObjectId(video_id)})

    # Auto-start next queued video
    next_queued = await db.videos.find_one(
        {"status": "queued", "_id": {"$ne": ObjectId(video_id)}},
        sort=[("created_at", 1)]
    )
    if next_queued:
        next_video_id = str(next_queued["_id"])
        celery_task   = process_video.delay(next_video_id, next_queued.get("task_id", ""))
        await db.videos.update_one(
            {"_id": next_queued["_id"]},
            {"$set": {"celery_task_id": celery_task.id}}
        )

    return {"message": f"Video {video_id} deleted"}
async def download_report(video_id: str, format: str = "excel"):
    """Download the generated report for a video."""
    db = get_db()
    try:
        video = await db.videos.find_one({"_id": ObjectId(video_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid video ID")
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    excel_path = video.get('excel_report_path')
    if not excel_path or not Path(excel_path).exists():
        raise HTTPException(status_code=404, detail="Report not yet generated")

    filename = f"report_{video.get('camera_type', 'survey')}_{video_id}.xlsx"
    return FileResponse(
        path=excel_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
