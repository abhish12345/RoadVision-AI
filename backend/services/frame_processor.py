"""
Frame Processor — core video processing engine.
Handles frame extraction, quality check, duplicate detection,
OCR overlay reading, and YOLO detection.
"""
import cv2
import numpy as np
from pathlib import Path
from typing import Generator, Tuple, Dict, Any, List, Optional
import logging
import hashlib

from services.ocr_service import extract_overlay_data, estimate_chainage_from_gps

logger = logging.getLogger(__name__)


def compute_frame_hash(frame: np.ndarray) -> str:
    """Compute perceptual hash of frame for duplicate detection."""
    small = cv2.resize(frame, (16, 16))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return hashlib.md5(gray.tobytes()).hexdigest()


def assess_frame_quality(frame: np.ndarray) -> float:
    """
    Assess frame quality (0-100).
    Checks: blur, brightness, contrast.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Blur detection (Laplacian variance)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    blur_norm = min(blur_score / 500.0, 1.0) * 40  # max 40 points

    # Brightness (avoid too dark or too bright)
    mean_brightness = gray.mean()
    if 50 <= mean_brightness <= 200:
        brightness_score = 30
    elif 30 <= mean_brightness <= 220:
        brightness_score = 20
    else:
        brightness_score = 5

    # Contrast
    contrast = gray.std()
    contrast_score = min(contrast / 80.0, 1.0) * 30  # max 30 points

    return round(blur_norm + brightness_score + contrast_score, 1)


def extract_frames_by_interval(
    video_path: str,
    output_dir: Path,
    capture_mode: str,
    capture_value: float,
    task_id: str,
    video_id: str,
    user_start_chainage: float = 0.0,
    progress_callback=None
) -> Generator[Dict[str, Any], None, None]:
    """
    Extract frames from video based on capture mode.
    user_start_chainage: the actual road chainage at video start (km), provided by user.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 5.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    logger.info(f"Video: {total_frames} frames @ {fps}fps, {frame_width}x{frame_height}")

    # Determine frame step
    if capture_mode == "fps":
        # capture_value = desired fps (e.g. 5 = every frame at 5fps)
        step = max(1, int(fps / capture_value))
    else:
        # capture_mode == "interval" (meters)
        # Assume average speed ~30 km/h = 8.33 m/s
        # frames_per_meter = fps / speed_m_per_s
        # We'll update dynamically from OCR speed data
        assumed_speed_mps = 8.33  # 30 km/h default
        frames_per_meter = fps / assumed_speed_mps
        step = max(1, int(frames_per_meter * capture_value))

    output_dir.mkdir(parents=True, exist_ok=True)

    frame_num = 0
    extracted_count = 0
    prev_hash = None

    # OCR state — track last known telemetry
    last_ocr: Dict[str, Any] = {}
    # Use user_start_chainage as the base — overridden by OCR if available
    start_chainage = user_start_chainage if user_start_chainage > 0 else None
    start_lat = None
    start_lon = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_num % step == 0:
            # Quality check
            quality = assess_frame_quality(frame)

            # Duplicate check
            frame_hash = compute_frame_hash(frame)
            is_duplicate = (frame_hash == prev_hash)
            prev_hash = frame_hash

            if is_duplicate:
                frame_num += 1
                continue

            # OCR — read overlay every 10 extracted frames to save time
            ocr_data = {}
            if extracted_count % 10 == 0:
                ocr_data = extract_overlay_data(frame)
                if ocr_data:
                    last_ocr.update(ocr_data)

            # Use last known OCR data
            current_ocr = dict(last_ocr)

            # Chainage estimation
            chainage = current_ocr.get('chainage')
            lat = current_ocr.get('latitude')
            lon = current_ocr.get('longitude')

            if lat and lon:
                if start_lat is None:
                    start_lat = lat
                    start_lon = lon
                    # Priority: OCR chainage > user_start_chainage > 0
                    if start_chainage is None:
                        start_chainage = chainage or user_start_chainage or 0.0
                    elif chainage:
                        start_chainage = chainage  # OCR wins if available
                elif chainage is None and start_lat:
                    # GPS-based chainage from user-provided start
                    chainage = estimate_chainage_from_gps(
                        lat, lon, start_lat, start_lon, start_chainage
                    )
            elif start_chainage is not None and chainage is None:
                # No GPS yet — use frame-based distance estimate
                # Assume 30 km/h average speed
                elapsed_km = (frame_num / fps) * (30 / 3600)
                chainage = start_chainage + elapsed_km

            # Update step dynamically if speed available
            if capture_mode == "interval" and current_ocr.get('speed'):
                speed_kmh = current_ocr['speed']
                speed_mps = speed_kmh / 3.6
                if speed_mps > 0:
                    frames_per_meter = fps / speed_mps
                    step = max(1, int(frames_per_meter * capture_value))

            # Save frame
            timestamp_sec = frame_num / fps
            img_filename = f"frame_{frame_num:06d}_ch{chainage or 0:.3f}.jpg"
            img_path = output_dir / img_filename
            cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

            frame_info = {
                "frame_number": frame_num,
                "timestamp_sec": round(timestamp_sec, 2),
                "chainage": round(chainage, 3) if chainage else None,
                "latitude": lat,
                "longitude": lon,
                "speed": current_ocr.get('speed'),
                "survey_date": current_ocr.get('survey_date'),
                "description": current_ocr.get('description'),
                "image_path": str(img_path),
                "image_filename": img_filename,
                "quality_score": quality,
                "is_duplicate": False,
                "ocr_data": current_ocr,
                "frame": frame,  # numpy array for detection
            }

            extracted_count += 1

            # Progress callback
            if progress_callback and total_frames > 0:
                progress = int((frame_num / total_frames) * 100)
                progress_callback(progress, frame_num, total_frames, extracted_count)

            yield frame_info

        frame_num += 1

    cap.release()
    logger.info(f"Extracted {extracted_count} frames from {total_frames} total")


