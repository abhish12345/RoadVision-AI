"""
Reports API — Excel, PDF, KML, CSV export endpoints.
"""
import io
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, Response
from bson import ObjectId

from database import get_db
from config import settings

router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = logging.getLogger(__name__)


@router.get("/task/{task_id}/excel")
async def download_task_excel(task_id: str, camera_type: Optional[str] = None):
    """Download Excel report for a task (latest completed video)."""
    db = get_db()
    query = {"task_id": task_id, "status": "completed"}
    if camera_type:
        query["camera_type"] = camera_type

    video = await db.videos.find_one(query, sort=[("created_at", -1)])
    if not video:
        raise HTTPException(status_code=404, detail="No completed video found for this task")

    excel_path = video.get("excel_report_path")
    if not excel_path or not Path(excel_path).exists():
        raise HTTPException(status_code=404, detail="Report not yet generated. Process a video first.")

    cam = video.get("camera_type", "survey")
    filename = f"RIS_Report_{cam.upper()}_{task_id[:8]}.xlsx"
    return FileResponse(
        path=excel_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/task/{task_id}/csv")
async def download_task_csv(task_id: str, camera_type: Optional[str] = None):
    """Download CSV of all detections for a task."""
    db = get_db()
    query = {"task_id": task_id}
    if camera_type:
        query["camera_type"] = camera_type

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "frame_number", "timestamp_sec", "chainage_km",
        "latitude", "longitude", "speed_kmh", "survey_date",
        "camera_type", "detection_class", "confidence_pct",
        "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2",
        "quality_score", "image_filename"
    ])

    async for doc in db.detections.find(query).sort("frame_number", 1):
        for det in doc.get("detections", []):
            writer.writerow([
                doc.get("frame_number", ""),
                doc.get("timestamp_sec", ""),
                doc.get("chainage", ""),
                doc.get("latitude", ""),
                doc.get("longitude", ""),
                doc.get("speed", ""),
                doc.get("survey_date", ""),
                doc.get("camera_type", ""),
                det.get("normalized_class", det.get("class_name", "")),
                round(det.get("confidence", 0) * 100, 1),
                det.get("x1", ""), det.get("y1", ""),
                det.get("x2", ""), det.get("y2", ""),
                doc.get("quality_score", ""),
                doc.get("image_filename", ""),
            ])

    output.seek(0)
    task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    task_name = (task.get("name", task_id) if task else task_id).replace(" ", "_")
    filename = f"detections_{task_name}_{datetime.now().strftime('%Y%m%d')}.csv"

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/task/{task_id}/kml")
async def download_task_kml(task_id: str, camera_type: Optional[str] = None):
    """
    Download KML file for Google Earth / GIS visualization.
    Each detection becomes a placemark with coordinates and description.
    """
    db = get_db()
    query = {
        "task_id": task_id,
        "latitude": {"$ne": None},
        "longitude": {"$ne": None},
        "detections.0": {"$exists": True}
    }
    if camera_type:
        query["camera_type"] = camera_type

    task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    task_name = task.get("name", task_id) if task else task_id

    # KML color map per class
    kml_colors = {
        "pothole": "ff0000ff",
        "alligator_crack": "ff0080ff",
        "longitudinal_crack": "ff00ffff",
        "transverse_crack": "ffff00ff",
        "road_sign": "ff00ff00",
        "crash_barrier": "ff0000ff",
        "km_stone": "ffffff00",
        "street_light": "ff00aaff",
        "drain": "ffaa00ff",
        "default": "ffff8800",
    }

    placemarks = []
    async for doc in db.detections.find(query).sort("chainage", 1).limit(5000):
        lat = doc.get("latitude")
        lon = doc.get("longitude")
        if not lat or not lon:
            continue

        for det in doc.get("detections", []):
            cls = det.get("normalized_class", det.get("class_name", "unknown"))
            conf = round(det.get("confidence", 0) * 100, 1)
            ch = doc.get("chainage", "")
            color = kml_colors.get(cls, kml_colors["default"])

            placemarks.append(f"""
    <Placemark>
      <name>{cls.replace('_', ' ').title()}</name>
      <description><![CDATA[
        <b>Type:</b> {cls.replace('_', ' ').title()}<br/>
        <b>Confidence:</b> {conf}%<br/>
        <b>Chainage:</b> {ch} km<br/>
        <b>Frame:</b> {doc.get('frame_number', '')}<br/>
        <b>Survey Date:</b> {doc.get('survey_date', '')}<br/>
        <b>Camera:</b> {doc.get('camera_type', '').upper()}
      ]]></description>
      <Style>
        <IconStyle>
          <color>{color}</color>
          <scale>0.8</scale>
          <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>
        </IconStyle>
      </Style>
      <Point>
        <coordinates>{lon},{lat},0</coordinates>
      </Point>
    </Placemark>""")

    kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{task_name}</name>
    <description>Road Survey Detections — {task_name}</description>
    {''.join(placemarks)}
  </Document>
