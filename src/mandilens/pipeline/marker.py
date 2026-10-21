"""Find the printed ArUco marker and the millimetres per pixel it implies."""

from __future__ import annotations

from dataclasses import dataclass

import cv2 as cv
import numpy as np

from mandilens.images import dictionary


@dataclass
class MarkerHit:
    marker_id: int
    corners: np.ndarray  # shape (4, 2), float32, ArUco order
    side_px: float
    box: tuple[int, int, int, int]


def detect_marker(image: np.ndarray) -> MarkerHit | None:
    detector = cv.aruco.ArucoDetector(dictionary(), cv.aruco.DetectorParameters())
    corners, ids, _rejected = detector.detectMarkers(image)
    if ids is None or len(ids) == 0:
        return None
    best: MarkerHit | None = None
    best_side = -1.0
    for index, marker_id in enumerate(ids.ravel().tolist()):
        pts = np.asarray(corners[index], dtype=np.float32).reshape(4, 2)
        side = _side_length(pts)
        if side > best_side:
            best_side = side
            x, y, w, h = cv.boundingRect(pts.astype(np.float32))
            pad = int(round(side * 0.35))
            best = MarkerHit(
                marker_id=int(marker_id),
                corners=pts,
                side_px=float(side),
                box=(x - pad, y - pad, w + pad * 2, h + pad * 2),
            )
    return best


def _side_length(corners: np.ndarray) -> float:
    lengths = [float(np.linalg.norm(corners[i] - corners[(i + 1) % 4])) for i in range(4)]
    return float(np.mean(lengths))
