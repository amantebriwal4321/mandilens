import io
import json

import cv2 as cv
import pytest
from fastapi.testclient import TestClient

from mandilens.api.app import app, store
from mandilens.synth import morning_lot, review_lot


@pytest.fixture
def client():
    store.clear()
    return TestClient(app)


def _png(image) -> bytes:
    ok, encoded = cv.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_health_reports_opencv_5(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["opencv"].startswith("5.")


def test_grade_morning_lot_and_serve_the_page(client):
    response = client.post(
        "/api/grade",
        files={"file": ("tray.png", _png(morning_lot().image), "image/png")},
        data={"marker_mm": "50"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "routed"
    assert body["destination"] == "local"
    assert len(body["fruits"]) == 6
    assert body["rectified_jpeg"]
    page = client.get("/")
    assert page.status_code == 200
    assert "MandiLens" in page.text


def test_review_changes_the_destination(client):
    response = client.post(
        "/api/grade",
        files={"file": ("tray.png", _png(review_lot().image), "image/png")},
    )
    body = response.json()
    assert body["status"] == "needs_review"
    decisions = [{"fruit_id": fruit_id, "grade": "C"} for fruit_id in body["review_ids"]]
    reviewed = client.post(f"/api/lots/{body['lot_id']}/review", json={"decisions": decisions})
    assert reviewed.status_code == 200
    assert reviewed.json()["destination"] == "local"
    assert reviewed.json()["status"] == "routed"
    again = client.post(f"/api/lots/{body['lot_id']}/review", json={"decisions": decisions})
    assert again.status_code == 400
    store.clear()
    fresh = client.post(
        "/api/grade",
        files={"file": ("tray.png", _png(review_lot().image), "image/png")},
    ).json()
    messy = client.post(
        f"/api/lots/{fresh['lot_id']}/review",
        json={"decisions": [{"fruit_id": fresh["review_ids"][0], "grade": " c "}]},
    )
    assert messy.status_code == 200
    assert messy.json()["destination"] == "local"


def test_bad_upload_is_a_400(client):
    response = client.post("/api/grade", files={"file": ("nope.txt", b"not a photo", "text/plain")})
    assert response.status_code == 400
    assert "JPEG" in response.json()["detail"] or "PNG" in response.json()["detail"]


def test_marker_downloads(client):
    png = client.get("/api/marker.png")
    assert png.status_code == 200
    assert png.content.startswith(b"\x89PNG")
    pdf = client.get("/api/marker.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_lambda_handlers_grade_without_aws(monkeypatch):
    monkeypatch.delenv("LOTS_TABLE", raising=False)
    monkeypatch.delenv("UPLOADS_BUCKET", raising=False)
    from mandilens.aws import handler

    handler._LOCAL_LOTS = None
    health = handler.health_handler({}, None)
    assert json.loads(health["body"])["status"] == "ok"
    event = {"body": json.dumps({"image_base64": _b64(morning_lot().image)})}
    graded = handler.agent_handler(event, None)
    assert graded["statusCode"] == 200
    payload = json.loads(graded["body"])
    assert payload["destination"] == "local"
    missing = handler.presign_handler({}, None)
    assert missing["statusCode"] == 500


def test_presign_uses_the_uploads_prefix(monkeypatch):
    monkeypatch.setenv("UPLOADS_BUCKET", "mandilens-uploads")

    class FakeS3:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "put_object"
            assert Params["Bucket"] == "mandilens-uploads"
            assert Params["Key"].startswith("uploads/")
            assert ExpiresIn == 300
            return "https://example.invalid/put"

    import boto3

    monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: FakeS3())
    from mandilens.aws.handler import presign_handler

    response = presign_handler({"body": json.dumps({"content_type": "image/jpeg"})}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["upload_url"].startswith("https://")


def _b64(image) -> str:
    import base64

    return base64.b64encode(_png(image)).decode("ascii")