</kml>"""

    filename = f"survey_{task_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.kml"
    return Response(
        content=kml_content,
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/task/{task_id}/geojson")
async def download_task_geojson(task_id: str, camera_type: Optional[str] = None):
    """Download GeoJSON for QGIS / web mapping."""
    import json
    db = get_db()
    query = {
        "task_id": task_id,
        "latitude": {"$ne": None},
        "longitude": {"$ne": None},
        "detections.0": {"$exists": True}
    }
    if camera_type:
        query["camera_type"] = camera_type

    features = []
    async for doc in db.detections.find(query).sort("chainage", 1).limit(5000):
        lat = doc.get("latitude")
        lon = doc.get("longitude")
        if not lat or not lon:
            continue

        for det in doc.get("detections", []):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "class": det.get("normalized_class", det.get("class_name", "")),
                    "confidence": round(det.get("confidence", 0) * 100, 1),
                    "chainage": doc.get("chainage"),
                    "frame": doc.get("frame_number"),
                    "camera": doc.get("camera_type"),
                    "survey_date": doc.get("survey_date"),
                    "speed": doc.get("speed"),
                }
            })

    geojson = {"type": "FeatureCollection", "features": features}
    task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    task_name = (task.get("name", task_id) if task else task_id).replace(" ", "_")
    filename = f"survey_{task_name}_{datetime.now().strftime('%Y%m%d')}.geojson"

    return Response(
        content=json.dumps(geojson, indent=2),
        media_type="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/task/{task_id}/pdf")
async def download_task_pdf(task_id: str):
    """Generate and download a PDF summary report."""
    db = get_db()
    try:
        task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Gather stats
    pipeline = [
        {"$match": {"task_id": task_id}},
        {"$group": {
            "_id": None,
            "total_frames": {"$sum": 1},
            "total_detections": {"$sum": {"$size": "$detections"}}
        }}
    ]
    totals = {"total_frames": 0, "total_detections": 0}
    async for doc in db.detections.aggregate(pipeline):
        totals = doc

    class_pipeline = [
        {"$match": {"task_id": task_id}},
        {"$unwind": "$detections"},
        {"$group": {"_id": "$detections.normalized_class", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    class_counts = []
    async for doc in db.detections.aggregate(class_pipeline):
        class_counts.append((doc["_id"] or "unknown", doc["count"]))

    # Generate PDF using reportlab
    pdf_bytes = _generate_pdf(task, totals, class_counts)

    task_name = task.get("name", task_id).replace(" ", "_")
    filename = f"Report_{task_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _generate_pdf(task: dict, totals: dict, class_counts: list) -> bytes:
    """Generate PDF report using ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                  fontSize=18, textColor=colors.HexColor('#1e3a8a'),
                                  spaceAfter=6)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'],
                                    fontSize=13, textColor=colors.HexColor('#1e3a8a'),
                                    spaceBefore=12, spaceAfter=6)
    normal_style = styles['Normal']
    normal_style.fontSize = 10

    story = []

    # Title
    story.append(Paragraph("Road Identification System", title_style))
    story.append(Paragraph("Survey Analysis Report", styles['Heading2']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1e3a8a')))
    story.append(Spacer(1, 0.4*cm))

    # Task info table
    health = task.get('road_health_score')
    health_str = f"{health:.1f}/100" if health is not None else "N/A"
    health_color = colors.green if health and health >= 70 else colors.orange if health and health >= 40 else colors.red

    info_data = [
        ["Task Name", task.get('name', '')],
        ["NH Number", task.get('nh_number', '')],
        ["Section Code", task.get('section_code', '')],
        ["Survey Date", task.get('survey_date', '')],
        ["Status", task.get('status', '').upper()],
        ["Road Health Score", health_str],
        ["Total Frames Processed", str(totals.get('total_frames', 0))],
        ["Total Detections", str(totals.get('total_detections', 0))],
        ["Report Generated", datetime.now().strftime("%d-%m-%Y %H:%M")],
    ]

    info_table = Table(info_data, colWidths=[5*cm, 11*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#dbeafe')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    # Detection summary
    if class_counts:
        story.append(Paragraph("Detection Summary", heading_style))
        det_data = [["Detection Class", "Count", "% of Total"]]
        total_det = sum(c for _, c in class_counts)
        for cls, count in class_counts:
            pct = f"{count/total_det*100:.1f}%" if total_det > 0 else "0%"
            det_data.append([cls.replace('_', ' ').title(), str(count), pct])

        det_table = Table(det_data, colWidths=[9*cm, 4*cm, 4*cm])
        det_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(det_table)
        story.append(Spacer(1, 0.5*cm))

    # Road condition legend
    story.append(Paragraph("Road Condition Scale (IRI)", heading_style))
    legend_data = [
        ["Condition", "IRI Range (m/km)", "Score"],
        ["Very Good", "< 2.0", "5"],
        ["Good", "2.0 – 4.0", "4"],
        ["Fair", "4.0 – 6.0", "3"],
        ["Poor", "6.0 – 8.0", "2"],
        ["Very Poor", "> 8.0", "1"],
    ]
    legend_colors = [
        colors.HexColor('#1e3a8a'),
        colors.HexColor('#00B050'),
        colors.HexColor('#92D050'),
        colors.HexColor('#FFFF00'),
        colors.HexColor('#FF9900'),
        colors.HexColor('#FF0000'),
    ]
    legend_table = Table(legend_data, colWidths=[6*cm, 6*cm, 5*cm])
    ts = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]
    for i, color in enumerate(legend_colors[1:], start=1):
        ts.append(('BACKGROUND', (0, i), (0, i), color))
    legend_table.setStyle(TableStyle(ts))
    story.append(legend_table)

    # Footer
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1')))
    story.append(Paragraph(
        f"Generated by Road Identification System | {datetime.now().strftime('%d %B %Y')}",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8,
                       textColor=colors.HexColor('#94a3b8'), alignment=TA_CENTER)
    ))

    doc.build(story)
    return buffer.getvalue()
