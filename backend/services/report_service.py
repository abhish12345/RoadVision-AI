"""
Report Service — generates Excel (RIS format) and PDF reports.
"""
import io
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, LineChart, Reference, PieChart
from openpyxl.chart.series import DataPoint

logger = logging.getLogger(__name__)

# Condition score colors
SCORE_COLORS = {
    5: "00B050",  # Very Good - Green
    4: "92D050",  # Good - Light Green
    3: "FFFF00",  # Fair - Yellow
    2: "FF9900",  # Poor - Orange
    1: "FF0000",  # Very Poor - Red
}

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
SUBHEADER_FILL = PatternFill("solid", fgColor="2E75B6")
SUBHEADER_FONT = Font(color="FFFFFF", bold=True, size=9)
THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)


def _apply_header(ws, row, col, value, fill=None, font=None, alignment=None):
    cell = ws.cell(row=row, column=col, value=value)
    if fill:
        cell.fill = fill
    if font:
        cell.font = font
    cell.border = THIN_BORDER
    cell.alignment = alignment or Alignment(horizontal='center', vertical='center', wrap_text=True)
    return cell


def generate_pave_excel_report(
    task: Dict,
    video: Dict,
    detections: List[Dict],
    segments: List[Dict],
    output_path: str
) -> str:
    """Generate PAVE camera Excel report in RIS DataTemplate format."""
    wb = openpyxl.Workbook()

    # Remove default sheet
    wb.remove(wb.active)

    # ── Sheet 1: Summary ──────────────────────────────────────────────────────
    ws_summary = wb.create_sheet("Summary")
    _build_summary_sheet(ws_summary, task, video, detections, segments, "pave")

    # ── Sheet 2: Visual Condition (RIS format) ────────────────────────────────
    ws_vc = wb.create_sheet("VisualCondition")
    _build_visual_condition_sheet(ws_vc, task, video, segments)

    # ── Sheet 3: Roughness (RIS format) ──────────────────────────────────────
    ws_rough = wb.create_sheet("Roughness")
    _build_roughness_sheet(ws_rough, task, video, segments)

    # ── Sheet 4: Defect Detail ────────────────────────────────────────────────
    ws_defect = wb.create_sheet("DefectDetail")
    _build_defect_detail_sheet(ws_defect, detections)

    # ── Sheet 5: Charts ───────────────────────────────────────────────────────
    ws_charts = wb.create_sheet("Charts")
    _build_pave_charts(ws_charts, segments, detections)

    wb.save(output_path)
    logger.info(f"PAVE Excel report saved: {output_path}")
    return output_path