def run_yolo_detection(
    frame: np.ndarray,
    model,
    conf_threshold: float = 0.35,
    iou_threshold: float = 0.45
) -> List[Dict[str, Any]]:
    """Run YOLO detection on a frame and return list of detections."""
    results = model(frame, conf=conf_threshold, iou=iou_threshold, verbose=False)
    detections = []

    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = result.names.get(cls_id, str(cls_id))

            detections.append({
                "x1": round(x1, 1),
                "y1": round(y1, 1),
                "x2": round(x2, 1),
                "y2": round(y2, 1),
                "confidence": round(conf, 3),
                "class_name": cls_name,
                "class_id": cls_id,
            })

    return detections


def is_road_marking_false_positive(
    frame: np.ndarray,
    x1: float, y1: float, x2: float, y2: float,
    class_name: str
) -> bool:
    """
    Detect if a crack detection is actually a false positive:
    - White/yellow road markings (lane lines, zebra crossings, arrows)
    - Road surface texture mistaken for cracks
    - Shadow lines
    - Low-confidence noise detections

    Real cracks:
    - Dark color (shadow inside crack)
    - Irregular edges
    - Mean brightness typically < 110
    - Low white pixel ratio
    """
    # Only filter crack detections — potholes are 3D depressions
    crack_classes = {"alligator_crack", "longitudinal_crack", "transverse_crack", "crack"}
    if class_name not in crack_classes:
        return False

    h, w = frame.shape[:2]
    x1i, y1i = max(0, int(x1)), max(0, int(y1))
    x2i, y2i = min(w, int(x2)), min(h, int(y2))

    if x2i <= x1i or y2i <= y1i:
        return False

    roi = frame[y1i:y2i, x1i:x2i]
    if roi.size == 0:
        return False

    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(gray_roi.mean())
    std_dev = float(gray_roi.std())
    box_w = x2i - x1i
    box_h = y2i - y1i

    # ── Check 1: Very bright = white road marking ─────────────────────────────
    if mean_brightness > 155:
        return True

    # ── Check 2: High white pixel ratio = painted marking ────────────────────
    white_pixels = np.sum(gray_roi > 200)
    white_ratio = white_pixels / gray_roi.size
    if white_ratio > 0.30:
        return True

    # ── Check 3: Elongated + moderately bright = lane line ───────────────────
    if box_w > 0 and box_h > 0:
        aspect = max(box_w, box_h) / min(box_w, box_h)
        if aspect > 6 and mean_brightness > 110:
            return True

    # ── Check 4: Uniform + bright = painted surface ───────────────────────────
    if mean_brightness > 130 and std_dev < 25:
        return True

    # ── Check 5: Very low contrast = road texture noise (not a real crack) ────
    # Real cracks have high local contrast (dark crack against lighter road)
    # Texture noise has very low std deviation
    if std_dev < 8 and mean_brightness > 60:
        return True

    # ── Check 6: Tiny bounding box = noise detection ─────────────────────────
    box_area = box_w * box_h
    frame_area = w * h
    if box_area < frame_area * 0.0001:  # less than 0.01% of frame
        return True

    # ── Check 7: Check surrounding context ───────────────────────────────────
    # If the area around the detection is very bright (road marking context),
    # expand ROI and check
    pad = 20
    cx1 = max(0, x1i - pad)
    cy1 = max(0, y1i - pad)
    cx2 = min(w, x2i + pad)
    cy2 = min(h, y2i + pad)
    context_roi = frame[cy1:cy2, cx1:cx2]
    if context_roi.size > 0:
        ctx_gray = cv2.cvtColor(context_roi, cv2.COLOR_BGR2GRAY)
        ctx_mean = float(ctx_gray.mean())
        ctx_white = float(np.sum(ctx_gray > 200) / ctx_gray.size)
        # If surrounding area is very bright (white marking context)
        if ctx_mean > 160 and ctx_white > 0.25:
            return True

    return False


