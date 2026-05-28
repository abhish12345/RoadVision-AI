# RoadVision AI

AI-powered road survey analysis system for automated detection of pavement defects and road assets from NSV camera footage. Processes PAVE and ROW camera videos using YOLOv8 to detect potholes, cracks, road signs, barriers and 30+ road features — generating RIS DataTemplate compliant reports with interactive maps, heatmaps and multi-format exports.

---

## Prerequisites

| Service | URL | Status |
|---------|-----|--------|
| MongoDB | localhost:27017 | Must be running |
| Redis | localhost:6379 | Must be running |
| Python 3.14 (venv) | `.venv/` | Ready |
| Node.js v22+ | — | Installed |

---

## Quick Start

### Step 1 — Download AI Models (run once)
```
setup_models.bat
```

### Step 2 — Start Backend
```
start_backend.bat
```
Opens two windows:
- **FastAPI** on http://localhost:8000
- **Celery Worker** for background video processing

### Step 3 — Start Frontend
```
start_frontend.bat
```
Opens: http://localhost:5173

---

## How to Use

### 1. Create a Task
- Go to **Tasks → New Task**
- Enter: Task name, NH Number, Section Code, Survey Date
- Optionally add email for completion notification

### 2. Upload a Video
Inside the task:
- Select **Camera Type**: PAVE (pavement defects) or ROW (road assets)
- Choose **Capture Mode**: Every N meters OR every N fps
- Drag & drop your video file (MP4, AVI, MOV, MKV)
- Processing starts automatically in background

### 3. Monitor Progress
- Real-time progress bar shows frame processing status

### 4. View Results

| Feature | Description |
|---------|-------------|
| **Image Gallery** | Browse all detected frames with filters |
| **Map View** | GPS-plotted detections on Leaflet map |
| **Heatmap** | Chainage-wise severity color map |
| **AI Replay** | Video playback with bounding box overlay |
| **Reports** | Download Excel, PDF, CSV, KML, GeoJSON |
| **Compare** | Side-by-side comparison of two survey tasks |

### 5. Delete a Task
Click **Delete Task** — removes ALL data including detected images

---

## Camera Types

### PAVE Camera (downward-facing)
Detects pavement defects:
- Alligator Cracks, Longitudinal Cracks, Transverse Cracks
- Potholes, Patching, Bleeding/Ravelling
- IRI (Roughness), MPD, Texture, Lane Marking Width

### ROW Camera (forward/side-facing)
Detects road assets:
- Road Signs, Crash Barriers, KM Stones
- Street Lights, Drain Type, Culverts & Bridges
- Retaining Walls, Utility Lines, Encroachments
- Wayside Amenities, Median/Divider, Service Roads
- Topography, Visual Condition, Structure Details

---

## AI Models — Parallel Detection Architecture

### PAVE Camera — 4 Models Run in Parallel

| Model | Source | Detects | Size |
|-------|--------|---------|------|
| `rdd2022_yolov8m.pt` | vishnus23d158/HuggingFace | D00=longitudinal, D10=transverse, D20=alligator, D40=pothole | 49 MB |
| `crack_seg_yolov8m.pt` | OpenSistemas/HuggingFace | crack (segmentation, thin cracks) | 52 MB |
| `pothole_seg_yolov8m.pt` | keremberke/HuggingFace | pothole (segmentation, shape) | 52 MB |
| `pothole_finetune_yolov8.pt` | Harisanth/HuggingFace | pothole (fine-tuned) | 21 MB |

**Pipeline:**
```
Frame → [rdd2022 + crack_seg + pothole_seg + pothole_finetune] (parallel)
      → Merge all detections
      → NMS (remove duplicates across models)
      → False positive filter (remove white lane lines, zebra crossings)
      → Save annotated frame
```

### ROW Camera — 2 Models Run in Parallel

| Model | Source | Detects | Size |
|-------|--------|---------|------|
| `row_road_objects_yolov8s.pt` | Aniket200325/HuggingFace | traffic sign, traffic light, vehicles, pedestrian | 21 MB |
| `yolov8m.pt` | Ultralytics COCO | stop sign, person, bench + 77 more | 49 MB |

**Pipeline:**
```
Frame → [row_road_objects + yolov8m_coco] (parallel)
      → Merge all detections
      → NMS (remove duplicates)
      → Skip irrelevant COCO classes (airplane, banana, etc.)
      → Save annotated frame
```

### False Positive Filter (PAVE)
Automatically removes road markings detected as cracks:
- White lane lines (brightness > 160)
- Zebra crossings (white pixel ratio > 35%)
- Road arrows (elongated + bright)
- Painted markings (uniform + bright)

Real cracks are dark (shadow inside) — they always pass the filter.

---

## Report Formats

| Format | Contents |
|--------|----------|
| **Excel (RIS)** | Full RIS DataTemplate — VisualCondition, Roughness, CarriagewayFurniture sheets + charts |
| **PDF** | Summary report with detection table and condition scale |
| **CSV** | Raw detection data — all frames, classes, coordinates |
| **KML** | Google Earth placemarks for each detection |
| **GeoJSON** | QGIS/web mapping compatible format |

---

## Project Structure

```
road_identification/
├── backend/
│   ├── api/              # FastAPI routes (tasks, videos, images, reports, models)
│   ├── services/         # OCR, frame processor, model manager, reports, email
│   ├── tasks/            # Celery background processing task
│   ├── models/           # Pydantic schemas
│   ├── ml_models/        # YOLO model weights (8 .pt files)
│   ├── uploads/          # Uploaded video files (per task)
│   ├── detected_images/  # Extracted frames (per task/camera)
│   ├── reports/          # Generated Excel/PDF reports
│   ├── main.py           # FastAPI app entry point
│   └── celery_app.py     # Celery configuration
├── frontend/
│   └── src/
│       ├── pages/        # Dashboard, Tasks, Gallery, Map, Reports, Compare, VideoPlayer
│       └── components/   # Layout, ProgressRing, StatCard, ModelStatus
├── start_backend.bat     # Start FastAPI + Celery
├── start_frontend.bat    # Start React dev server
└── setup_models.bat      # Download AI models (run once)
```

---

## API Documentation

Interactive docs: http://localhost:8000/docs

Key endpoints:
- `POST /api/tasks/` — Create task
- `GET  /api/tasks/` — List all tasks
- `DELETE /api/tasks/{id}` — Delete task + all data
- `POST /api/videos/upload` — Upload video + start processing
- `GET  /api/videos/{id}/progress` — Real-time progress
- `GET  /api/images/task/{id}` — Get detected images
- `GET  /api/images/task/{id}/map-data` — GPS markers for map
- `GET  /api/images/task/{id}/heatmap` — Chainage severity data
- `GET  /api/reports/task/{id}/excel` — Download Excel (RIS format)
- `GET  /api/reports/task/{id}/pdf` — Download PDF
- `GET  /api/reports/task/{id}/csv` — Download CSV
- `GET  /api/reports/task/{id}/kml` — Download KML
- `GET  /api/reports/task/{id}/geojson` — Download GeoJSON
- `GET  /api/models/status` — AI model availability status

---

## Road Health Score

Calculated 0–100 from:
- IRI (roughness) — 40 points
- Defect density — 40 points
- Rut depth — 20 points

| Score | Condition |
|-------|-----------|
| 70–100 | Good (green) |
| 40–69 | Fair (yellow) |
| 0–39 | Poor (red) |

---

## Email Notifications

Configured with Gmail SMTP. When processing completes, an email is sent with:
- Total frames processed, total detections, Road Health Score
- Excel report attached