def generate_row_excel_report(
    task: Dict,
    video: Dict,
    detections: List[Dict],
    assets: List[Dict],
    output_path: str
) -> str:
    """Generate ROW camera Excel report in RIS DataTemplate format."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ── Sheet 1: Summary ──────────────────────────────────────────────────────
    ws_summary = wb.create_sheet("Summary")
    _build_summary_sheet(ws_summary, task, video, detections, assets, "row")

    # ── Sheet 2: CarriagewayFurniture (RIS format) ────────────────────────────
    ws_cf = wb.create_sheet("CarriagewayFurniture")
    _build_carriageway_furniture_sheet(ws_cf, task, video, assets)

    # ── Sheet 3: Asset Inventory ──────────────────────────────────────────────
    ws_inv = wb.create_sheet("AssetInventory")
    _build_asset_inventory_sheet(ws_inv, assets)

    # ── Sheet 4: Charts ───────────────────────────────────────────────────────
    ws_charts = wb.create_sheet("Charts")
    _build_row_charts(ws_charts, assets)

    wb.save(output_path)
    logger.info(f"ROW Excel report saved: {output_path}")
    return output_path


def _build_summary_sheet(ws, task, video, detections, data, camera_type):
    ws.title = "Summary"
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 40

    # Title
    ws.merge_cells('A1:B1')
    title_cell = ws['A1']
    title_cell.value = "ROAD IDENTIFICATION SYSTEM — SURVEY REPORT"
    title_cell.font = Font(bold=True, size=14, color="FFFFFF")
    title_cell.fill = PatternFill("solid", fgColor="1F3864")
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    rows = [
        ("Task Name", task.get('name', '')),
        ("NH Number", task.get('nh_number', 'NH-033')),
        ("Section Code", task.get('section_code', '')),
        ("Survey Date", task.get('survey_date', '')),
        ("Camera Type", "PAVE Camera (Pavement Defects)" if camera_type == "pave" else "ROW Camera (Road Assets)"),
        ("Video File", video.get('original_filename', '')),
        ("Processing Date", datetime.now().strftime("%d-%m-%Y %H:%M")),
        ("Total Frames Processed", video.get('total_frames_extracted', 0)),
        ("Total Detections", len(detections)),
        ("Road Health Score", f"{task.get('road_health_score', 'N/A')}/100"),
        ("Chainage From (km)", video.get('chainage_start', '')),
        ("Chainage To (km)", video.get('chainage_end', '')),
    ]

    for i, (label, value) in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        ws.cell(row=i, column=1).fill = PatternFill("solid", fgColor="D9E1F2")
        ws.cell(row=i, column=2, value=str(value))
        ws.cell(row=i, column=1).border = THIN_BORDER
        ws.cell(row=i, column=2).border = THIN_BORDER


def _build_visual_condition_sheet(ws, task, video, segments):
    """Build VisualCondition sheet matching RIS DataTemplate format."""
    # Row 1: Title
    ws.merge_cells('A1:AG1')
    ws['A1'] = "Visual Condition"
    ws['A1'].font = Font(bold=True, size=12)
    ws['A1'].fill = HEADER_FILL
    ws['A1'].font = HEADER_FONT

    # Row 2: NH number headers
    headers_r2 = ['As per Old NH number', None, None, 'As per New NH number']
    for i, h in enumerate(headers_r2, 1):
        if h:
            ws.cell(row=2, column=i, value=h).font = Font(bold=True)

    # Row 3: Column headers
    col_headers = [
        'NH Number_old', 'Start Chainage', 'End Chainage',
        'NH Number', 'Section Code', 'Start Chainage', 'End Chainage',
        'Direction', 'Lane Number',
        'StructAll Cracks', 'Wide Cracks', 'Thermal Transverse Cracks',
        'Ravelling', 'PotHoles', 'Edge Break', 'Faulting',
        'Spalled Joint', 'Crack Slab', 'Poor Cracks', 'Failures',
        'Cracking', 'Disintegration', 'Depression', 'Bleeding', 'Patching',
        'Drain Condition', 'Shoulder Condition',
        'Survey Date', 'Latitude', 'Longitude', 'Latitude End', 'Longitude End'
    ]
    for i, h in enumerate(col_headers, 1):
        cell = ws.cell(row=3, column=i, value=h)
        cell.fill = SUBHEADER_FILL
        cell.font = SUBHEADER_FONT
        cell.border = THIN_BORDER
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = 14

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')
    survey_date = task.get('survey_date', '')

    for row_idx, seg in enumerate(segments, start=4):
        defects = seg.get('defects', {})
        row_data = [
            nh_old,
            seg.get('chainage_from', ''),
            seg.get('chainage_to', ''),
            nh_new,
            section,
            seg.get('chainage_from', ''),
            seg.get('chainage_to', ''),
            seg.get('direction', 'Increasing'),
            'L1',
            _score(defects.get('alligator_cracks', 0)),
            _score(defects.get('longitudinal_cracks', 0)),
            _score(defects.get('transverse_cracks', 0)),
            _score(defects.get('bleeding_ravelling', 0)),
            _score(defects.get('potholes', 0)),
            5,  # Edge Break
            5,  # Faulting
            5,  # Spalled Joint
            5,  # Crack Slab
            5,  # Poor Cracks
            5,  # Failures
            _score(defects.get('alligator_cracks', 0) + defects.get('longitudinal_cracks', 0)),
            5,  # Disintegration
            5,  # Depression
            _score(defects.get('bleeding_ravelling', 0)),
            _score(defects.get('patching', 0)),
            3,  # Drain Condition
            3,  # Shoulder Condition
            survey_date,
            seg.get('lat_start', ''),
            seg.get('lon_start', ''),
            seg.get('lat_end', ''),
            seg.get('lon_end', ''),
        ]
        for col_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal='center')
            # Color code score cells
            if isinstance(val, int) and 1 <= val <= 5:
                cell.fill = PatternFill("solid", fgColor=SCORE_COLORS.get(val, "FFFFFF"))


def _build_roughness_sheet(ws, task, video, segments):
    """Build Roughness sheet matching RIS DataTemplate format."""
    ws.merge_cells('A1:X1')
    ws['A1'] = "Roughness"
    ws['A1'].font = HEADER_FONT
    ws['A1'].fill = HEADER_FILL

    col_headers = [
        'UPC', 'RO', 'PIU', 'Project Name',
        'NSV Survey Date', 'NH Number', 'Section Code',
        'Chainage From (km)', 'Chainage To (km)', 'Length (m)',
        'Direction', 'Side', 'Lane Number',
        'LHS Inner IRI (m/km)', 'LHS Outer IRI (m/km)',
        'LHS Inner BI (m/km)', 'LHS Outer BI (m/km)',
        'RHS Inner IRI (m/km)', 'RHS Outer IRI (m/km)',
        'RHS Inner BI (m/km)', 'RHS Outer BI (m/km)',
        'Speed', 'Latitude', 'Longitude'
    ]
    for i, h in enumerate(col_headers, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.fill = SUBHEADER_FILL
        cell.font = SUBHEADER_FONT
        cell.border = THIN_BORDER
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = 14

    nh = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')
    survey_date = task.get('survey_date', '')

    for row_idx, seg in enumerate(segments, start=3):
        iri = seg.get('iri', 2.0)
        row_data = [
            None, None, None, task.get('name', ''),
            survey_date, nh, section,
            seg.get('chainage_from', ''),
            seg.get('chainage_to', ''),
            round((seg.get('chainage_to', 0) - seg.get('chainage_from', 0)) * 1000, 0),
            seg.get('direction', 'Increasing'),
            'LHS', 'L1',
            iri, None,
            round(iri * 720, 1), None,
            None, None, None, None,
            seg.get('speed', 30),
            seg.get('lat_start', ''),
            seg.get('lon_start', ''),
        ]
        for col_idx, val in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=val).border = THIN_BORDER


def _build_defect_detail_sheet(ws, detections):
    """Build detailed defect listing sheet."""
    ws.merge_cells('A1:J1')
    ws['A1'] = "Defect Detection Detail"
    ws['A1'].font = HEADER_FONT
    ws['A1'].fill = HEADER_FILL

    headers = ['Frame No.', 'Timestamp (s)', 'Chainage (km)', 'Latitude', 'Longitude',
               'Defect Type', 'Confidence (%)', 'Severity', 'Image File', 'Survey Date']
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.fill = SUBHEADER_FILL
        cell.font = SUBHEADER_FONT
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(i)].width = 18

    for row_idx, det in enumerate(detections, start=3):
        for d in det.get('detections', []):
            row_data = [
                det.get('frame_number', ''),
                det.get('timestamp_sec', ''),
                det.get('chainage', ''),
                det.get('latitude', ''),
                det.get('longitude', ''),
                d.get('normalized_class', d.get('class_name', '')),
                round(d.get('confidence', 0) * 100, 1),
                _confidence_to_severity(d.get('confidence', 0)),
                det.get('image_filename', ''),
                det.get('survey_date', ''),
            ]
            for col_idx, val in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=val).border = THIN_BORDER
            row_idx += 1


def _build_carriageway_furniture_sheet(ws, task, video, assets):
    """Build CarriagewayFurniture sheet matching RIS DataTemplate format."""
    ws.merge_cells('A1:L1')
    ws['A1'] = "Carriageway Furniture"
    ws['A1'].font = HEADER_FONT
    ws['A1'].fill = HEADER_FILL

    col_headers = [
        'NH Number_Old', 'Start Chainage', 'NH Number', 'Section Code',
        'Chainage', 'Direction', 'EventType', 'Survey Date',
        'Latitude', 'Longitude', 'Altitude', 'Remarks'
    ]
    for i, h in enumerate(col_headers, 1):
        cell = ws.cell(row=3, column=i, value=h)
        cell.fill = SUBHEADER_FILL
        cell.font = SUBHEADER_FONT
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(i)].width = 16

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')

    for row_idx, asset in enumerate(assets, start=4):
        row_data = [
            nh_old,
            asset.get('chainage', ''),
            nh_new,
            section,
            asset.get('chainage', ''),
            asset.get('direction', 'Increasing'),
            _normalize_event_type(asset.get('asset_type', '')),
            asset.get('survey_date', task.get('survey_date', '')),
            asset.get('latitude', ''),
            asset.get('longitude', ''),
            '',
            asset.get('side', '') + ' ' + asset.get('remarks', ''),
        ]
        for col_idx, val in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=val).border = THIN_BORDER


def _build_asset_inventory_sheet(ws, assets):
    """Build asset inventory summary sheet."""
    ws.merge_cells('A1:F1')
    ws['A1'] = "Asset Inventory Summary"
    ws['A1'].font = HEADER_FONT
    ws['A1'].fill = HEADER_FILL

    # Count by type
    type_counts: Dict[str, int] = {}
    for a in assets:
        t = a.get('asset_type', 'unknown')
        type_counts[t] = type_counts.get(t, 0) + 1

    headers = ['Asset Type', 'Count', 'First Chainage', 'Last Chainage', 'Avg Confidence', 'Notes']
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.fill = SUBHEADER_FILL
        cell.font = SUBHEADER_FONT
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(i)].width = 20

    for row_idx, (asset_type, count) in enumerate(sorted(type_counts.items()), start=3):
        type_assets = [a for a in assets if a.get('asset_type') == asset_type]
        chainages = [a.get('chainage', 0) for a in type_assets if a.get('chainage')]
        confs = [a.get('confidence', 0) for a in type_assets]
        row_data = [
            asset_type.replace('_', ' ').title(),
            count,
            min(chainages) if chainages else '',
            max(chainages) if chainages else '',
            round(sum(confs) / len(confs) * 100, 1) if confs else '',
            '',
        ]
        for col_idx, val in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=val).border = THIN_BORDER


def _build_pave_charts(ws, segments, detections):
    """Add IRI line chart and defect bar chart."""
    ws['A1'] = "Charts"
    ws['A1'].font = Font(bold=True, size=12)

    if not segments:
        return

    # IRI data table
    ws['A3'] = "Chainage (km)"
    ws['B3'] = "IRI (m/km)"
    ws['C3'] = "Condition"
    for i, seg in enumerate(segments, start=4):
        ws.cell(row=i, column=1, value=seg.get('chainage_from', ''))
        ws.cell(row=i, column=2, value=seg.get('iri', 2.0))
        ws.cell(row=i, column=3, value=seg.get('condition', 'Good'))

    # IRI Line Chart
    chart = LineChart()
    chart.title = "IRI (Roughness) along Chainage"
    chart.style = 10
    chart.y_axis.title = "IRI (m/km)"
    chart.x_axis.title = "Chainage (km)"
    chart.height = 12
    chart.width = 20

    data_ref = Reference(ws, min_col=2, min_row=3, max_row=3 + len(segments))
    cats_ref = Reference(ws, min_col=1, min_row=4, max_row=3 + len(segments))
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    ws.add_chart(chart, "E3")

    # Defect count table
    defect_types = ['pothole', 'alligator_crack', 'longitudinal_crack',
                    'transverse_crack', 'patching', 'bleeding_ravelling']
    ws['A25'] = "Defect Type"
    ws['B25'] = "Count"
    for i, dt in enumerate(defect_types, start=26):
        count = sum(
            1 for det in detections
            for d in det.get('detections', [])
            if d.get('normalized_class') == dt
        )
        ws.cell(row=i, column=1, value=dt.replace('_', ' ').title())
        ws.cell(row=i, column=2, value=count)

    # Defect Bar Chart
    bar_chart = BarChart()
    bar_chart.title = "Defect Type Distribution"
    bar_chart.style = 10
    bar_chart.y_axis.title = "Count"
    bar_chart.height = 12
    bar_chart.width = 20
    data_ref2 = Reference(ws, min_col=2, min_row=25, max_row=25 + len(defect_types))
    cats_ref2 = Reference(ws, min_col=1, min_row=26, max_row=25 + len(defect_types))
    bar_chart.add_data(data_ref2, titles_from_data=True)
    bar_chart.set_categories(cats_ref2)
    ws.add_chart(bar_chart, "E25")


def _build_row_charts(ws, assets):
    """Add asset distribution pie chart."""
    ws['A1'] = "Asset Charts"
    ws['A1'].font = Font(bold=True, size=12)

    if not assets:
        return

    type_counts: Dict[str, int] = {}
    for a in assets:
        t = a.get('asset_type', 'unknown').replace('_', ' ').title()
        type_counts[t] = type_counts.get(t, 0) + 1

    ws['A3'] = "Asset Type"
    ws['B3'] = "Count"
    for i, (t, c) in enumerate(sorted(type_counts.items()), start=4):
        ws.cell(row=i, column=1, value=t)
        ws.cell(row=i, column=2, value=c)

    pie = PieChart()
    pie.title = "Asset Type Distribution"
    pie.style = 10
    pie.height = 14
    pie.width = 20
    data_ref = Reference(ws, min_col=2, min_row=3, max_row=3 + len(type_counts))
    cats_ref = Reference(ws, min_col=1, min_row=4, max_row=3 + len(type_counts))
    pie.add_data(data_ref, titles_from_data=True)
    pie.set_categories(cats_ref)
    ws.add_chart(pie, "D3")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score(count: int) -> int:
    """Convert defect count to 1-5 condition score."""
    if count == 0:
        return 5
    elif count <= 2:
        return 4
    elif count <= 5:
        return 3
    elif count <= 10:
        return 2
    else:
        return 1


def _confidence_to_severity(conf: float) -> str:
    if conf >= 0.8:
        return "High"
    elif conf >= 0.5:
        return "Medium"
    else:
        return "Low"


def _normalize_event_type(asset_type: str) -> str:
    """Map internal asset type to RIS EventType."""
    mapping = {
        "road_sign": "Road Sign",
        "crash_barrier": "Crash Barrier (Start)",
        "km_stone": "KM Stone",
        "street_light": "Street Light (Start)",
        "wayside_amenity": "Bus Shelter",
        "culvert_bridge": "Culvert",
        "drain": "Drain",
        "retaining_wall": "Retaining Wall",
        "utility_lines": "Utility Lines",
        "median_divider": "Median",
        "service_road": "Service Road",
        "encroachment": "Encroachment",
        "hazard_marker": "Hazard Marker",
    }
    return mapping.get(asset_type, asset_type.replace('_', ' ').title())
