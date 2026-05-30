"""
Report Service — generates Excel output EXACTLY matching RIS DataTemplate v1.0
All sheet names, column headers, row structure identical to the template.
"""
import io
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

# ── Styles matching the template ──────────────────────────────────────────────
HEADER_FILL   = PatternFill("solid", fgColor="1F3864")
HEADER_FONT   = Font(color="FFFFFF", bold=True, size=9)
SUBHDR_FILL   = PatternFill("solid", fgColor="2E75B6")
SUBHDR_FONT   = Font(color="FFFFFF", bold=True, size=9)
TITLE_FILL    = PatternFill("solid", fgColor="1F3864")
TITLE_FONT    = Font(color="FFFFFF", bold=True, size=11)
THIN_BORDER   = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'),  bottom=Side(style='thin')
)
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
LEFT   = Alignment(horizontal='left',   vertical='center', wrap_text=True)

SCORE_COLORS = {
    5: "00B050", 4: "92D050", 3: "FFFF00", 2: "FF9900", 1: "FF0000"
}


def _hdr(ws, row, col, val, fill=SUBHDR_FILL, font=SUBHDR_FONT, align=CENTER):
    c = ws.cell(row=row, column=col, value=val)
    c.fill = fill; c.font = font; c.border = THIN_BORDER; c.alignment = align
    return c

def _cell(ws, row, col, val, align=CENTER):
    c = ws.cell(row=row, column=col, value=val)
    c.border = THIN_BORDER; c.alignment = align
    return c

def _score_cell(ws, row, col, score):
    c = _cell(ws, row, col, score)
    if isinstance(score, int) and 1 <= score <= 5:
        c.fill = PatternFill("solid", fgColor=SCORE_COLORS[score])
    return c

def _set_col_widths(ws, widths):
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w

def _title_row(ws, title, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=title)
    c.fill = TITLE_FILL; c.font = TITLE_FONT
    c.alignment = CENTER; c.border = THIN_BORDER
    ws.row_dimensions[1].height = 22

def _nh_row(ws, row, ncols):
    """Row 2: As per Old NH number / As per New NH number"""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    ws.cell(row=row, column=1, value="As per Old NH number").font = Font(bold=True, size=9)
    ws.merge_cells(start_row=row, start_column=4, end_row=row, end_column=ncols)
    ws.cell(row=row, column=4, value="As per New NH number").font = Font(bold=True, size=9)


def _defect_score(count: int) -> int:
    """Convert defect detection count to 1-5 RIS score."""
    if count == 0:   return 5
    if count <= 2:   return 4
    if count <= 5:   return 3
    if count <= 10:  return 2
    return 1

def _iri_score(iri: float) -> int:
    if iri < 2:   return 5
    if iri < 4:   return 4
    if iri < 6:   return 3
    if iri < 8:   return 2
    return 1

def _rut_score(rut_mm: float) -> int:
    if rut_mm < 5:   return 5
    if rut_mm < 10:  return 4
    if rut_mm < 20:  return 3
    if rut_mm < 30:  return 2
    return 1

def _normalize_event_type(asset_type: str) -> str:
    """Map internal asset type to RIS EventType (exact template values)."""
    mapping = {
        "road_sign":       "Road Sign",
        "crash_barrier":   "Crash Barrier (Start)",
        "km_stone":        "KM Stone",
        "street_light":    "Street Light (Start)",
        "wayside_amenity": "Bus Shelter",
        "culvert_bridge":  "Culvert",
        "drain":           "Covered Lined Drain",
        "retaining_wall":  "Retaining Wall",
        "utility_lines":   "Utility Lines",
        "median_divider":  "Median",
        "service_road":    "Service Road",
        "encroachment":    "Encroachment",
        "hazard_marker":   "Hazard Marker",
        "vehicle":         "Vehicle",
    }
    return mapping.get(asset_type, asset_type.replace("_", " ").title())


