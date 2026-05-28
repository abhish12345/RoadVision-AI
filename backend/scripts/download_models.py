"""
Model Downloader Script
Run once before starting the server to pre-download all required models.

Usage:
    python scripts/download_models.py

Models downloaded (10 total):

  PAVE Camera — 4 models run in PARALLEL:
    1. rdd2022_yolov8m.pt         — RDD2022 YOLOv8m, D00/D10/D20/D40 (49 MB) *** PRIMARY ***
    2. crack_seg_yolov8m.pt       — OpenSistemas, crack segmentation   (52 MB) *** PARALLEL ***
    3. pothole_seg_yolov8m.pt     — keremberke, pothole segmentation   (52 MB) *** PARALLEL ***
    4. pothole_finetune_yolov8.pt — Harisanth, pothole fine-tuned      (21 MB) *** PARALLEL ***
    5. road_damage_yolov8.pt      — fallback (yolov8s copy)            (21 MB)

  ROW Camera — 2 models run in PARALLEL:
    6. row_road_objects_yolov8s.pt — Aniket, traffic sign/light/vehicles (21 MB) *** PRIMARY ***
    7. yolov8m.pt                  — Ultralytics COCO 80 classes         (49 MB) *** PARALLEL ***

  Base models:
    8. yolov8n.pt  — Ultralytics COCO nano  (6 MB)
    9. yolov8s.pt  — Ultralytics COCO small (21 MB)
   10. (road_damage_yolov8.pt = copy of yolov8s)

  Total: ~298 MB
"""
import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ultralytics import YOLO
from config import settings

MODELS_DIR = settings.get_models_path()

print("=" * 65)
print("RoadVision AI — Model Downloader")
print("=" * 65)
print(f"Models directory: {MODELS_DIR}")
print()


def download_ultralytics(model_name: str, desc: str):
    dest = MODELS_DIR / model_name
    if dest.exists():
        print(f"  ✓ {model_name} already exists ({dest.stat().st_size // 1024 // 1024} MB)")
        return
    print(f"  ↓ Downloading {model_name} — {desc}")
    try:
        model = YOLO(model_name)
        cwd_file = Path(model_name)
        if cwd_file.exists():
            shutil.move(str(cwd_file), str(dest))
        else:
            model.save(str(dest))
        print(f"    ✓ Saved ({dest.stat().st_size // 1024 // 1024} MB)")
    except Exception as e:
        print(f"    ✗ Failed: {e}")


def download_huggingface(repo_id: str, filename: str, dest_name: str, desc: str):
    dest = MODELS_DIR / dest_name
    if dest.exists():
        print(f"  ✓ {dest_name} already exists ({dest.stat().st_size // 1024 // 1024} MB)")
        return
    print(f"  ↓ Downloading {dest_name} from {repo_id} — {desc}")
    try:
        from huggingface_hub import hf_hub_download
        token = settings.HF_TOKEN if settings.HF_TOKEN else None
        path = hf_hub_download(repo_id=repo_id, filename=filename,
                               local_dir=str(MODELS_DIR), token=token)
        shutil.copy(path, dest)
        print(f"    ✓ Saved ({dest.stat().st_size // 1024 // 1024} MB)")
    except Exception as e:
        print(f"    ✗ Failed: {e}")


def setup_road_damage_fallback():
    """
    road_damage_yolov8.pt is the last-resort fallback.
    Since we now have 3 dedicated pothole models, this is rarely used.
    We keep it as yolov8s copy for compatibility.
    """
    dest = MODELS_DIR / "road_damage_yolov8.pt"
    if dest.exists():
        print(f"  ✓ road_damage_yolov8.pt already exists (fallback)")
        return
    src = MODELS_DIR / "yolov8s.pt"
    if src.exists():
        shutil.copy(src, dest)
        print(f"  ✓ Created road_damage_yolov8.pt (yolov8s fallback — only used if all pothole models missing)")
    else:
        model = YOLO("yolov8s.pt")
        model.save(str(dest))
        print(f"  ✓ Created road_damage_yolov8.pt")


def check_easyocr():
    print("  ↓ Pre-loading EasyOCR English model...")
    try:
        import easyocr
        easyocr.Reader(['en'], gpu=False, verbose=False)
        print("    ✓ EasyOCR ready")
    except Exception as e:
        print(f"    ✗ EasyOCR failed: {e}")


if __name__ == "__main__":

    print("[1/4] Downloading Ultralytics base models...")
    download_ultralytics("yolov8n.pt", "COCO nano — fast general detection")
    download_ultralytics("yolov8s.pt", "COCO small — PAVE fallback")
    download_ultralytics("yolov8m.pt", "COCO medium — ROW camera")

    print()
    print("[2/4] Downloading PAVE camera models (pothole + crack)...")
    download_huggingface(
        "vishnus23d158/Road-Damage-Detection", "best (3).pt",
        "rdd2022_yolov8m.pt",
        "RDD2022 YOLOv8m — D00/D10/D20/D40 (longitudinal/transverse/alligator/pothole) BEST"
    )
    download_huggingface(
        "keremberke/yolov8m-pothole-segmentation", "best.pt",
        "pothole_seg_yolov8m.pt",
        "YOLOv8m pothole segmentation — backup"
    )
    download_huggingface(
        "keremberke/yolov8n-pothole-segmentation", "best.pt",
        "pothole_seg_yolov8n.pt",
        "YOLOv8n pothole segmentation — fast backup"
    )
    download_huggingface(
        "Harisanth/Pothole-Finetuned-YOLOv8", "best.pt",
        "pothole_finetune_yolov8.pt",
        "Fine-tuned pothole detector — backup"
    )
    download_huggingface(
        "OpenSistemas/YOLOv8-crack-seg", "yolov8m/weights/best.pt",
        "crack_seg_yolov8m.pt",
        "YOLOv8m crack segmentation — secondary model"
    )
    setup_road_damage_fallback()

    print()
    print("[3/5] Downloading ROW camera models...")
    download_huggingface(
        "Aniket200325/road_object_detection_yolov8", "best.pt",
        "row_road_objects_yolov8s.pt",
        "Road objects: traffic sign, traffic light, vehicles, pedestrian (10 classes)"
    )

    print()
    print("[4/5] Pre-loading EasyOCR...")
    check_easyocr()

    print()
    print("[5/5] Verifying all models...")
    from services.model_manager import list_available_models
    status = list_available_models()
    all_ok = True
    for name, info in status.items():
        icon = "✓" if info["available"] else "✗"
        size = f"{info.get('size_mb','?')} MB" if info["available"] else "MISSING"
        print(f"  [{icon}] {name:<30} {size}")
        if not info["available"] and name in ("rdd2022_yolov8m", "crack_seg_yolov8m",
                                               "row_road_objects_yolov8s", "yolov8m_coco"):
            all_ok = False

    print()
    print("=" * 65)
    if all_ok:
        print("✓ All critical models ready!")
    else:
        print("⚠ Some models missing — check errors above")
    print("=" * 65)
    print()
    print("Start the system:")
    print("  start_backend.bat   — FastAPI + Celery")
    print("  start_frontend.bat  — React UI at http://localhost:5173")
