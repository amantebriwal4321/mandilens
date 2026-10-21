"""Synthetic trays with a known marker and known fruit.

The hackathon allows simulated data. These photos are how the tests and the
local demo run before anyone shoots a real tray. They are not a field trial.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2 as cv
import numpy as np

from mandilens.config import MARKER_MM
from mandilens.images import marker_square


@dataclass
class FruitSpec:
    cx: int
    cy: int
    diameter_px: int
    hue: int
    defect_fraction: float = 0.0
    cut_off: bool = False

    @property
    def diameter_mm(self) -> float:
        return self.diameter_px * MARKER_MM / 100.0

    @property
    def ripeness(self) -> str:
        if self.hue <= 12 or self.hue >= 160:
            return "red"
        if self.hue <= 32:
            return "turning"
        return "green"


@dataclass
class Scene:
    image: np.ndarray
    fruits: list[FruitSpec] = field(default_factory=list)
    marker_px: int = 100
    marker_mm: float = MARKER_MM
    has_marker: bool = True
    name: str = "scene"


def hsv_bgr(hue: int, sat: int = 210, val: int = 175) -> tuple[int, int, int]:
    pixel = np.uint8([[[hue, sat, val]]])
    bgr = cv.cvtColor(pixel, cv.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def render_scene(
    fruits: list[FruitSpec],
    seed: int = 1,
    blur: int = 0,
    exposure: float = 1.0,
    glare: bool = False,
    marker: bool = True,
    tilt: bool = False,
    tray_bgr: tuple[int, int, int] = (206, 202, 194),
    warm: bool = False,
    width: int = 960,
    height: int = 720,
    name: str = "scene",
) -> Scene:
    rng = np.random.default_rng(seed)
    image = np.full((height, width, 3), tray_bgr, np.uint8)
    image = np.clip(image.astype(np.float32) + rng.normal(0, 4, image.shape), 0, 255).astype(np.uint8)
    if marker:
        _paste_marker(image)
    for spec in fruits:
        _paint_fruit(image, spec, rng)
    if warm:
        image = _warm(image)
    if exposure != 1.0:
        image = np.clip(image.astype(np.float32) * float(exposure), 0, 255).astype(np.uint8)
    if blur:
        kernel = blur if blur % 2 == 1 else blur + 1
        image = cv.GaussianBlur(image, (kernel, kernel), 0)
    if glare:
        cv.circle(image, (430, 360), 100, (255, 255, 255), thickness=-1)
    if tilt:
        image = _tilt(image)
    return Scene(image=image, fruits=list(fruits), has_marker=marker, name=name)


def _paste_marker(image: np.ndarray) -> None:
    square = marker_square(100)
    block = np.full((150, 150), 255, np.uint8)
    block[25:125, 25:125] = square
    color = cv.cvtColor(block, cv.COLOR_GRAY2BGR)
    image[24:174, 790:940] = color


def _paint_fruit(image: np.ndarray, spec: FruitSpec, rng: np.random.Generator) -> None:
    radius = max(int(round(spec.diameter_px / 2.0)), 2)
    color = np.array(hsv_bgr(spec.hue), dtype=np.float32)
    mask = np.zeros(image.shape[:2], np.uint8)
    cv.circle(mask, (int(spec.cx), int(spec.cy)), radius, 255, thickness=-1)
    noise = rng.normal(0, 4, image.shape).astype(np.float32)
    painted = np.clip(color + noise, 0, 255)
    image[mask > 0] = painted[mask > 0]
    if spec.defect_fraction > 0:
        bruise = max(int(round(radius * np.sqrt(spec.defect_fraction))), 2)
        center = (int(spec.cx + radius * 0.15), int(spec.cy - radius * 0.05))
        cv.circle(image, center, bruise, (22, 18, 32), thickness=-1)


def _warm(image: np.ndarray) -> np.ndarray:
    shifted = image.astype(np.float32)
    shifted[:, :, 2] = np.clip(shifted[:, :, 2] * 1.22, 0, 255)
    shifted[:, :, 0] = np.clip(shifted[:, :, 0] * 0.78, 0, 255)
    return shifted.astype(np.uint8)


def _tilt(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    src = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    dst = np.float32([[36, 48], [width - 30, 18], [width - 16, height - 36], [18, height - 28]])
    matrix = cv.getPerspectiveTransform(src, dst)
    return cv.warpPerspective(image, matrix, (width, height), borderValue=(48, 46, 44))


def morning_lot() -> Scene:
    fruits = [
        FruitSpec(230, 260, 124, 4),
        FruitSpec(420, 280, 92, 55),
        FruitSpec(300, 490, 140, 16, defect_fraction=0.08),
        FruitSpec(560, 520, 72, 3),
        FruitSpec(500, 180, 96, 2),
        FruitSpec(575, 196, 96, 50),
    ]
    return render_scene(fruits, seed=7, name="morning")


def mandi_lot() -> Scene:
    fruits = [
        FruitSpec(220, 250, 130, 4),
        FruitSpec(400, 270, 124, 6),
        FruitSpec(250, 470, 136, 2),
        FruitSpec(470, 500, 128, 5),
    ]
    return render_scene(fruits, seed=8, name="mandi")


def processing_lot() -> Scene:
    fruits = [
        FruitSpec(230, 280, 64, 4, defect_fraction=0.18),
        FruitSpec(360, 300, 68, 8, defect_fraction=0.16),
        FruitSpec(500, 340, 70, 16, defect_fraction=0.02),
        FruitSpec(300, 500, 120, 4),
    ]
    return render_scene(fruits, seed=9, name="processing")


def blurry_lot() -> Scene:
    return render_scene(morning_lot().fruits, seed=7, blur=21, name="blur")


def dark_lot() -> Scene:
    return render_scene(morning_lot().fruits, seed=7, exposure=0.34, name="dark")


def glare_lot() -> Scene:
    return render_scene(morning_lot().fruits, seed=7, glare=True, name="glare")


def no_marker_lot() -> Scene:
    return render_scene(morning_lot().fruits, seed=7, marker=False, name="no-marker")


def tilted_lot() -> Scene:
    fruits = [
        FruitSpec(260, 300, 120, 4),
        FruitSpec(450, 340, 100, 55),
        FruitSpec(320, 520, 110, 16),
    ]
    return render_scene(fruits, seed=4, tilt=True, name="tilt")


def review_lot() -> Scene:
    # Three full grade-A fruit, plus one clipped fruit the pipeline should not trust.
    fruits = [
        FruitSpec(240, 280, 130, 4),
        FruitSpec(450, 300, 128, 6),
        FruitSpec(300, 520, 136, 2),
        FruitSpec(4, 400, 92, 4, cut_off=True),
    ]
    return render_scene(fruits, seed=5, name="review")


def red_tray_lot() -> Scene:
    fruits = [
        FruitSpec(260, 300, 110, 4),
        FruitSpec(460, 340, 100, 6),
    ]
    # Bright red, so this fails for color rather than exposure.
    return render_scene(fruits, seed=6, tray_bgr=(70, 70, 230), name="red-tray")


def random_tray(rng: np.random.Generator) -> Scene:
    """A frontal tray with fruit that do not touch, for the benchmark."""

    fruits: list[FruitSpec] = []
    target = int(rng.integers(4, 7))
    hues = [3, 6, 16, 18, 52, 58]
    diameters = [70, 84, 100, 116, 132, 148]
    defects = [0.0, 0.0, 0.0, 0.02, 0.08, 0.18]
    attempts = 0
    while len(fruits) < target and attempts < 500:
        attempts += 1
        diameter = int(rng.choice(diameters))
        radius = diameter / 2.0
        margin = int(radius) + 12
        if margin >= 740 or margin >= 700:
            continue
        cx = int(rng.integers(margin, 960 - margin))
        cy = int(rng.integers(margin, 720 - margin))
        if _hits_marker(cx, cy, radius):
            continue
        if any(
            np.hypot(cx - other.cx, cy - other.cy) < radius + other.diameter_px / 2.0 + 16
            for other in fruits
        ):
            continue
        fruits.append(
            FruitSpec(
                cx,
                cy,
                diameter,
                int(rng.choice(hues)),
                defect_fraction=float(rng.choice(defects)),
            )
        )
    if len(fruits) < 3:
        return morning_lot()
    return render_scene(fruits, seed=int(rng.integers(0, 1_000_000)), name="random")


def _hits_marker(cx: float, cy: float, radius: float) -> bool:
    closest_x = min(max(cx, 780), 950)
    closest_y = min(max(cy, 16), 184)
    return (cx - closest_x) ** 2 + (cy - closest_y) ** 2 < (radius + 8) ** 2


def warm_lot() -> Scene:
    fruits = [
        FruitSpec(250, 300, 120, 4),
        FruitSpec(450, 320, 100, 55),
        FruitSpec(320, 520, 110, 16),
    ]
    return render_scene(fruits, seed=11, warm=True, name="warm")
