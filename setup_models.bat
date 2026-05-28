@echo off
title RoadVision AI - Model Setup
echo ============================================================
echo  RoadVision AI - AI Model Setup
echo  Run this ONCE before starting the server
echo ============================================================
echo.
echo  Models to download:
echo.
echo  PAVE Camera (Pavement Defects):
echo    1. rdd2022_yolov8m.pt         RDD2022 YOLOv8m  (49 MB) *** PRIMARY ***
echo       Detects: D00=Longitudinal, D10=Transverse, D20=Alligator, D40=Pothole
echo    2. pothole_seg_yolov8m.pt     Keremberke       (52 MB) Backup
echo    3. pothole_seg_yolov8n.pt     Keremberke       ( 6 MB) Backup fast
echo    4. pothole_finetune_yolov8.pt Harisanth        (21 MB) Backup
echo    5. crack_seg_yolov8m.pt       OpenSistemas     (52 MB) Secondary crack
echo    6. road_damage_yolov8.pt      Fallback         (21 MB)
echo.
echo  ROW Camera (Road Assets):
echo    7. row_road_objects_yolov8s.pt Aniket YOLOv8s  (21 MB) *** PRIMARY ***
echo       Detects: traffic sign, traffic light, vehicles, pedestrian
echo    8. yolov8m.pt                 COCO YOLOv8m     (49 MB) Secondary
echo       Detects: stop sign, bench, person, car, truck + 74 more
echo.
echo  Base Models:
echo    9. yolov8n.pt                 COCO YOLOv8n     ( 6 MB)
echo   10. yolov8s.pt                 COCO YOLOv8s     (21 MB)
echo.
echo  Total download: ~298 MB
echo  Requires: Internet + HuggingFace token (set in backend/.env)
echo.
echo ============================================================
echo.

cd /d "%~dp0"

echo Checking Python environment...
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Please create virtual environment first.
    echo Run: python -m venv .venv
    pause
    exit /b 1
)

echo Starting model download...
echo.
.venv\Scripts\python.exe backend\scripts\download_models.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo ============================================================
    echo  Setup complete! All models downloaded successfully.
    echo  You can now run:
    echo    start_backend.bat   - Start FastAPI + Celery
    echo    start_frontend.bat  - Start React UI
    echo ============================================================
) else (
    echo ============================================================
    echo  Some models may have failed. Check errors above.
    echo  The system will still work with available models.
    echo ============================================================
)

echo.
pause
