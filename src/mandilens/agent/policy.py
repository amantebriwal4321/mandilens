"""Rule planner. Same tools a Bedrock model would call, chosen from the metrics."""

from __future__ import annotations

from dataclasses import dataclass

from mandilens.config import (
    BLUR_MIN,
    BRIGHT_MAX,
    BRIGHT_MIN,
    CONFIDENCE_REVIEW,
    GLARE_MAX,
)
from mandilens.types import Inspection


@dataclass
class Action:
    tool: str
    because: str
    op: str | None = None
    fruit_ids: list[int] | None = None


def decide(inspection: Inspection, enhanced: str | None) -> Action:
    if inspection.blur_score < BLUR_MIN:
        shown = f"{inspection.blur_score:.0f}"
        if enhanced is None:
            return Action(
                "enhance",
                f"Blur score is {shown}, under {BLUR_MIN:.0f}. Sharpen once and inspect again.",
                op="sharpen",
            )
        return Action(
            "request_retake",
            f"Blur score is still {shown} after {enhanced}. Hold the phone steady and retake.",
        )

    if inspection.brightness < BRIGHT_MIN:
        shown = f"{inspection.brightness:.0f}"
        if enhanced is None:
            return Action(
                "enhance",
                f"Mean brightness is {shown}, under {BRIGHT_MIN:.0f}. Lift gamma and inspect again.",
                op="gamma",
            )
        return Action(
            "request_retake",
            f"Mean brightness is still {shown} after {enhanced}. Add light and retake.",
        )

    if inspection.brightness > BRIGHT_MAX:
        return Action(
            "request_retake",
            f"Mean brightness is {inspection.brightness:.0f}. Move off the overhead light and retake.",
        )

    if not inspection.marker_found:
        return Action(
            "request_retake",
            "The 50 mm marker is not fully in frame. Lay it flat beside the fruit and retake.",
        )

    if inspection.glare_fraction > GLARE_MAX:
        pct = inspection.glare_fraction * 100.0
        return Action(
            "request_retake",
            f"Glare covers {pct:.1f}% of the tray. Tilt the phone so the lamp is not in the lens.",
        )

    if not inspection.background_ok:
        return Action(
            "request_retake",
            "The tray is as colorful as the fruit. Use a plain light tray and retake.",
        )

    if not inspection.fruits:
        return Action(
            "request_retake",
            "The marker is in frame but I cannot see fruit. Fill the tray and retake.",
        )

    low = [fruit.fruit_id for fruit in inspection.fruits if fruit.confidence < CONFIDENCE_REVIEW]
    if low:
        joined = ", ".join(str(item) for item in low)
        return Action(
            "ask_human",
            f"Fruit {joined} is low confidence. A person has to accept or override before routing.",
            fruit_ids=low,
        )

    return Action(
        "route",
        "Quality gate passed and every fruit is confident enough to grade.",
    )
