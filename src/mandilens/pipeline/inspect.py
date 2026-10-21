"""Run the OpenCV 5 pipeline on one photo."""

from __future__ import annotations

import math
import time

import cv2 as cv
import numpy as np

from mandilens.config import MARKER_MM, MIN_DIAMETER_MM
from mandilens.pipeline.grade import confidence, grade_fruit
from mandilens.pipeline.marker import detect_marker
from mandilens.pipeline.measure import measure_piece
from mandilens.pipeline.quality import blur_score, brightness, glare_fraction, quality_reasons, tray_chroma
from mandilens.pipeline.rectify import rectify
from mandilens.pipeline.segment import chroma_mask, fruit_labels
from mandilens.types import Fruit, Inspection


def inspect_image(image: np.ndarray, marker_mm: float = MARKER_MM) -> Inspection:
    if image is None or image.size == 0:
        raise ValueError("No image to inspect.")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Inspect expects a color image.")

    timings: dict[str, float] = {}
    started = time.perf_counter()
    blur = blur_score(image)
    bright = brightness(image)
    chroma = tray_chroma(image)
    timings["quality"] = _ms(started)

    started = time.perf_counter()
    hit = detect_marker(image)
    timings["marker"] = _ms(started)
    glare = glare_fraction(image, None if hit is None else hit.box)

    rectified = None
    mm_per_px = None
    if hit is not None:
        started = time.perf_counter()
        flat = rectify(image, hit, marker_mm)
        timings["rectify"] = _ms(started)
        if flat is not None:
            rectified = flat.image
            mm_per_px = flat.mm_per_px

    fruits: list[Fruit] = []
    mask_fraction = 0.0
    view = rectified if rectified is not None else None
    if view is not None and mm_per_px is not None:
        started = time.perf_counter()
        mask, lab = chroma_mask(view)
        mask_fraction = float(np.count_nonzero(mask)) / float(mask.size)
        min_area = max(400, int(math.pi * ((MIN_DIAMETER_MM / 2.0) / mm_per_px) ** 2))
        pieces = fruit_labels(view, mask, min_area)
        hsv = cv.cvtColor(view, cv.COLOR_BGR2HSV)
        measured: list[dict] = []
        for piece in pieces:
            row = measure_piece(piece, view, lab, hsv, mm_per_px)
            if row is None:
                continue
            if row["diameter_mm"] < MIN_DIAMETER_MM:
                continue
            measured.append(row)
        timings["segment"] = _ms(started)
        fruits = _to_fruits(measured)

    reasons = quality_reasons(
        blur,
        bright,
        glare,
        hit is not None and mm_per_px is not None,
        mask_fraction,
        chroma,
    )
    return Inspection(
        blur_score=blur,
        brightness=bright,
        glare_fraction=glare,
        tray_chroma=chroma,
        marker_found=hit is not None and mm_per_px is not None,
        marker_id=None if hit is None else hit.marker_id,
        mm_per_px=mm_per_px,
        mask_fraction=mask_fraction,
        reasons=reasons,
        fruits=fruits,
        rectified=rectified,
        timings_ms=timings,
    )


def _to_fruits(rows: list[dict]) -> list[Fruit]:
    rows = sorted(rows, key=lambda row: (row["center_x"], row["center_y"]))
    fruits: list[Fruit] = []
    for index, row in enumerate(rows, start=1):
        grade, size, defect = grade_fruit(row["diameter_mm"], row["defect_pct"], row["solidity"])
        score = confidence(
            row["diameter_mm"],
            row["defect_pct"],
            row["solidity"],
            row["ripeness"],
            row["touches_border"],
        )
        fruits.append(
            Fruit(
                fruit_id=index,
                center_x=row["center_x"],
                center_y=row["center_y"],
                diameter_px=row["diameter_px"],
                diameter_mm=row["diameter_mm"],
                ripeness=row["ripeness"],
                defect_pct=row["defect_pct"],
                solidity=row["solidity"],
                grade=grade,
                size_band=size,
                defect_band=defect,
                confidence=score,
                touches_border=row["touches_border"],
            )
        )
    return fruits


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 2)
