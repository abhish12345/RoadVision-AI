"""
Celery Task — main video processing pipeline.
ALL models run in parallel automatically — no user choice needed.

PAVE: rdd2022 + crack_seg + pothole_seg_m + pothole_finetune → merged + false positive filter
ROW:  row_road_objects + yolov8m_coco → merged, irrelevant classes skipped
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from celery_app import celery_app
from config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.processing_task.process_video",
                 max_retries=2, soft_time_limit=7200)
def process_video(self, video_id: str, task_id: str):
    from pymongo import MongoClient
    from bson import ObjectId

    client = MongoClient(settings.MONGO_URL)
    db = client[settings.MONGO_DB]

    try:
        # ── Load records ──────────────────────────────────────────────────────
        video = db.videos.find_one({"_id": ObjectId(video_id)})
        if not video:
            raise ValueError(f"Video {video_id} not found")
        task = db.tasks.find_one({"_id": ObjectId(task_id)})
        if not task:
            raise ValueError(f"Task {task_id} not found")

        camera_type = video['camera_type']
        video_path = video['file_path']
        capture_mode = video.get('capture_mode', 'interval')
        capture_value = video.get('capture_interval', 10.0)
        notification_email = (video.get('notification_email') or
                               task.get('notification_email') or '')
        # User-provided start chainage — used as base for GPS chainage calculation
        user_start_chainage = video.get('start_chainage', 0.0) or 0.0

        # ── Mark processing ───────────────────────────────────────────────────
        db.videos.update_one({"_id": ObjectId(video_id)},
                              {"$set": {"status": "processing", "started_at": datetime.utcnow()}})
        db.tasks.update_one({"_id": ObjectId(task_id)},
                             {"$set": {"status": "processing", "updated_at": datetime.utcnow()}})

        # ── Output dirs ───────────────────────────────────────────────────────
        output_dir = settings.BASE_DIR / settings.DETECTED_IMAGES_DIR / task_id / camera_type
        output_dir.mkdir(parents=True, exist_ok=True)
        annotated_dir = output_dir / "annotated"
        annotated_dir.mkdir(exist_ok=True)

        # ── Load ALL models for this camera type ──────────────────────────────
        from services.model_manager import (
            get_all_pave_models, get_all_row_models,
            normalize_pave_class, normalize_row_class, is_row_class_relevant
        )
        from services.frame_processor import (
            extract_frames_by_interval, run_yolo_detection,
            draw_detections_on_frame, compute_road_health_score,
            filter_false_positives, merge_detections_nms
        )

        if camera_type == "pave":
            all_models = get_all_pave_models()   # [(filename, model), ...]
        else:
            all_models = get_all_row_models()

        logger.info(f"Camera={camera_type} | Models: {[f for f,_ in all_models]}")

        # ── Process frames ────────────────────────────────────────────────────
        all_detections_db = []
        total_frames = 0
        total_detections = 0

        def progress_cb(pct, frame_num, total, extracted):
            self.update_state(state="PROGRESS", meta={
                "progress": pct, "frame_num": frame_num,
                "total_frames": total, "extracted": extracted,
                "detections": total_detections,
                "status": f"Processing frame {frame_num}/{total}"
            })
            db.videos.update_one({"_id": ObjectId(video_id)},
                                  {"$set": {"progress": pct, "frames_processed": frame_num}})

        for frame_info in extract_frames_by_interval(
            video_path=video_path, output_dir=output_dir,
            capture_mode=capture_mode, capture_value=capture_value,
            task_id=task_id, video_id=video_id,
            user_start_chainage=user_start_chainage,
            progress_callback=progress_cb
        ):
            frame = frame_info.pop('frame')
            total_frames += 1

            # ── Run ALL models in parallel, collect all detections ────────────
            raw_detections = []
            for model_file, model in all_models:
                # Use higher confidence for crack_seg to reduce false positives
                if 'crack_seg' in model_file:
                    conf = 0.45  # crack_seg is very sensitive — needs higher threshold
                elif camera_type == "pave":
                    conf = 0.30
                else:
                    conf = 0.35
                dets = run_yolo_detection(frame, model, conf_threshold=conf)
                for d in dets:
                    d['source_model'] = model_file
                raw_detections.extend(dets)

            # ── Normalize class names ─────────────────────────────────────────
            for det in raw_detections:
                if camera_type == "pave":
                    det['normalized_class'] = normalize_pave_class(det['class_name'])
                else:
                    det['normalized_class'] = normalize_row_class(det['class_name'])

            # ── Filter: remove irrelevant ROW classes ─────────────────────────
            if camera_type == "row":
                raw_detections = [d for d in raw_detections
                                  if d['normalized_class'] != 'skip'
                                  and d['confidence'] > 0.35]

            # ── Filter: remove road marking false positives (PAVE) ────────────
            if camera_type == "pave":
                raw_detections = filter_false_positives(frame, raw_detections, camera_type)

            # ── NMS merge: remove duplicate detections across models ──────────
            relevant = merge_detections_nms(raw_detections, iou_threshold=0.5)

            # ── Final confidence filter ───────────────────────────────────────
            if camera_type == "pave":
                relevant = [d for d in relevant
                            if d['normalized_class'] != 'other_defect' or d['confidence'] > 0.6]
            else:
                relevant = [d for d in relevant if d['confidence'] > 0.35]

            # ── Save annotated frame ──────────────────────────────────────────
            annotated_path = None
            if relevant:
                annotated_frame = draw_detections_on_frame(frame, relevant, camera_type)
                ann_filename = f"ann_{frame_info['image_filename']}"
                annotated_path = str(annotated_dir / ann_filename)
                import cv2
                cv2.imwrite(annotated_path, annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            total_detections += len(relevant)

            all_detections_db.append({
                "task_id": task_id,
                "video_id": video_id,
                "camera_type": camera_type,
                "frame_number": frame_info['frame_number'],
                "timestamp_sec": frame_info['timestamp_sec'],
                "chainage": frame_info.get('chainage'),
                "latitude": frame_info.get('latitude'),
                "longitude": frame_info.get('longitude'),
                "speed": frame_info.get('speed'),
                "survey_date": frame_info.get('survey_date'),
                "image_path": frame_info['image_path'],
                "image_filename": frame_info['image_filename'],
                "annotated_path": annotated_path,
                "detections": relevant,
                "quality_score": frame_info.get('quality_score'),
                "ocr_data": frame_info.get('ocr_data', {}),
                "created_at": datetime.utcnow(),
            })

        # ── Bulk insert ───────────────────────────────────────────────────────
        if all_detections_db:
            db.detections.insert_many(all_detections_db)

        # ── Aggregate segments ────────────────────────────────────────────────
        segments = _aggregate_segments(all_detections_db, camera_type)

        # ── Health score ──────────────────────────────────────────────────────
        avg_iri = 2.0
        if camera_type == "pave" and segments:
            iris = [s.get('iri', 2.0) for s in segments]
            avg_iri = sum(iris) / len(iris)
        health_score = compute_road_health_score(avg_iri, 6.0, total_detections, total_frames)

        # ── Generate reports ──────────────────────────────────────────────────
        reports_dir = Path(settings.BASE_DIR) / "reports" / task_id
        reports_dir.mkdir(parents=True, exist_ok=True)

        from services.report_service import generate_pave_excel_report, generate_row_excel_report

        excel_path = str(reports_dir / f"{camera_type}_report_{video_id}.xlsx")
        task_dict = {
            "name": task.get('name', ''),
            "nh_number": task.get('nh_number', 'NH-033'),
            "section_code": task.get('section_code', ''),
            "survey_date": task.get('survey_date', ''),
            "road_health_score": health_score,
        }
        video_dict = {
            "original_filename": video.get('original_filename', ''),
            "total_frames_extracted": total_frames,
            "chainage_start": segments[0].get('chainage_from') if segments else '',
            "chainage_end": segments[-1].get('chainage_to') if segments else '',
        }

        if camera_type == "pave":
            generate_pave_excel_report(task_dict, video_dict, all_detections_db, segments, excel_path)
        else:
            assets = _extract_assets(all_detections_db)
            generate_row_excel_report(task_dict, video_dict, all_detections_db, assets, excel_path)

        # ── Update DB ─────────────────────────────────────────────────────────
        chainages = [d.get('chainage') for d in all_detections_db if d.get('chainage')]
        db.videos.update_one({"_id": ObjectId(video_id)}, {"$set": {
            "status": "completed", "progress": 100,
            "total_frames_extracted": total_frames,
            "total_detections": total_detections,
            "chainage_start": min(chainages) if chainages else None,
            "chainage_end": max(chainages) if chainages else None,
            "excel_report_path": excel_path,
            "completed_at": datetime.utcnow(),
        }})
        db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {
            "status": "completed",
            "road_health_score": health_score,
            "updated_at": datetime.utcnow(),
        }})

        # ── Email ─────────────────────────────────────────────────────────────
        if notification_email:
            from services.email_service import send_task_completion_email
            send_task_completion_email(
                to_email=notification_email,
                task_name=task.get('name', ''),
                task_id=task_id,
                camera_type=camera_type,
                total_detections=total_detections,
                total_frames=total_frames,
                road_health_score=health_score,
                report_path=excel_path,
            )

        logger.info(f"Task {task_id} completed: {total_frames} frames, {total_detections} detections")
        return {"status": "completed", "total_frames": total_frames,
                "total_detections": total_detections, "health_score": health_score}

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        try:
            db.videos.update_one({"_id": ObjectId(video_id)},
                                  {"$set": {"status": "failed", "error": str(e)}})
            db.tasks.update_one({"_id": ObjectId(task_id)},
                                 {"$set": {"status": "failed", "updated_at": datetime.utcnow()}})
        except Exception:
            pass
        try:
            _t = db.tasks.find_one({"_id": ObjectId(task_id)})
            _v = db.videos.find_one({"_id": ObjectId(video_id)})
            _email = (_v.get('notification_email') if _v else '') or \
                     (_t.get('notification_email') if _t else '') or ''
            if _email:
                from services.email_service import send_processing_failed_email
                send_processing_failed_email(_email, _t.get('name', task_id) if _t else task_id,
                                             task_id, str(e))
        except Exception:
            pass
        raise
    finally:
        client.close()


def _aggregate_segments(detections: List[Dict], camera_type: str) -> List[Dict]:
    """Aggregate detections into 100m chainage segments."""
    if not detections:
        return []
    segments: Dict[float, Dict] = {}
    for det in detections:
        ch = det.get('chainage')
        if ch is None:
            continue
        seg_key = round(ch * 10) / 10
        if seg_key not in segments:
            segments[seg_key] = {
                "chainage_from": seg_key, "chainage_to": round(seg_key + 0.1, 3),
                "direction": "Increasing",
                "lat_start": det.get('latitude'), "lon_start": det.get('longitude'),
                "lat_end": det.get('latitude'), "lon_end": det.get('longitude'),
                "speed": det.get('speed', 30), "defects": {}, "assets": [],
                "frame_count": 0, "iri": 2.0, "condition": "Good",
            }
        seg = segments[seg_key]
        seg['frame_count'] += 1
        seg['lat_end'] = det.get('latitude', seg['lat_end'])
        seg['lon_end'] = det.get('longitude', seg['lon_end'])
        for d in det.get('detections', []):
            cls = d.get('normalized_class', 'unknown')
            if camera_type == "pave":
                seg['defects'][cls] = seg['defects'].get(cls, 0) + 1
            else:
                seg['assets'].append({
                    "asset_type": cls, "confidence": d.get('confidence', 0),
                    "chainage": det.get('chainage'), "latitude": det.get('latitude'),
                    "longitude": det.get('longitude'), "survey_date": det.get('survey_date'),
                    "image_path": det.get('image_path', ''), "side": "LHS",
                })

    for seg in segments.values():
        if camera_type == "pave":
            total = sum(seg['defects'].values())
            frames = max(seg['frame_count'], 1)
            # Defect density per frame (not raw count)
            # A segment with 20 frames and 2 defects = 0.1 density = Good
            # A segment with 20 frames and 20 defects = 1.0 density = Very Poor
            density = total / frames

            if density == 0:
                seg['iri'] = 1.5; seg['condition'] = "Very Good"
            elif density < 0.1:
                seg['iri'] = 2.0; seg['condition'] = "Good"
            elif density < 0.25:
                seg['iri'] = 3.0; seg['condition'] = "Good"
            elif density < 0.5:
                seg['iri'] = 4.5; seg['condition'] = "Fair"
            elif density < 0.75:
                seg['iri'] = 6.0; seg['condition'] = "Poor"
            else:
                seg['iri'] = 8.0; seg['condition'] = "Very Poor"

    return sorted(segments.values(), key=lambda x: x['chainage_from'])


def _extract_assets(detections: List[Dict]) -> List[Dict]:
    """
    Extract flat list of assets from ROW detections.
    Excludes vehicles — they are not road inventory assets.
    """
    # Asset types that belong in RIS sheets
    VALID_ASSET_TYPES = {
        'road_sign', 'crash_barrier', 'km_stone', 'street_light',
        'wayside_amenity', 'culvert_bridge', 'drain', 'retaining_wall',
        'utility_lines', 'median_divider', 'service_road',
        'encroachment', 'hazard_marker', 'roadside_feature',
    }
    # Types to completely exclude from reports
    EXCLUDE_TYPES = {'vehicle', 'skip', 'other_defect'}

    assets = []
    for det in detections:
        for d in det.get('detections', []):
            asset_type = d.get('normalized_class', 'unknown')
            # Skip vehicles and irrelevant classes
            if asset_type in EXCLUDE_TYPES:
                continue
            assets.append({
                "asset_type": asset_type,
                "confidence": d.get('confidence', 0),
                "chainage": det.get('chainage'),
                "latitude": det.get('latitude'),
                "longitude": det.get('longitude'),
                "survey_date": det.get('survey_date'),
                "image_path": det.get('image_path', ''),
                "image_filename": det.get('image_filename', ''),
                "side": "LHS", "direction": "Increasing",
            })
    return assets