def filter_false_positives(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    camera_type: str
) -> List[Dict[str, Any]]:
    """
    Filter out false positive detections.
    Main use: remove road markings detected as cracks.
    """
    if camera_type != "pave":
        return detections

    filtered = []
    removed = 0

    for det in detections:
        cls = det.get('normalized_class', det.get('class_name', ''))
        is_fp = is_road_marking_false_positive(
            frame,
            det['x1'], det['y1'], det['x2'], det['y2'],
            cls
        )
        if is_fp:
            removed += 1
            logger.debug(f"Filtered false positive: {cls} at ({det['x1']:.0f},{det['y1']:.0f}) brightness check")
        else:
            filtered.append(det)

    if removed > 0:
        logger.debug(f"Removed {removed} road marking false positives from {len(detections)} detections")

    return filtered


def draw_detections_on_frame(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    camera_type: str
) -> np.ndarray:
    """Draw bounding boxes and labels on frame."""
    annotated = frame.copy()

    # Color map per camera type
    if camera_type == "pave":
        colors = {
            "pothole": (0, 0, 255),          # Red
            "alligator_crack": (0, 128, 255), # Orange
            "longitudinal_crack": (0, 255, 255), # Yellow
            "transverse_crack": (255, 0, 255),   # Magenta
            "patching": (128, 128, 0),           # Olive
            "bleeding_ravelling": (255, 128, 0), # Blue-orange
        }
        default_color = (0, 200, 0)
    else:
        colors = {
            "road_sign": (0, 255, 0),         # Green
            "crash_barrier": (0, 0, 255),     # Red
            "km_stone": (255, 255, 0),        # Cyan
            "street_light": (255, 200, 0),    # Light blue
            "drain": (128, 0, 128),           # Purple
            "culvert_bridge": (0, 128, 255),  # Orange
        }
        default_color = (0, 200, 200)

    for det in detections:
        x1, y1, x2, y2 = int(det['x1']), int(det['y1']), int(det['x2']), int(det['y2'])
        cls = det.get('normalized_class', det['class_name'])
        conf = det['confidence']
        color = colors.get(cls, default_color)

        # Draw box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # Label background
        label = f"{cls} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(annotated, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return annotated


