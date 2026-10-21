"""Optional Amazon Bedrock planner.

The rule planner is the one the tests run. This module calls Bedrock Converse
with the same tools when BEDROCK_ENABLED is true. If the call fails, the loop
falls back to the rules. Guardrails refuse a route when the last inspect did
not pass the quality gate, or while a human review is still open.
"""

from __future__ import annotations

import os

from mandilens.agent.enhance import enhance
from mandilens.agent.loop import LotResult, Step, _finish
from mandilens.agent.routing import choose_destination
from mandilens.config import MARKER_MM, MAX_STEPS
from mandilens.pipeline.inspect import inspect_image
from mandilens.types import Inspection

_SYSTEM = (
    "You grade a tray of tomatoes for MandiLens. You do not invent measurements. "
    "Call inspect first. If blur is high, call enhance with op sharpen once. "
    "If the photo is dark, call enhance with op gamma once. "
    "If the marker is missing, glare is high, or the tray is colorful, call request_retake. "
    "If any fruit has needs_review, call ask_human and stop. "
    "Otherwise call record_lot and then route_lot. Never route a photo that failed inspect."
)


def tool_config() -> dict:
    def spec(name: str, description: str, properties: dict, required: list[str]) -> dict:
        return {
            "toolSpec": {
                "name": name,
                "description": description,
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    }
                },
            }
        }

    return {
        "tools": [
            spec("inspect", "Run the OpenCV 5 pipeline and return metrics and grades.", {}, []),
            spec(
                "enhance",
                "Apply one photometric fix, then the loop will inspect again.",
                {"op": {"type": "string", "enum": ["sharpen", "gamma", "clahe", "white_balance"]}},
                ["op"],
            ),
            spec(
                "request_retake",
                "Refuse to grade and tell the person exactly what to fix.",
                {"reason": {"type": "string"}},
                ["reason"],
            ),
            spec(
                "ask_human",
                "Send low confidence fruit to a person. Do not route yet.",
                {"fruit_ids": {"type": "array", "items": {"type": "integer"}}},
                ["fruit_ids"],
            ),
            spec("record_lot", "Record a trusted lot.", {}, []),
            spec(
                "route_lot",
                "Choose mandi, local, or processing from the grades.",
                {"destination": {"type": "string", "enum": ["mandi", "local", "processing"]}},
                ["destination"],
            ),
        ]
    }


def converse(model_id: str, messages: list[dict], system: str) -> dict:
    import boto3

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    client = boto3.client("bedrock-runtime", region_name=region)
    return client.converse(
        modelId=model_id,
        system=[{"text": system}],
        messages=messages,
        toolConfig=tool_config(),
    )


def run_bedrock(image, marker_mm: float = MARKER_MM, lot_id: str | None = None) -> LotResult:
    model_id = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
    current = image
    inspection: Inspection | None = None
    enhanced: str | None = None
    steps: list[Step] = []
    pending_review = False
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Grade this tray. Marker size is "
                        f"{marker_mm:.0f} mm. Use tools. Do not guess diameters."
                    )
                }
            ],
        }
    ]
    for _ in range(MAX_STEPS):
        response = converse(model_id, messages, _SYSTEM)
        message = response["output"]["message"]
        messages.append(message)
        blocks = message.get("content") or []
        tool_uses = [block["toolUse"] for block in blocks if "toolUse" in block]
        if not tool_uses:
            break
        results = []
        terminal: LotResult | None = None
        for tool in tool_uses:
            if len(steps) >= MAX_STEPS:
                break
            payload, terminal, current, inspection, enhanced, pending_review = _execute(
                tool["name"],
                tool.get("input") or {},
                current,
                inspection,
                enhanced,
                pending_review,
                steps,
                marker_mm,
                lot_id,
                image,
            )
            results.append(
                {
                    "toolResult": {
                        "toolUseId": tool["toolUseId"],
                        "content": [{"json": payload}],
                        "status": "error" if payload.get("error") else "success",
                    }
                }
            )
            if terminal is not None:
                terminal.planner = "bedrock"
                return terminal
        messages.append({"role": "user", "content": results})
    raise RuntimeError("Bedrock did not finish the grading loop")


