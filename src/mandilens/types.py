"""Plain data the pipeline and the agent pass around."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from mandilens.config import CONFIDENCE_REVIEW


def _num(value: float, places: int = 2) -> float:
    return round(float(value), places)


@dataclass
class Fruit:
    fruit_id: int
    center_x: float
    center_y: float
    diameter_px: float
    diameter_mm: float
    ripeness: str
    defect_pct: float
    solidity: float
    grade: str
    size_band: str
    defect_band: str
    confidence: float
    touches_border: bool

    @property
    def needs_review(self) -> bool:
        return self.confidence < CONFIDENCE_REVIEW

    def as_dict(self) -> dict:
        data = asdict(self)
        for key in ("center_x", "center_y", "diameter_px", "diameter_mm", "defect_pct", "solidity", "confidence"):
            data[key] = _num(data[key], 2)
        data["needs_review"] = self.needs_review
        return data


@dataclass
class Inspection:
    blur_score: float
    brightness: float
    glare_fraction: float
    tray_chroma: float
    marker_found: bool
    marker_id: int | None
    mm_per_px: float | None
    mask_fraction: float
    reasons: list[str]
    fruits: list[Fruit]
    rectified: np.ndarray | None
    timings_ms: dict[str, float] = field(default_factory=dict)

    @property
    def blur_ok(self) -> bool:
        from mandilens.config import BLUR_MIN

        return self.blur_score >= BLUR_MIN

    @property
    def exposure_ok(self) -> bool:
        from mandilens.config import BRIGHT_MAX, BRIGHT_MIN

        return BRIGHT_MIN <= self.brightness <= BRIGHT_MAX

    @property
    def glare_ok(self) -> bool:
        from mandilens.config import GLARE_MAX

        return self.glare_fraction <= GLARE_MAX

    @property
    def background_ok(self) -> bool:
        from mandilens.config import MASK_FRACTION_MAX, TRAY_CHROMA_MAX

        return self.mask_fraction <= MASK_FRACTION_MAX and self.tray_chroma <= TRAY_CHROMA_MAX

    @property
    def quality_ok(self) -> bool:
        return (
            self.blur_ok
            and self.exposure_ok
            and self.glare_ok
            and self.marker_found
            and self.background_ok
            and self.mm_per_px is not None
        )

    def metrics(self) -> dict:
        return {
            "blur_score": _num(self.blur_score, 1),
            "blur_ok": self.blur_ok,
            "brightness": _num(self.brightness, 1),
            "exposure_ok": self.exposure_ok,
            "glare_fraction": _num(self.glare_fraction, 4),
            "glare_ok": self.glare_ok,
            "tray_chroma": _num(self.tray_chroma, 1),
            "marker_found": self.marker_found,
            "marker_id": self.marker_id,
            "mm_per_px": None if self.mm_per_px is None else _num(self.mm_per_px, 4),
            "mask_fraction": _num(self.mask_fraction, 4),
            "background_ok": self.background_ok,
            "quality_ok": self.quality_ok,
            "fruit_count": len(self.fruits),
            "reasons": list(self.reasons),
        }
