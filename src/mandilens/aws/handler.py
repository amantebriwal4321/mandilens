"""API Gateway handlers. OpenCV is imported only inside the vision paths.

Presign and health stay light so they do not need the OpenCV layer.
"""

from __future__ import annotations

import base64
import json
import os
import uuid

from mandilens import __version__
from mandilens.aws.metrics import emit
from mandilens.aws.store import lot_store
from mandilens.config import MARKER_MM, MAX_UPLOAD_BYTES

_LOCAL_LOTS = None


def _response(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _loads(event: dict) -> dict:
    body = event.get("body") or ""
    if event.get("isBase64Encoded") and body:
        body = base64.b64decode(body).decode("utf-8")
    if not body:
        return {}
    if isinstance(body, dict):
        return body
    return json.loads(body)


def _lots():
    global _LOCAL_LOTS
    table = os.environ.get("LOTS_TABLE", "").strip()
    if table:
        return lot_store()
    if _LOCAL_LOTS is None:
        from mandilens.aws.store import MemoryStore

        _LOCAL_LOTS = MemoryStore()
    return _LOCAL_LOTS


def api_handler(event, context):
    """One entry for grade and review so both routes share the OpenCV layer."""

    path = event.get("rawPath") or ""
    if path.endswith("/review"):
        return review_handler(event, context)
    return agent_handler(event, context)


def health_handler(event, context):
    return _response(200, {"status": "ok", "service": "mandilens", "version": __version__})


def presign_handler(event, context):
    bucket = os.environ.get("UPLOADS_BUCKET", "").strip()
    if not bucket:
        return _response(500, {"detail": "UPLOADS_BUCKET is not set."})
    body = _loads(event)
    content_type = body.get("content_type") or "image/jpeg"
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        return _response(400, {"detail": "content_type must be jpeg, png, or webp."})
    import boto3

    key = f"uploads/{uuid.uuid4().hex}"
    url = boto3.client("s3").generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=300,
    )
    return _response(200, {"key": key, "upload_url": url, "expires_in": 300, "content_type": content_type})


def vision_handler(event, context):
    try:
        image, marker_mm = _image_from_event(event)
    except ValueError as exc:
        return _response(400, {"detail": str(exc)})
    from mandilens.pipeline.inspect import inspect_image

    inspection = inspect_image(image, marker_mm=marker_mm)
    emit({"InspectCalls": 1, "FruitCount": len(inspection.fruits)})
    return _response(
        200,
        {
            "quality": inspection.metrics(),
            "fruits": [fruit.as_dict() for fruit in inspection.fruits],
            "timings_ms": inspection.timings_ms,
        },
    )


def agent_handler(event, context):
    try:
        image, marker_mm = _image_from_event(event)
    except ValueError as exc:
        return _response(400, {"detail": str(exc)})
    from mandilens.agent.loop import grade_lot

    result = grade_lot(image, marker_mm=marker_mm)
    payload = result.as_dict()
    _lots().put(payload)
    emit(
        {
            "AgentCalls": 1,
            "Retake": 1 if result.status == "retake" else 0,
            "HumanReview": 1 if result.status == "needs_review" else 0,
        }
    )
    return _response(200, payload)


def review_handler(event, context):
    from mandilens.agent.loop import apply_review_dict

    lot_id = (event.get("pathParameters") or {}).get("lot_id")
    if not lot_id:
        return _response(400, {"detail": "lot_id is missing."})
    current = _lots().get(lot_id)
    if current is None:
        return _response(404, {"detail": "No lot with that id."})
    body = _loads(event)
    try:
        updated = apply_review_dict(current, body.get("decisions") or [])
    except ValueError as exc:
        return _response(400, {"detail": str(exc)})
    _lots().put(updated)
    return _response(200, updated)


def _image_from_event(event: dict):
    from mandilens.images import decode_image

    body = _loads(event)
    marker_mm = float(body.get("marker_mm") or os.environ.get("MARKER_MM") or MARKER_MM)
    if body.get("image_base64"):
        raw = base64.b64decode(body["image_base64"])
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ValueError("Image is larger than 8 MB.")
        return decode_image(raw), marker_mm
    key = body.get("s3_key")
    if key:
        if not str(key).startswith("uploads/"):
            raise ValueError("s3_key must start with uploads/.")
        bucket = os.environ.get("UPLOADS_BUCKET", "").strip()
        if not bucket:
            raise ValueError("UPLOADS_BUCKET is not set.")
        import boto3

        obj = boto3.client("s3").get_object(Bucket=bucket, Key=key)
        raw = obj["Body"].read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ValueError("Image is larger than 8 MB.")
        return decode_image(raw), marker_mm
    raise ValueError("Send image_base64 or s3_key.")
