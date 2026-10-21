"""Photo quality, measured before any grading."""

from __future__ import annotations

import cv2 as cv
import numpy as np

from mandilens.config import BLUR_MIN, BRIGHT_MAX, BRIGHT_MIN, GLARE_MAX


def blur_score(image: np.ndarray) -> float:
    """Laplacian variance after stretching contrast.

    A dark but sharp photo still scores high. A soft photo stays low.
    """

    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    low, high = np.percentile(gray, (2, 98))
    if float(high - low) < 5:
        stretched = gray
    else:
        stretched = np.clip((gray.astype(np.float32) - low) * (255.0 / float(high - low)), 0, 255)
        stretched = stretched.astype(np.uint8)
    return float(cv.Laplacian(stretched, cv.CV_64F).var())


def brightness(image: np.ndarray) -> float:
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    return float(gray.mean())


def glare_fraction(image: np.ndarray, marker_box: tuple[int, int, int, int] | None = None) -> float:
    """Share of near-white pixels outside the marker.

    The marker's own white quiet zone is not glare.
    """

    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    hot = gray >= 248
    if marker_box is not None:
        x, y, w, h = marker_box
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(gray.shape[1], x + w), min(gray.shape[0], y + h)
        hot[y0:y1, x0:x1] = False
        area = hot.size - (y1 - y0) * (x1 - x0)
    else:
        area = hot.size
    if area <= 0:
        return 0.0
    return float(np.count_nonzero(hot)) / float(area)


def tray_chroma(image: np.ndarray) -> float:
    lab = cv.cvtColor(image, cv.COLOR_BGR2LAB).astype(np.float32)
    chroma = np.sqrt((lab[:, :, 1] - 128.0) ** 2 + (lab[:, :, 2] - 128.0) ** 2)
    return float(np.median(chroma))


def quality_reasons(
    blur: float,
    bright: float,
    glare: float,
    marker_found: bool,
    mask_fraction: float,
    chroma: float,
) -> list[str]:
    from mandilens.config import MASK_FRACTION_MAX, TRAY_CHROMA_MAX

    reasons: list[str] = []
    if blur < BLUR_MIN:
        reasons.append("blur")
    if bright < BRIGHT_MIN:
        reasons.append("dark")
    elif bright > BRIGHT_MAX:
        reasons.append("bright")
    if not marker_found:
        reasons.append("marker")
    if glare > GLARE_MAX:
        reasons.append("glare")
    if mask_fraction > MASK_FRACTION_MAX or chroma > TRAY_CHROMA_MAX:
        reasons.append("background")
    return reasons