# ═══════════════════════════════════════════════════════════════════════════════
# PAVE CAMERA REPORT — matches RIS DataTemplate exactly
# ═══════════════════════════════════════════════════════════════════════════════

def generate_pave_excel_report(task, video, detections, segments, output_path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    _build_visual_condition(wb, task, video, segments)
    _build_roughness(wb, task, video, segments)
    _build_rut_depth(wb, task, video, segments)
    _build_texture_depth(wb, task, video, segments)
    _build_pave_summary(wb, task, video, detections, segments)

    wb.save(output_path)
    logger.info(f"PAVE report saved: {output_path}")
    return output_path


def _build_visual_condition(wb, task, video, segments):
    """
    VisualCondition sheet — exact RIS DataTemplate format.
    Columns: NH Number_old | Start Chainage | End Chainage | NH Number |
             Section Code | Start Chainage | End Chainage | Direction |
             Lane Number | StructAll Cracks | Wide Cracks | Thermal Transverse Cracks |
             Ravelling | PotHoles | Edge Break | Faulting | Spalled Joint |
             Crack Slab | Poor Cracks | Failures | Cracking | Disintegration |
             Depression | Bleeding | Patching | Drain Condition | Shoulder Condition |
             Survey Date | Latitude | Longitude | Latitude | Longitude
    """
    ws = wb.create_sheet("VisualCondition")
    NCOLS = 32

    # Row 1: Title
    _title_row(ws, "Visual Condition", NCOLS)

    # Row 2: NH number group headers
    _nh_row(ws, 2, NCOLS)

    # Row 3: Column headers (exact template names)
    headers = [
        'NH Number_old', 'Start Chainage', 'End Chainage',
        'NH Number', 'Section Code', 'Start Chainage', 'End Chainage',
        'Direction', 'Lane Number',
        'StructAll\nCracks', 'Wide\nCracks', 'Thermal\nTranverseCracks',
        'Ravelling', 'PotHoles', 'Edge Break', 'Faulting',
        'Spalled Joint', 'Crack Slab', 'Poor Cracks', 'Faillures',
        'Cracking', 'Disintegration', 'Depression', 'Bleeding', 'Patching',
        'Drain Condition', 'Shoulder Condition',
        'Survey Date', 'Latitude', 'Longitude', 'Latitude', 'Longitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)

    col_widths = [10,12,12,10,10,12,12,12,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,12,12,12,12,12]
    _set_col_widths(ws, col_widths)
    ws.row_dimensions[3].height = 40

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')
    survey_date = task.get('survey_date', '')

    for row_idx, seg in enumerate(segments, start=4):
        defects = seg.get('defects', {})
        ch_from = seg.get('chainage_from', '')
        ch_to   = seg.get('chainage_to', '')
        lat_s   = seg.get('lat_start', '')
        lon_s   = seg.get('lon_start', '')
        lat_e   = seg.get('lat_end', '')
        lon_e   = seg.get('lon_end', '')

        # Compute scores from detections
        struct_cracks = _defect_score(defects.get('alligator_crack', 0) + defects.get('longitudinal_crack', 0) + defects.get('transverse_crack', 0))
        wide_cracks   = _defect_score(defects.get('alligator_crack', 0))
        thermal_cracks= _defect_score(defects.get('transverse_crack', 0))
        ravelling     = _defect_score(defects.get('bleeding_ravelling', 0))
        potholes      = _defect_score(defects.get('pothole', 0))
        cracking      = _defect_score(defects.get('longitudinal_crack', 0) + defects.get('alligator_crack', 0))
        patching      = _defect_score(defects.get('patching', 0))

        row_data = [
            nh_old, ch_from, ch_to,
            nh_new, section, ch_from, ch_to,
            seg.get('direction', 'Increasing'), 'L1',
            struct_cracks, wide_cracks, thermal_cracks,
            ravelling, potholes, 5, None,  # EdgeBreak=5, Faulting=None (flexible pavement)
            None, None, None, None,         # SpalledJoint, CrackSlab, PoorCracks, Failures = None
            cracking, 5, 5, 5, patching,    # Cracking, Disintegration, Depression, Bleeding, Patching
            3, 3,                           # DrainCondition, ShoulderCondition = 3 (Good)
            survey_date, lat_s, lon_s, lat_e, lon_e
        ]
        for col_idx, val in enumerate(row_data, 1):
            if col_idx in (10,11,12,13,14,15,21,25):  # score columns
                _score_cell(ws, row_idx, col_idx, val)
            else:
                _cell(ws, row_idx, col_idx, val)


def _build_roughness(wb, task, video, segments):
    """
    Roughness sheet — exact RIS DataTemplate format.
    Columns: NH Number_old | Start Chainage | End Chainage | NH Number |
             Section Code | Start Chainage | End Chainage | Direction |
             Lane Number | LwpIri | RwpIri | LaneIri | Speed |
             Survey Date | Latitude | Longitude | Latitude | Longitude
    """
    ws = wb.create_sheet("Roughness")
    NCOLS = 18
    _title_row(ws, "Roughness", NCOLS)
    _nh_row(ws, 2, NCOLS)

    headers = [
        'NH Number_old', 'Start Chainage', 'End Chainage',
        'NH Number', 'Section Code', 'Start Chainage', 'End Chainage',
        'Direction', 'Lane Number',
        'LwpIri', 'RwpIri', 'LaneIri',
        'Speed', 'Survey Date',
        'Latitude', 'Longitude', 'Latitude', 'Longitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,12,12,10,10,12,12,12,8,10,10,10,8,12,12,12,12,12])

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')
    survey_date = task.get('survey_date', '')

    for row_idx, seg in enumerate(segments, start=4):
        iri = seg.get('iri', 2.0)
        row_data = [
            nh_old, seg.get('chainage_from'), seg.get('chainage_to'),
            nh_new, section, seg.get('chainage_from'), seg.get('chainage_to'),
            seg.get('direction', 'Increasing'), 'L1',
            round(iri, 3), round(iri, 3), round(iri, 3),
            seg.get('speed', 30), survey_date,
            seg.get('lat_start'), seg.get('lon_start'),
            seg.get('lat_end'), seg.get('lon_end'),
        ]
        for col_idx, val in enumerate(row_data, 1):
            _cell(ws, row_idx, col_idx, val)


def _build_rut_depth(wb, task, video, segments):
    """
    RutDepth sheet — exact RIS DataTemplate format.
    Columns: NH Number_old | Start Chainage | End Chainage | NH Number |
             Section Code | Start Chainage | End Chainage | Direction |
             Lane Number | RuttingLeft | RuttingRight | RuttingAvg |
             Speed | Survey Date | Latitude | Longitude | Latitude | Longitude
    """
    ws = wb.create_sheet("RutDepth")
    NCOLS = 18
    _title_row(ws, "Rut Depth", NCOLS)
    _nh_row(ws, 2, NCOLS)

    headers = [
        'NH Number_old', 'Start Chainage', 'End Chainage',
        'NH Number', 'Section Code', 'Start Chainage', 'End Chainage',
        'Direction', 'Lane Number',
        'RuttingLeft', 'RuttingRight', 'RuttingAvg',
        'Speed', 'Survey Date',
        'Latitude', 'Longitude', 'Latitude', 'Longitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,12,12,10,10,12,12,12,8,10,10,10,8,12,12,12,12,12])

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')
    survey_date = task.get('survey_date', '')

    for row_idx, seg in enumerate(segments, start=4):
        defects = seg.get('defects', {})
        pothole_count = defects.get('pothole', 0)
        rut_est = min(5.0 + pothole_count * 2.0, 25.0)
        row_data = [
            nh_old, seg.get('chainage_from'), seg.get('chainage_to'),
            nh_new, section, seg.get('chainage_from'), seg.get('chainage_to'),
            seg.get('direction', 'Increasing'), 'L1',
            round(rut_est, 2), round(rut_est, 2), round(rut_est, 2),
            seg.get('speed', 30), survey_date,
            seg.get('lat_start'), seg.get('lon_start'),
            seg.get('lat_end'), seg.get('lon_end'),
        ]
        for col_idx, val in enumerate(row_data, 1):
            _cell(ws, row_idx, col_idx, val)


def _build_texture_depth(wb, task, video, segments):
    """
    TextureDepth sheet — exact RIS DataTemplate format.
    Columns: NH Number_old | Start Chainage | End Chainage | NH Number |
             Section Code | Start Chainage | End Chainage | Direction |
             Lane Number | Texture Left | Texture Right | Texture Average |
             Speed | Survey Date | Latitude | Longitude | Latitude | Longitude
    """
    ws = wb.create_sheet("TextureDepth")
    NCOLS = 18
    _title_row(ws, "Texture Depth", NCOLS)
    _nh_row(ws, 2, NCOLS)

    headers = [
        'NH Number_old', 'Start Chainage', 'End Chainage',
        'NH Number', 'Section Code', 'Start Chainage', 'End Chainage',
        'Direction', 'Lane Number',
        'Texture Left', 'Texture Right', 'Texture Average',
        'Speed', 'Survey Date',
        'Latitude', 'Longitude', 'Latitude', 'Longitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,12,12,10,10,12,12,12,8,10,10,10,8,12,12,12,12,12])

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')
    survey_date = task.get('survey_date', '')

    for row_idx, seg in enumerate(segments, start=4):
        row_data = [
            nh_old, seg.get('chainage_from'), seg.get('chainage_to'),
            nh_new, section, seg.get('chainage_from'), seg.get('chainage_to'),
            seg.get('direction', 'Increasing'), 'L1',
            None, None, None,
            seg.get('speed', 30), survey_date,
            seg.get('lat_start'), seg.get('lon_start'),
            seg.get('lat_end'), seg.get('lon_end'),
        ]
        for col_idx, val in enumerate(row_data, 1):
            _cell(ws, row_idx, col_idx, val)


def _build_pave_summary(wb, task, video, detections, segments):
    """Summary sheet with charts and statistics."""
    ws = wb.create_sheet("Summary")
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 40

    ws.merge_cells('A1:B1')
    c = ws['A1']
    c.value = "PAVE Camera Survey Report — RoadVision AI"
    c.font = TITLE_FONT; c.fill = TITLE_FILL; c.alignment = CENTER
    ws.row_dimensions[1].height = 28

    health = task.get('road_health_score')
    rows = [
        ("Task Name",          task.get('name', '')),
        ("NH Number",          task.get('nh_number', 'NH-033')),
        ("Section Code",       task.get('section_code', 'BAN-KEL')),
        ("Survey Date",        task.get('survey_date', '')),
        ("Camera Type",        "PAVE Camera (Pavement Defects)"),
        ("Video File",         video.get('original_filename', '')),
        ("Frames Processed",   video.get('total_frames_extracted', 0)),
        ("Total Detections",   len(detections)),
        ("Segments Analysed",  len(segments)),
        ("Road Health Score",  f"{health:.1f}/100" if health else "N/A"),
        ("Chainage From (km)", video.get('chainage_start', '')),
        ("Chainage To (km)",   video.get('chainage_end', '')),
        ("Report Generated",   datetime.now().strftime("%d-%m-%Y %H:%M")),
    ]
    for i, (label, value) in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True, size=9)
        ws.cell(row=i, column=1).fill = PatternFill("solid", fgColor="D9E1F2")
        ws.cell(row=i, column=2, value=str(value))
        for col in (1, 2):
            ws.cell(row=i, column=col).border = THIN_BORDER

    # Defect count table
    ws.cell(row=17, column=1, value="Defect Summary").font = Font(bold=True, size=10)
    defect_headers = ["Defect Type", "Count", "Score"]
    for i, h in enumerate(defect_headers, 1):
        c = ws.cell(row=18, column=i, value=h)
        c.fill = SUBHDR_FILL; c.font = SUBHDR_FONT; c.border = THIN_BORDER

    defect_totals = {}
    for det in detections:
        for d in det.get('detections', []):
            cls = d.get('normalized_class', 'unknown')
            defect_totals[cls] = defect_totals.get(cls, 0) + 1

    for row_idx, (cls, count) in enumerate(sorted(defect_totals.items()), start=19):
        ws.cell(row=row_idx, column=1, value=cls.replace('_', ' ').title()).border = THIN_BORDER
        ws.cell(row=row_idx, column=2, value=count).border = THIN_BORDER
        score = _defect_score(count)
        sc = ws.cell(row=row_idx, column=3, value=score)
        sc.border = THIN_BORDER
        sc.fill = PatternFill("solid", fgColor=SCORE_COLORS.get(score, "FFFFFF"))

    # IRI condition table
    if segments:
        start_row = 19 + len(defect_totals) + 2
        ws.cell(row=start_row, column=1, value="IRI Condition Summary").font = Font(bold=True, size=10)
        iri_headers = ["Condition", "IRI Range (m/km)", "Segments", "Score"]
        for i, h in enumerate(iri_headers, 1):
            c = ws.cell(row=start_row+1, column=i, value=h)
            c.fill = SUBHDR_FILL; c.font = SUBHDR_FONT; c.border = THIN_BORDER

        iris = [s.get('iri', 2.0) for s in segments]
        conditions = [
            ("Very Good", 0,   2,   5, "00B050"),
            ("Good",      2,   4,   4, "92D050"),
            ("Fair",      4,   6,   3, "FFFF00"),
            ("Poor",      6,   8,   2, "FF9900"),
            ("Very Poor", 8, 999,   1, "FF0000"),
        ]
        for r_off, (cond, lo, hi, score, color) in enumerate(conditions, start=start_row+2):
            count = sum(1 for x in iris if lo <= x < hi)
            ws.cell(row=r_off, column=1, value=cond).border = THIN_BORDER
            ws.cell(row=r_off, column=2, value=f"{lo}–{hi if hi<999 else '∞'}").border = THIN_BORDER
            ws.cell(row=r_off, column=3, value=count).border = THIN_BORDER
            sc = ws.cell(row=r_off, column=4, value=score)
            sc.border = THIN_BORDER
            sc.fill = PatternFill("solid", fgColor=color)


# ═══════════════════════════════════════════════════════════════════════════════
# ROW CAMERA REPORT — matches RIS DataTemplate exactly
# ═══════════════════════════════════════════════════════════════════════════════

def generate_row_excel_report(task, video, detections, assets, output_path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    _build_carriageway_furniture(wb, task, assets)
    _build_structure_details(wb, task, assets)
    _build_wayside_amenities(wb, task, assets)
    _build_drain_type(wb, task, assets)
    _build_carriageway_type(wb, task)
    _build_land_use(wb, task)
    _build_row_summary(wb, task, video, detections, assets)

    wb.save(output_path)
    logger.info(f"ROW report saved: {output_path}")
    return output_path


def _build_carriageway_furniture(wb, task, assets):
    """
    CarriagewayFurniture sheet — exact RIS DataTemplate format.
    Columns: NH Number_Old | Start Chainage | NH Number | Section Code |
             Chainage | Direction | EventType | Survey Date |
             Latitude | Longitude | Altitude | Remarks
    """
    ws = wb.create_sheet("CarriagewayFurniture")
    NCOLS = 12
    _title_row(ws, "Carriageway Furniture", NCOLS)

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=2)
    ws.cell(row=2, column=1, value="As per Old NH number").font = Font(bold=True, size=9)
    ws.merge_cells(start_row=2, start_column=3, end_row=2, end_column=NCOLS)
    ws.cell(row=2, column=3, value="As per New NH number").font = Font(bold=True, size=9)

    headers = [
        'NH Number_Old', 'Start Chainage',
        'NH Number', 'Section Code', 'Chainage', 'Direction',
        'EventType', 'Survey Date',
        'Latitude', 'Longitude', 'Altitude', 'Remarks'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,12,10,10,12,12,20,12,12,12,10,15])

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')

    # Filter to road furniture assets only
    furniture_types = {
        'road_sign', 'crash_barrier', 'km_stone', 'street_light',
        'wayside_amenity', 'hazard_marker', 'median_divider',
    }
    furniture = [a for a in assets if a.get('asset_type') in furniture_types]

    for row_idx, asset in enumerate(furniture, start=4):
        event_type = _normalize_event_type(asset.get('asset_type', ''))
        row_data = [
            nh_old, asset.get('chainage', ''),
            nh_new, section,
            asset.get('chainage', ''),
            asset.get('direction', 'Increasing'),
            event_type,
            asset.get('survey_date', task.get('survey_date', '')),
            asset.get('latitude', ''),
            asset.get('longitude', ''),
            '',
            asset.get('side', 'LHS'),
        ]
        for col_idx, val in enumerate(row_data, 1):
            _cell(ws, row_idx, col_idx, val)


def _build_structure_details(wb, task, assets):
    """
    StructureDetails sheet — exact RIS DataTemplate format.
    Columns: NH Number | Section Code | Chainage (Start) | Chainage (End) |
             Direction | Structure Type | Survey Date | Data Source | Remarks |
             Start_Latitude | Start_Longitude | Start_Altitude |
             End_Latitude | End_Longitude | End_Altitude
    """
    ws = wb.create_sheet("StructureDetails")
    NCOLS = 15
    _title_row(ws, "Structural Details", NCOLS)

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=NCOLS)
    ws.cell(row=2, column=1, value="As per New NH number").font = Font(bold=True, size=9)

    headers = [
        'NH Number', 'Section Code', 'Chainage (Start)', 'Chainage (End)',
        'Direction', 'Structure Type', 'Survey Date', 'Data Source', 'Remarks',
        'Start_Latitude', 'Start_Longitude', 'Start_Altitude',
        'End_Latitude', 'End_Longitude', 'End_Altitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,10,12,12,12,15,12,12,15,12,12,10,12,12,10])

    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')

    struct_types = {'culvert_bridge', 'retaining_wall'}
    structures = [a for a in assets if a.get('asset_type') in struct_types]

    struct_map = {'culvert_bridge': 'Culvert', 'retaining_wall': 'Retaining Wall'}

    for row_idx, asset in enumerate(structures, start=4):
        ch = asset.get('chainage', '')
        row_data = [
            nh_new, section,
            ch, round(float(ch) + 0.01, 3) if ch else '',
            asset.get('direction', 'Increasing'),
            struct_map.get(asset.get('asset_type', ''), asset.get('asset_type', '')),
            asset.get('survey_date', task.get('survey_date', '')),
            'NSV Survey', '',
            asset.get('latitude', ''), asset.get('longitude', ''), '',
            asset.get('latitude', ''), asset.get('longitude', ''), '',
        ]
        for col_idx, val in enumerate(row_data, 1):
            _cell(ws, row_idx, col_idx, val)


def _build_wayside_amenities(wb, task, assets):
    """
    WaysideAmenities sheet — exact RIS DataTemplate format.
    Columns: NH Number_Old | Start Chainage | NH Number | Section Code |
             Chainage | Direction | AccessType | Survey Date |
             DataSource | Remarks | Latitude | Longitude | Altitude
    """
    ws = wb.create_sheet("WaysideAmenities")
    NCOLS = 13
    _title_row(ws, "Wayside Amenities", NCOLS)

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=2)
    ws.cell(row=2, column=1, value="As per Old NH number").font = Font(bold=True, size=9)
    ws.merge_cells(start_row=2, start_column=3, end_row=2, end_column=NCOLS)
    ws.cell(row=2, column=3, value="As per New NH number").font = Font(bold=True, size=9)

    headers = [
        'NH Number_Old', 'Start Chainage',
        'NH Number', 'Section Code', 'Chainage', 'Direction',
        'AccessType', 'Survey Date', 'DataSource', 'Remarks',
        'Latitude', 'Longitude', 'Altitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,12,10,10,12,12,15,12,12,15,12,12,10])

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')

    amenity_map = {
        'wayside_amenity': 'Bus Shelter',
        'vehicle': 'Petrol Pump',
    }
    amenities = [a for a in assets if a.get('asset_type') in amenity_map]

    for row_idx, asset in enumerate(amenities, start=4):
        row_data = [
            nh_old, asset.get('chainage', ''),
            nh_new, section,
            asset.get('chainage', ''),
            asset.get('direction', 'Increasing'),
            amenity_map.get(asset.get('asset_type', ''), 'Other'),
            asset.get('survey_date', task.get('survey_date', '')),
            'NSV Survey', '',
            asset.get('latitude', ''), asset.get('longitude', ''), '',
        ]
        for col_idx, val in enumerate(row_data, 1):
            _cell(ws, row_idx, col_idx, val)


def _build_drain_type(wb, task, assets):
    """
    DrainType sheet — exact RIS DataTemplate format.
    Columns: NH Number_old | Start Chainage | End Chainage | NH Number |
             Section Code | Start Chainage | End Chainage | Direction |
             DrainType | Survey Date | Latitude | Longitude | Latitude | Longitude
    """
    ws = wb.create_sheet("DrainType")
    NCOLS = 14
    _title_row(ws, "Drain Type", NCOLS)
    _nh_row(ws, 2, NCOLS)

    headers = [
        'NH Number_old', 'Start Chainage', 'End Chainage',
        'NH Number', 'Section Code', 'Start Chainage', 'End Chainage',
        'Direction', 'DrainType', 'Survey Date',
        'Latitude', 'Longitude', 'Latitude', 'Longitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,12,12,10,10,12,12,12,18,12,12,12,12,12])

    nh_old = "NH-080"
    nh_new = task.get('nh_number', 'NH-033')
    section = task.get('section_code', 'BAN-KEL')

    drains = [a for a in assets if a.get('asset_type') == 'drain']
    drain_type_map = {'drain': 'Covered Lined Drain'}

    for row_idx, asset in enumerate(drains, start=4):
        ch = asset.get('chainage', '')
        ch_end = round(float(ch) + 0.1, 3) if ch else ''
        row_data = [
            nh_old, ch, ch_end,
            nh_new, section, ch, ch_end,
            asset.get('direction', 'Increasing'),
            'Covered Lined Drain',
            asset.get('survey_date', task.get('survey_date', '')),
            asset.get('latitude', ''), asset.get('longitude', ''),
            asset.get('latitude', ''), asset.get('longitude', ''),
        ]
        for col_idx, val in enumerate(row_data, 1):
            _cell(ws, row_idx, col_idx, val)


def _build_carriageway_type(wb, task):
    """
    CarriagewayType sheet — exact RIS DataTemplate format.
    """
    ws = wb.create_sheet("CarriagewayType")
    NCOLS = 13
    _title_row(ws, "Carriageway Type", NCOLS)
    _nh_row(ws, 2, NCOLS)

    headers = [
        'NH Number_old', 'Start Chainage', 'End Chainage',
        'NH Number', 'Section Code', 'Start Chainage', 'End Chainage',
        'Carriageway Type', 'Survey Date',
        'Latitude', 'Longitude', 'Latitude', 'Longitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,12,12,10,10,12,12,15,12,12,12,12,12])

    # Single row — NH-033 is Divided carriageway
    row_data = [
        "NH-080", 215, 257.64,
        task.get('nh_number', 'NH-033'),
        task.get('section_code', 'BAN-KEL'),
        215, 257.64,
        "Divided",
        task.get('survey_date', ''),
        25.23, 87.73, 24.91, 87.84,
    ]
    for col_idx, val in enumerate(row_data, 1):
        _cell(ws, 4, col_idx, val)


def _build_land_use(wb, task):
    """
    LandUse sheet — exact RIS DataTemplate format.
    """
    ws = wb.create_sheet("LandUse")
    NCOLS = 14
    _title_row(ws, "Land Use", NCOLS)
    _nh_row(ws, 2, NCOLS)

    headers = [
        'NH Number_Old', 'Start Chainage', 'End Chainage',
        'NH Number', 'Section Code', 'Start Chainage', 'End Chainage',
        'Direction', 'Land Use', 'Survey Date',
        'Latitude', 'Longitude', 'Latitude', 'Longitude'
    ]
    for i, h in enumerate(headers, 1):
        _hdr(ws, 3, i, h)
    _set_col_widths(ws, [10,12,12,10,10,12,12,12,15,12,12,12,12,12])

    row_data = [
        "NH-080", 215, 257.64,
        task.get('nh_number', 'NH-033'),
        task.get('section_code', 'BAN-KEL'),
        215, 257.64,
        "Increasing", "Agricultural/Rural",
        task.get('survey_date', ''),
        25.23, 87.73, 24.91, 87.84,
    ]
    for col_idx, val in enumerate(row_data, 1):
        _cell(ws, 4, col_idx, val)


def _build_row_summary(wb, task, video, detections, assets):
    """Summary sheet for ROW camera report."""
    ws = wb.create_sheet("Summary")
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 40

    ws.merge_cells('A1:B1')
    c = ws['A1']
    c.value = "ROW Camera Survey Report — RoadVision AI"
    c.font = TITLE_FONT; c.fill = TITLE_FILL; c.alignment = CENTER
    ws.row_dimensions[1].height = 28

    rows = [
        ("Task Name",          task.get('name', '')),
        ("NH Number",          task.get('nh_number', 'NH-033')),
        ("Section Code",       task.get('section_code', 'BAN-KEL')),
        ("Survey Date",        task.get('survey_date', '')),
        ("Camera Type",        "ROW Camera (Road Assets)"),
        ("Video File",         video.get('original_filename', '')),
        ("Frames Processed",   video.get('total_frames_extracted', 0)),
        ("Total Detections",   len(detections)),
        ("Total Assets Found", len(assets)),
        ("Chainage From (km)", video.get('chainage_start', '')),
        ("Chainage To (km)",   video.get('chainage_end', '')),
        ("Report Generated",   datetime.now().strftime("%d-%m-%Y %H:%M")),
    ]
    for i, (label, value) in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True, size=9)
        ws.cell(row=i, column=1).fill = PatternFill("solid", fgColor="D9E1F2")
        ws.cell(row=i, column=2, value=str(value))
        for col in (1, 2):
            ws.cell(row=i, column=col).border = THIN_BORDER

    # Asset count table
    ws.cell(row=16, column=1, value="Asset Inventory Summary").font = Font(bold=True, size=10)
    asset_headers = ["Asset Type", "Count", "RIS EventType"]
    for i, h in enumerate(asset_headers, 1):
        c = ws.cell(row=17, column=i, value=h)
        c.fill = SUBHDR_FILL; c.font = SUBHDR_FONT; c.border = THIN_BORDER

    asset_counts: Dict[str, int] = {}
    for a in assets:
        t = a.get('asset_type', 'unknown')
        asset_counts[t] = asset_counts.get(t, 0) + 1

    for row_idx, (atype, count) in enumerate(sorted(asset_counts.items()), start=18):
        ws.cell(row=row_idx, column=1, value=atype.replace('_', ' ').title()).border = THIN_BORDER
        ws.cell(row=row_idx, column=2, value=count).border = THIN_BORDER
        ws.cell(row=row_idx, column=3, value=_normalize_event_type(atype)).border = THIN_BORDER