def _execute(name, args, current, inspection, enhanced, pending_review, steps, marker_mm, lot_id, original):
    if name == "inspect":
        inspection = inspect_image(current, marker_mm=marker_mm)
        steps.append(
            Step(
                index=len(steps) + 1,
                tool="inspect",
                because="Bedrock asked for an inspect.",
                arguments={"marker_mm": marker_mm},
                metrics=inspection.metrics(),
            )
        )
        body = inspection.metrics()
        body["fruits"] = [fruit.as_dict() for fruit in inspection.fruits]
        return body, None, current, inspection, enhanced, pending_review, 

    if name == "enhance":
        op = str(args.get("op") or "")
        if enhanced is not None:
            return {"error": "Only one enhance is allowed."}, None, current, inspection, enhanced, pending_review
        if inspection is None:
            return {"error": "Call inspect before enhance."}, None, current, inspection, enhanced, pending_review
        current = enhance(current, op)
        enhanced = op
        steps.append(Step(index=len(steps) + 1, tool="enhance", because=f"Bedrock chose {op}.", arguments={"op": op}))
        return {"op": op, "applied": True}, None, current, inspection, enhanced, pending_review

    if name == "request_retake":
        reason = str(args.get("reason") or "Retake the photo.")
        steps.append(Step(index=len(steps) + 1, tool="request_retake", because=reason))
        result = _finish(original, lot_id, "retake", None, reason, steps, [], inspection, marker_mm, [])
        return {"status": "retake"}, result, current, inspection, enhanced, pending_review

    if name == "ask_human":
        if inspection is None:
            return {"error": "Call inspect before ask_human."}, None, current, inspection, enhanced, pending_review
        fruit_ids = [int(item) for item in (args.get("fruit_ids") or [])]
        steps.append(
            Step(
                index=len(steps) + 1,
                tool="ask_human",
                because="Bedrock asked a person to check low confidence fruit.",
                arguments={"fruit_ids": fruit_ids},
            )
        )
        result = _finish(
            original,
            lot_id,
            "needs_review",
            None,
            "A person has to accept or override the flagged fruit before routing.",
            steps,
            inspection.fruits,
            inspection,
            marker_mm,
            fruit_ids,
        )
        return {"status": "needs_review", "fruit_ids": fruit_ids}, result, current, inspection, enhanced, True

    if name == "record_lot":
        if inspection is None or not inspection.quality_ok or pending_review:
            return {"error": "Refusing to record. The last inspect is not trusted, or a review is open."}, None, current, inspection, enhanced, pending_review
        steps.append(
            Step(
                index=len(steps) + 1,
                tool="record_lot",
                because="Bedrock recorded the trusted lot.",
                arguments={"fruit_count": len(inspection.fruits)},
            )
        )
        return {"recorded": True, "fruit_count": len(inspection.fruits)}, None, current, inspection, enhanced, pending_review

    if name == "route_lot":
        if inspection is None or not inspection.quality_ok or pending_review:
            return {
                "error": "Refusing to route. The last inspect failed the quality gate, or a human review is still open."
            }, None, current, inspection, enhanced, pending_review
        destination, why = choose_destination([fruit.grade for fruit in inspection.fruits])
        # The model may suggest a destination. The grades decide. That keeps routing tied to vision.
        steps.append(
            Step(
                index=len(steps) + 1,
                tool="route_lot",
                because=why,
                arguments={"destination": destination, "model_suggested": args.get("destination")},
            )
        )
        result = _finish(
            original,
            lot_id,
            "routed",
            destination,
            why,
            steps,
            inspection.fruits,
            inspection,
            marker_mm,
            [],
        )
        return {"destination": destination, "reason": why}, result, current, inspection, enhanced, pending_review

    return {"error": f"Unknown tool {name}"}, None, current, inspection, enhanced, pending_review
