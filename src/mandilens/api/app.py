"""Local demo server. Same pipeline the Lambda handlers call."""

from __future__ import annotations

from pathlib import Path

import cv2 as cv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from mandilens import __version__
from mandilens.agent.loop import apply_review_dict, grade_lot
from mandilens.aws.store import MemoryStore
from mandilens.config import MARKER_MM, MAX_UPLOAD_BYTES
from mandilens.images import decode_image, marker_page_bgr, marker_pdf_bytes, png_bytes

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "web"
SAMPLES = ROOT / "samples"

app = FastAPI(title="MandiLens", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
store = MemoryStore()


class DecisionIn(BaseModel):
    fruit_id: int
    grade: str

    @field_validator("grade")
    @classmethod
    def one_letter(cls, value: str) -> str:
        letter = value.strip().upper()
        if letter not in {"A", "B", "C"}:
            raise ValueError("grade has to be A, B, or C")
        return letter


class ReviewIn(BaseModel):
    decisions: list[DecisionIn]


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "mandilens", "version": __version__, "opencv": cv.__version__}


@app.get("/api/samples")
def samples() -> dict:
    names = sorted(path.name for path in SAMPLES.glob("*.png")) if SAMPLES.exists() else []
    return {"samples": [{"name": name, "url": f"/samples/{name}"} for name in names]}


@app.post("/api/grade")
async def grade(file: UploadFile = File(...), marker_mm: float = Form(MARKER_MM)) -> dict:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Image is larger than 8 MB.")
    if marker_mm <= 0 or marker_mm > 500:
        raise HTTPException(status_code=400, detail="marker_mm has to be between 0 and 500.")
    try:
        image = decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = grade_lot(image, marker_mm=marker_mm)
    payload = result.as_dict()
    store.put(payload)
    return payload


@app.post("/api/lots/{lot_id}/review")
def review(lot_id: str, body: ReviewIn) -> dict:
    current = store.get(lot_id)
    if current is None:
        raise HTTPException(status_code=404, detail="No lot with that id.")
    try:
        updated = apply_review_dict(current, [item.model_dump() for item in body.decisions])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.put(updated)
    return updated


@app.get("/api/marker.png")
def marker_png() -> Response:
    return Response(content=png_bytes(marker_page_bgr()), media_type="image/png")


@app.get("/api/marker.pdf")
def marker_pdf() -> Response:
    return Response(
        content=marker_pdf_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=mandilens-marker.pdf"},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
def favicon() -> Response:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
        "<rect width='32' height='32' rx='6' fill='#c4452d'/>"
        "<text x='16' y='22' text-anchor='middle' font-size='13' "
        "font-family='sans-serif' fill='white'>ML</text></svg>"
    )
    return Response(content=svg, media_type="image/svg+xml")


if SAMPLES.exists():
    app.mount("/samples", StaticFiles(directory=SAMPLES), name="samples")
app.mount("/static", StaticFiles(directory=WEB), name="static")
