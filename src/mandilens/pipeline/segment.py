"""Separate fruit from a plain tray, then split fruit that touch."""

from __future__ import annotations

import cv2 as cv
import numpy as np


def chroma_mask(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Binary mask of colorful pixels against a dull tray.

    The threshold sits above the median chroma, so a warm cast on the tray
    does not paint the whole frame as fruit. Returns the mask and the Lab image.
    """

    lab = cv.cvtColor(image, cv.COLOR_BGR2LAB)
    lab_f = lab.astype(np.float32)
    chroma = np.sqrt((lab_f[:, :, 1] - 128.0) ** 2 + (lab_f[:, :, 2] - 128.0) ** 2)
    threshold = max(float(np.median(chroma)) + 14.0, 18.0)
    mask = (chroma >= threshold).astype(np.uint8) * 255
    close = cv.getStructuringElement(cv.MORPH_ELLIPSE, (7, 7))
    open_k = cv.getStructuringElement(cv.MORPH_ELLIPSE, (3, 3))
    mask = cv.morphologyEx(mask, cv.MORPH_CLOSE, close, iterations=2)
    mask = cv.morphologyEx(mask, cv.MORPH_OPEN, open_k, iterations=1)
    mask = _fill_holes(mask)
    return mask, lab


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    contours, hierarchy = cv.findContours(mask, cv.RETR_CCOMP, cv.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return mask
    filled = mask.copy()
    for index, rel in enumerate(hierarchy[0]):
        parent = rel[3]
        if parent != -1:
            cv.drawContours(filled, contours, index, 255, thickness=-1)
    return filled


def fruit_labels(image: np.ndarray, mask: np.ndarray, min_area: int) -> list[np.ndarray]:
    """One uint8 mask per fruit. Touching fruit are split with watershed."""

    count, labels, stats, _centroids = cv.connectedComponentsWithStats(mask)
    kept = np.zeros_like(mask)
    for index in range(1, count):
        if stats[index, cv.CC_STAT_AREA] >= min_area:
            kept[labels == index] = 255
    if not np.any(kept):
        return []

    dist = cv.distanceTransform(kept, cv.DIST_L2, 5)
    comp_count, comp_labels, _comp_stats, _ = cv.connectedComponentsWithStats(kept)
    pieces: list[np.ndarray] = []
    for index in range(1, comp_count):
        component = comp_labels == index
        if int(component.sum()) < min_area:
            continue
        seeds = _peaks(dist, component)
        if not seeds:
            pieces.append(component.astype(np.uint8) * 255)
            continue
        local = np.ones(mask.shape, np.int32)
        local[component] = 0
        for seed_id, (x, y) in enumerate(seeds, start=2):
            cv.circle(local, (x, y), 2, seed_id, thickness=-1)
        try:
            watershed = cv.watershed(image.copy(), local)
        except cv.error:
            pieces.append(component.astype(np.uint8) * 255)
            continue
        for seed_id in range(2, len(seeds) + 2):
            piece = np.uint8(watershed == seed_id) * 255
            if int(np.count_nonzero(piece)) >= max(400, min_area // 4):
                pieces.append(piece)
    return pieces


def _peaks(dist: np.ndarray, component: np.ndarray) -> list[tuple[int, int]]:
    local = np.where(component, dist, 0)
    maximum = float(local.max())
    if maximum < 6:
        return []
    kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (19, 19))
    dilated = cv.dilate(local, kernel)
    peaks = (local >= dilated - 1e-3) & (local >= max(8.0, 0.58 * maximum)) & component
    count, _labels, _stats, centroids = cv.connectedComponentsWithStats(peaks.astype(np.uint8))
    found: list[tuple[int, int]] = []
    for index in range(1, count):
        x = int(round(centroids[index][0]))
        y = int(round(centroids[index][1]))
        if component[y, x]:
            found.append((x, y))
    return found
