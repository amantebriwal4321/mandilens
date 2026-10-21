"""Diameter, ripeness, defect area, and shape for one fruit mask."""

from __future__ import annotations

import cv2 as cv
import numpy as np


def measure_piece(
    piece: np.ndarray,
    bgr: np.ndarray,
    lab: np.ndarray,
    hsv: np.ndarray,
    mm_per_px: float,
) -> dict | None:
    area = int(np.count_nonzero(piece))
    if area < 400:
        return None
    contours, _ = cv.findContours(piece, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE)
    if not contours:
        return None
    contour = max(contours, key=cv.contourArea)
    if len(contour) < 5:
        return None
    (cx, cy), radius = cv.minEnclosingCircle(contour)
    diameter_px = float(radius * 2.0)
    hull = cv.convexHull(contour)
    hull_area = float(cv.contourArea(hull))
    solidity = float(cv.contourArea(contour)) / hull_area if hull_area > 1 else 0.0

    height, width = piece.shape[:2]
    x, y, bw, bh = cv.boundingRect(contour)
    touches_border = x <= 8 or y <= 8 or (x + bw) >= width - 8 or (y + bh) >= height - 8

    rim = max(3, int(round(diameter_px * 0.04)))
    kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (rim * 2 + 1, rim * 2 + 1))
    inner = cv.erode(piece, kernel)
    if int(np.count_nonzero(inner)) < 80:
        inner = piece

    lightness = lab[:, :, 0]
    inner_l = lightness[inner > 0]
    median_l = float(np.median(inner_l)) if inner_l.size else 0.0
    dark = (lightness < (median_l - 36)) & (piece > 0)
    defect_pct = 100.0 * float(np.count_nonzero(dark)) / float(area)

    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    color_pixels = (inner > 0) & (sat > 50) & (val > 45)
    ripeness = _ripeness(hue[color_pixels])

    return {
        "center_x": float(cx),
        "center_y": float(cy),
        "diameter_px": diameter_px,
        "diameter_mm": diameter_px * float(mm_per_px),
        "ripeness": ripeness,
        "defect_pct": float(defect_pct),
        "solidity": float(solidity),
        "touches_border": bool(touches_border),
    }


def _ripeness(hues: np.ndarray) -> str:
    if hues.size == 0:
        return "unknown"
    red_share = float(np.mean((hues <= 12) | (hues >= 160)))
    median = float(np.median(hues))
    if red_share >= 0.55:
        return "red"
    if median <= 32:
        return "turning"
    if median <= 95:
        return "green"
    return "unknown"