def merge_detections_nms(
    detections: List[Dict[str, Any]],
    iou_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Merge detections from multiple models using Non-Maximum Suppression.
    Removes duplicate detections of the same object detected by different models.
    Keeps the detection with highest confidence when boxes overlap significantly.
    """
    if not detections:
        return []

    # Group by normalized class for NMS
    # Sort by confidence descending
    sorted_dets = sorted(detections, key=lambda d: d.get('confidence', 0), reverse=True)
    kept = []

    for det in sorted_dets:
        x1, y1, x2, y2 = det['x1'], det['y1'], det['x2'], det['y2']
        area = max(0, x2 - x1) * max(0, y2 - y1)
        if area == 0:
            continue

        # Check overlap with already kept detections
        is_duplicate = False
        for k in kept:
            # Compute IoU
            ix1 = max(x1, k['x1'])
            iy1 = max(y1, k['y1'])
            ix2 = min(x2, k['x2'])
            iy2 = min(y2, k['y2'])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            if inter == 0:
                continue
            k_area = max(0, k['x2'] - k['x1']) * max(0, k['y2'] - k['y1'])
            union = area + k_area - inter
            iou = inter / union if union > 0 else 0

            if iou > iou_threshold:
                # Same object — keep higher confidence (already sorted, so skip this one)
                is_duplicate = True
                break

        if not is_duplicate:
            kept.append(det)

    return kept
    """
    Estimate IRI from frame quality variance.
    Lower quality variance = smoother road = lower IRI.
    This is a proxy metric; real IRI needs accelerometer data.
    """
    if not frames_data:
        return 2.0
    qualities = [f.get('quality_score', 50) for f in frames_data]
    variance = np.var(qualities)
    # Map variance to IRI range 0.5 - 10
    iri = 0.5 + (variance / 100.0) * 9.5
    return round(min(max(iri, 0.5), 10.0), 2)


def compute_road_health_score(
    iri: float,
    rut_depth: float,
    defect_count: int,
    total_frames: int
) -> float:
    """
    Compute overall road health score 0-100.
    100 = perfect, 0 = very poor.

    IRI thresholds (IRC standard):
      < 2.0  = Very Good (score 40)
      2-4    = Good      (score 30-40)
      4-6    = Fair      (score 20-30)
      6-8    = Poor      (score 10-20)
      > 8    = Very Poor (score 0-10)
    """
    # Clamp IRI to realistic range 0.5–10
    iri = max(0.5, min(iri, 10.0))

    # IRI score (0-40 points)
    if iri < 2.0:
        iri_score = 40.0
    elif iri < 4.0:
        iri_score = 40.0 - (iri - 2.0) * 5.0   # 40→30
    elif iri < 6.0:
        iri_score = 30.0 - (iri - 4.0) * 5.0   # 30→20
    elif iri < 8.0:
        iri_score = 20.0 - (iri - 6.0) * 5.0   # 20→10
    else:
        iri_score = max(0.0, 10.0 - (iri - 8.0) * 5.0)

    # Defect density score (0-40 points)
    if total_frames > 0:
        density = defect_count / total_frames
        # density 0 = 40pts, density 0.5+ = 0pts
        defect_score = max(0.0, 40.0 - density * 80.0)
    else:
        defect_score = 40.0

    # Rut depth score (0-20 points)
    rut_depth = max(0.0, min(rut_depth, 30.0))
    if rut_depth < 5.0:
        rut_score = 20.0
    elif rut_depth < 10.0:
        rut_score = 20.0 - (rut_depth - 5.0) * 2.0   # 20→10
    elif rut_depth < 20.0:
        rut_score = 10.0 - (rut_depth - 10.0) * 1.0  # 10→0
    else:
        rut_score = 0.0

    total = round(iri_score + defect_score + rut_score, 1)
    return min(100.0, max(0.0, total))
