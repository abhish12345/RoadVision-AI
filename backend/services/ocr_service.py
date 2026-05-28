"""
OCR Service — reads the video overlay border:
Speed | Latitude | Longitude | Chainage | Date | Description
"""
import re
import cv2
import numpy as np
from typing import Dict, Any, Optional
import easyocr

_reader = None

def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader


def extract_overlay_data(frame: np.ndarray) -> Dict[str, Any]:
    """
    Extract telemetry data from the video overlay/border.
    The overlay is typically at the top or bottom strip of the frame.
    Returns dict with: speed, latitude, longitude, chainage, date, description
    """
    h, w = frame.shape[:2]

    # Try top strip (first 15% of height) and bottom strip (last 15%)
    top_strip = frame[0:int(h * 0.15), :]
    bottom_strip = frame[int(h * 0.85):, :]

    result = {}

    for strip_name, strip in [("top", top_strip), ("bottom", bottom_strip)]:
        text_data = _run_ocr(strip)
        parsed = _parse_overlay_text(text_data)
        if parsed:
            result.update(parsed)
            if len(result) >= 3:  # got enough data
                break

    return result


def _run_ocr(strip: np.ndarray) -> str:
    """Run EasyOCR on a strip and return concatenated text."""
    try:
        reader = get_reader()
        # Upscale strip for better OCR
        scale = 3
        strip_up = cv2.resize(strip, (strip.shape[1] * scale, strip.shape[0] * scale))
        # Convert to grayscale + enhance contrast
        gray = cv2.cvtColor(strip_up, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        results = reader.readtext(gray, detail=0, paragraph=False)
        return " ".join(results)
    except Exception as e:
        return ""


def _parse_overlay_text(text: str) -> Dict[str, Any]:
    """Parse overlay text to extract telemetry fields."""
    result = {}
    text_upper = text.upper()

    # Speed: e.g. "Speed: 25 km/h" or "SPD 25" or just "25 KM/H"
    speed_match = re.search(r'(?:SPEED|SPD)[:\s]*(\d+(?:\.\d+)?)', text_upper)
    if not speed_match:
        speed_match = re.search(r'(\d+(?:\.\d+)?)\s*KM[/\s]?H', text_upper)
    if speed_match:
        try:
            result['speed'] = float(speed_match.group(1))
        except:
            pass

    # Latitude: e.g. "Lat: 25.2316" or "25.2316N"
    lat_match = re.search(r'(?:LAT|LATITUDE)[:\s]*([+-]?\d{1,3}\.\d+)', text_upper)
    if not lat_match:
        lat_match = re.search(r'([2][0-9]\.\d{4,})', text)  # India lat range 8-37
    if lat_match:
        try:
            result['latitude'] = float(lat_match.group(1))
        except:
            pass

    # Longitude: e.g. "Lon: 87.7292" or "87.7292E"
    lon_match = re.search(r'(?:LON|LONG|LONGITUDE)[:\s]*([+-]?\d{1,3}\.\d+)', text_upper)
    if not lon_match:
        lon_match = re.search(r'([7-9][0-9]\.\d{4,})', text)  # India lon range 68-97
    if lon_match:
        try:
            result['longitude'] = float(lon_match.group(1))
        except:
            pass

    # Chainage: e.g. "Ch: 215.010" or "Chainage: 215.010" or "215+010"
    ch_match = re.search(r'(?:CH|CHAIN|CHAINAGE)[:\s]*(\d+(?:[.+]\d+)?)', text_upper)
    if not ch_match:
        ch_match = re.search(r'(\d{3}[.+]\d{3})', text)  # pattern like 215.010
    if ch_match:
        try:
            ch_str = ch_match.group(1).replace('+', '.')
            result['chainage'] = float(ch_str)
        except:
            pass

    # Date: e.g. "14-02-2026" or "2026-02-14"
    date_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4}|\d{4}[-/]\d{2}[-/]\d{2})', text)
    if date_match:
        result['survey_date'] = date_match.group(1)

    # Description / Road name
    desc_match = re.search(r'(?:DESC|DESCRIPTION|ROAD)[:\s]*([A-Z0-9\s\-]+)', text_upper)
    if desc_match:
        result['description'] = desc_match.group(1).strip()

    return result


def estimate_chainage_from_gps(lat: float, lon: float,
                                 start_lat: float, start_lon: float,
                                 start_chainage: float) -> float:
    """
    Estimate chainage from GPS coordinates using Haversine distance.
    """
    import math
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(start_lat)
    phi2 = math.radians(lat)
    dphi = math.radians(lat - start_lat)
    dlambda = math.radians(lon - start_lon)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    dist_m = 2 * R * math.asin(math.sqrt(a))
    return start_chainage + dist_m / 1000  # convert to km
