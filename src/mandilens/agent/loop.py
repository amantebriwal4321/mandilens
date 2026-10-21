"""The agent loop. OpenCV output chooses the next tool call."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from mandilens.agent.enhance import enhance
from mandilens.agent.policy import decide
from mandilens.agent.routing import choose_destination
from mandilens.config import CONFIDENCE_REVIEW, MARKER_MM, MAX_STEPS
from mandilens.images import jpeg_b64
from mandilens.pipeline.inspect import inspect_image
from mandilens.types import Fruit, Inspection


@dataclass
class Step:
    index: int
    tool: str
    because: str
    arguments: dict = field(default_factory=dict)
    metrics: dict | None = None

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "tool": self.tool,
            "because": self.because,
            "arguments": self.arguments,
            "metrics": self.metrics,
        }


@dataclass
class LotResult:
    lot_id: str
    status: str
    planner: str
    destination: str | None
    reason: str
    steps: list[Step]
    fruits: list[Fruit]
    inspection: Inspection | None
    marker_mm: float
    created_at: str
    note: str = ""
    review_ids: list[int] = field(default_factory=list)

    def as_dict(self, include_images: bool = True) -> dict:
        preview = None
        rectified = None
        if include_images and self.inspection is not None and self._source is not None:
            preview = jpeg_b64(self._source, max_side=900, quality=72)
            if self.inspection.rectified is not None:
                rectified = jpeg_b64(self.inspection.rectified, max_side=1100, quality=74)
        payload = {
            "lot_id": self.lot_id,
            "status": self.status,
            "planner": self.planner,
            "destination": self.destination,
            "reason": self.reason,
            "note": self.note,
            "marker_mm": self.marker_mm,
            "created_at": self.created_at,
            "review_ids": list(self.review_ids),
            "steps": [step.as_dict() for step in self.steps],
            "fruits": [fruit.as_dict() for fruit in self.fruits],
            "quality": None if self.inspection is None else self.inspection.metrics(),
            "timings_ms": {} if self.inspection is None else self.inspection.timings_ms,
        }
        if include_images:
            payload["preview_jpeg"] = preview
            payload["rectified_jpeg"] = rectified
        return payload

    _source: object | None = None


def grade_lot(image, marker_mm: float = MARKER_MM, planner: str | None = None, lot_id: str | None = None) -> LotResult:
    chosen = planner or os.environ.get("MANDILENS_PLANNER", "auto")
    use_bedrock = chosen == "bedrock" or (
        chosen == "auto" and os.environ.get("BEDROCK_ENABLED", "false").lower() == "true"
    )
    if use_bedrock:
        from mandilens.agent.bedrock import run_bedrock

        try:
            result = run_bedrock(image, marker_mm=marker_mm, lot_id=lot_id)
            result._source = image
            return result
        except Exception as exc:  # noqa: BLE001 - any AWS or network failure falls back
            result = run_policy(image, marker_mm=marker_mm, lot_id=lot_id)
            result.planner = "policy"
            result.note = f"Bedrock was unavailable ({exc.__class__.__name__}). Used the rule planner."
            result._source = image
            return result
    result = run_policy(image, marker_mm=marker_mm, lot_id=lot_id)
    result._source = image
    return result


def run_policy(image, marker_mm: float = MARKER_MM, lot_id: str | None = None) -> LotResult:
    current = image
    enhanced: str | None = None
    steps: list[Step] = []
    inspection: Inspection | None = None
    first = True
    while len(steps) < MAX_STEPS:
        inspection = inspect_image(current, marker_mm=marker_mm)
        steps.append(
            Step(
                index=len(steps) + 1,
                tool="inspect",
                because="First look at the photo." if first else f"Inspect again after {enhanced}.",
                arguments={"marker_mm": marker_mm},
                metrics=inspection.metrics(),
            )
        )
        first = False
        action = decide(inspection, enhanced)
        if action.tool == "enhance" and enhanced is None and len(steps) < MAX_STEPS:
            steps.append(
                Step(
                    index=len(steps) + 1,
                    tool="enhance",
                    because=action.because,
                    arguments={"op": action.op},
                    metrics=inspection.metrics(),
                )
            )
            current = enhance(current, action.op or "sharpen")
            enhanced = action.op
            continue
        if action.tool == "request_retake":
            steps.append(Step(index=len(steps) + 1, tool="request_retake", because=action.because, metrics=inspection.metrics()))
            return _finish(
                image, lot_id, "retake", None, action.because, steps, [], inspection, marker_mm, action.fruit_ids or []
            )
        if action.tool == "ask_human":
            steps.append(
                Step(
                    index=len(steps) + 1,
                    tool="ask_human",
                    because=action.because,
                    arguments={"fruit_ids": action.fruit_ids or []},
                    metrics=inspection.metrics(),
                )
            )
            return _finish(
                image,
                lot_id,
                "needs_review",
                None,
                action.because,
                steps,
                inspection.fruits,
                inspection,
                marker_mm,
                action.fruit_ids or [],
            )
        destination, why = choose_destination([fruit.grade for fruit in inspection.fruits])
        steps.append(
            Step(
                index=len(steps) + 1,
                tool="record_lot",
                because="The shot is trusted. Record the lot before routing it.",
                arguments={"fruit_count": len(inspection.fruits)},
                metrics=inspection.metrics(),
            )
        )
        steps.append(
            Step(
                index=len(steps) + 1,
                tool="route_lot",
                because=why,
                arguments={"destination": destination},
                metrics=inspection.metrics(),
            )
        )
        return _finish(
            image, lot_id, "routed", destination, why, steps, inspection.fruits, inspection, marker_mm, []
        )

    reason = "Stopped after 6 steps without a trusted grade. Retake the photo."
    steps.append(Step(index=len(steps) + 1, tool="request_retake", because=reason))
    return _finish(image, lot_id, "retake", None, reason, steps, [], inspection, marker_mm, [])


def _grade_updates(fruit_ids: set[int], review_ids: set[int], decisions: list[dict]) -> dict[int, str]:
    given = {int(item["fruit_id"]) for item in decisions}
    missing = review_ids - given
    if missing:
        joined = ", ".join(str(item) for item in sorted(missing))
        raise ValueError(f"Still need a decision for fruit {joined}.")
    updates: dict[int, str] = {}
    for item in decisions:
        fruit_id = int(item["fruit_id"])
        grade = str(item["grade"]).upper()
        if fruit_id not in fruit_ids:
            raise ValueError(f"Fruit {fruit_id} is not in this lot.")
        if grade not in {"A", "B", "C"}:
            raise ValueError("Grade must be A, B, or C.")
        updates[fruit_id] = grade
    return updates


def apply_review(result: LotResult, decisions: list[dict]) -> LotResult:
    if result.status != "needs_review":
        raise ValueError("This lot is not waiting for review.")
    updates = _grade_updates(
        {fruit.fruit_id for fruit in result.fruits},
        set(result.review_ids),
        decisions,
    )
    for fruit in result.fruits:
        if fruit.fruit_id in updates:
            fruit.grade = updates[fruit.fruit_id]
            fruit.confidence = 0.99
            fruit.touches_border = False
    destination, why = choose_destination([fruit.grade for fruit in result.fruits])
    result.steps.append(
        Step(
            index=len(result.steps) + 1,
            tool="human_review",
            because="A person accepted or overrode the low confidence fruit.",
            arguments={"decisions": [{"fruit_id": int(item["fruit_id"]), "grade": str(item["grade"]).upper()} for item in decisions]},
        )
    )
    result.steps.append(
        Step(
            index=len(result.steps) + 1,
            tool="route_lot",
            because=why,
            arguments={"destination": destination},
        )
    )
    result.status = "routed"
    result.destination = destination
    result.reason = why
    result.review_ids = []
    return result


def apply_review_dict(payload: dict, decisions: list[dict]) -> dict:
    """Same review step as apply_review, on the JSON lot the API stores."""

    if payload.get("status") != "needs_review":
        raise ValueError("This lot is not waiting for review.")
    fruits = payload.get("fruits") or []
    updates = _grade_updates(
        {int(fruit["fruit_id"]) for fruit in fruits},
        {int(item) for item in payload.get("review_ids") or []},
        decisions,
    )
    for fruit in fruits:
        grade = updates.get(int(fruit["fruit_id"]))
        if grade is None:
            continue
        fruit["grade"] = grade
        fruit["confidence"] = 0.99
        fruit["touches_border"] = False
        fruit["needs_review"] = False
    destination, why = choose_destination([fruit["grade"] for fruit in fruits])
    steps = list(payload.get("steps") or [])
    recorded = [
        {"fruit_id": int(item["fruit_id"]), "grade": str(item["grade"]).upper()}
        for item in decisions
    ]
    steps.append(
        {
            "index": len(steps) + 1,
            "tool": "human_review",
            "because": "A person accepted or overrode the low confidence fruit.",
            "arguments": {"decisions": recorded},
            "metrics": None,
        }
    )
    steps.append(
        {
            "index": len(steps) + 1,
            "tool": "route_lot",
            "because": why,
            "arguments": {"destination": destination},
            "metrics": None,
        }
    )
    payload["fruits"] = fruits
    payload["steps"] = steps
    payload["status"] = "routed"
    payload["destination"] = destination
    payload["reason"] = why
    payload["review_ids"] = []
    return payload


def _finish(image, lot_id, status, destination, reason, steps, fruits, inspection, marker_mm, review_ids) -> LotResult:
    import uuid

    result = LotResult(
        lot_id=lot_id or uuid.uuid4().hex[:12],
        status=status,
        planner="policy",
        destination=destination,
        reason=reason,
        steps=steps,
        fruits=fruits,
        inspection=inspection,
        marker_mm=marker_mm,
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        review_ids=list(review_ids),
    )
    result._source = image
    return result
