"""Small photometric fixes. Each one is followed by another inspect."""

from __future__ import annotations

import cv2 as cv
import numpy as np


def enhance(image: np.ndarray, op: str) -> np.ndarray:
    if op == "sharpen":
        soft = cv.GaussianBlur(image, (0, 0), 2.5)
        return cv.addWeighted(image, 1.65, soft, -0.65, 0)
    if op == "gamma":
        lut = np.array([min(255, int(round(((i / 255.0) ** 0.5) * 255))) for i in range(256)], dtype=np.uint8)
        return cv.LUT(image, lut)
    if op == "clahe":
        lab = cv.cvtColor(image, cv.COLOR_BGR2LAB)
        lightness, a, b = cv.split(lab)
        clahe = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        merged = cv.merge((clahe.apply(lightness), a, b))
        return cv.cvtColor(merged, cv.COLOR_LAB2BGR)
    if op == "white_balance":
        flat = image.astype(np.float32)
        average = flat.reshape(-1, 3).mean(axis=0)
        scale = float(average.mean()) / np.clip(average, 1.0, None)
        return np.clip(flat * scale, 0, 255).astype(np.uint8)
    raise ValueError(f"Unknown enhance op: {op}")
