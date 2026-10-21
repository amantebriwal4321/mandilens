"""Flatten the photo so the marker becomes a square of known size."""

from __future__ import annotations

from dataclasses import dataclass

import cv2 as cv
import numpy as np

from mandilens.config import MARKER_SKEW_MAX
from mandilens.pipeline.marker import MarkerHit


@dataclass
class Rectified:
    image: np.ndarray
    mm_per_px: float
    homography: np.ndarray
    warped: bool


def _skew(corners: np.ndarray) -> tuple[float, float]:
    sides = [float(np.linalg.norm(corners[i] - corners[(i + 1) % 4])) for i in range(4)]
    horizontal = max(sides[0], sides[2]) / max(min(sides[0], sides[2]), 1e-6)
    vertical = max(sides[1], sides[3]) / max(min(sides[1], sides[3]), 1e-6)
    return horizontal, vertical


def rectify(image: np.ndarray, hit: MarkerHit, marker_mm: float, max_side: int = 1600) -> Rectified | None:
    """Scale from the marker. Warp only when the marker is a real trapezoid.

    A homography fit to a marker that is only a pixel off square will bend the
    rest of the tray and invent diameter error. Top-down photos keep their
    pixels. Millimetres per pixel still come from the printed square.
    """

    horizontal, vertical = _skew(hit.corners)
    if horizontal < MARKER_SKEW_MAX and vertical < MARKER_SKEW_MAX:
        identity = np.eye(3, dtype=np.float64)
        return Rectified(
            image=image,
            mm_per_px=float(marker_mm) / float(hit.side_px),
            homography=identity,
            warped=False,
        )

    src = hit.corners.astype(np.float32)
    dest = max(int(round(hit.side_px)), 40)
    dst = np.float32([[0, 0], [dest, 0], [dest, dest], [0, dest]])
    homography = cv.getPerspectiveTransform(src, dst)
    if homography is None:
        return None

    height, width = image.shape[:2]
    image_corners = np.float32(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    ).reshape(-1, 1, 2)
    warped = cv.perspectiveTransform(image_corners, homography).reshape(-1, 2)
    if not np.isfinite(warped).all():
        return None
    minimum = warped.min(axis=0)
    maximum = warped.max(axis=0)
    span = maximum - minimum
    if span[0] < 80 or span[1] < 80:
        return None
    if span[0] > 8000 or span[1] > 8000:
        return None

    translate = np.array(
        [[1, 0, -minimum[0] + 2], [0, 1, -minimum[1] + 2], [0, 0, 1]],
        dtype=np.float64,
    )
    full = translate @ homography.astype(np.float64)
    out_w = int(np.ceil(span[0])) + 6
    out_h = int(np.ceil(span[1])) + 6
    scale = 1.0
    longest = max(out_w, out_h)
    if longest > max_side:
        scale = max_side / float(longest)
        shrink = np.array([[scale, 0, 0], [0, scale, 0], [0, 0, 1]], dtype=np.float64)
        full = shrink @ full
        out_w = max(1, int(round(out_w * scale)))
        out_h = max(1, int(round(out_h * scale)))

    rectified = cv.warpPerspective(
        image,
        full,
        (out_w, out_h),
        flags=cv.INTER_LINEAR,
        borderValue=(188, 186, 180),
    )
    mm_per_px = float(marker_mm) / float(dest * scale)
    return Rectified(image=rectified, mm_per_px=mm_per_px, homography=full, warped=True)
