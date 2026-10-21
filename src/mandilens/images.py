"""Image decode, encode, and the printable marker."""

from __future__ import annotations

import base64

import cv2 as cv
import numpy as np

from mandilens.config import MARKER_ID, MARKER_MM, MAX_SIDE_PX


def dictionary():
    return cv.aruco.getPredefinedDictionary(cv.aruco.DICT_4X4_50)


def marker_square(side_px: int, marker_id: int = MARKER_ID) -> np.ndarray:
    side_px = int(max(side_px, 20))
    return cv.aruco.generateImageMarker(dictionary(), marker_id, side_px)


def decode_image(raw: bytes, max_side: int = MAX_SIDE_PX) -> np.ndarray:
    if not raw:
        raise ValueError("The upload is empty.")
    arr = np.frombuffer(raw, dtype=np.uint8)
    image = cv.imdecode(arr, cv.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not read that file. Use a JPEG or a PNG.")
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest > max_side:
        scale = max_side / float(longest)
        image = cv.resize(
            image,
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            interpolation=cv.INTER_AREA,
        )
    return image


def jpeg_bytes(image: np.ndarray, max_side: int = 960, quality: int = 74) -> bytes:
    view = image
    height, width = view.shape[:2]
    longest = max(height, width)
    if longest > max_side:
        scale = max_side / float(longest)
        view = cv.resize(
            view,
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            interpolation=cv.INTER_AREA,
        )
    ok, buf = cv.imencode(".jpg", view, [int(cv.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("Could not encode a JPEG preview.")
    return buf.tobytes()


def jpeg_b64(image: np.ndarray, max_side: int = 960, quality: int = 74) -> str:
    return base64.b64encode(jpeg_bytes(image, max_side=max_side, quality=quality)).decode("ascii")


def marker_page_bgr() -> np.ndarray:
    """A page with a 50 mm marker at 300 dpi, plus a caption.

    The black square is 591 pixels, which is 50 mm at 300 dpi.
    """

    black = 591
    quiet = 148  # about 12.5 mm of white around the square
    side = black + quiet * 2
    page_w = side + 160
    page_h = side + 280
    page = np.full((page_h, page_w, 3), 255, np.uint8)
    square = marker_square(black)
    x0 = (page_w - side) // 2
    y0 = 120
    tile = cv.cvtColor(square, cv.COLOR_GRAY2BGR)
    page[y0 + quiet : y0 + quiet + black, x0 + quiet : x0 + quiet + black] = tile
    cv.rectangle(page, (x0 + quiet, y0 + quiet), (x0 + quiet + black - 1, y0 + quiet + black - 1), (0, 0, 0), 1)
    _put_center(page, "MandiLens marker", 56, 1.1, 2)
    _put_center(page, "Print at 100 percent. The black square is 50 mm wide.", page_h - 150, 0.7, 1)
    _put_center(page, "Dict 4x4, id 0. Lay it flat on the tray, fully in frame.", page_h - 100, 0.6, 1)
    return page


def _put_center(image: np.ndarray, text: str, y: int, scale: float, thickness: int) -> None:
    font = cv.FONT_HERSHEY_SIMPLEX
    (tw, _), _ = cv.getTextSize(text, font, scale, thickness)
    x = max(10, (image.shape[1] - tw) // 2)
    cv.putText(image, text, (x, y), font, scale, (20, 20, 20), thickness, cv.LINE_AA)


def png_bytes(image: np.ndarray) -> bytes:
    ok, buf = cv.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not encode a PNG.")
    return _set_png_dpi(buf.tobytes(), 300)


def _set_png_dpi(png: bytes, dpi: int) -> bytes:
    """Write a pHYs chunk so a print dialog can honour 300 dpi."""

    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        return png
    ppm = int(round(dpi / 0.0254))
    data = ppm.to_bytes(4, "big") + ppm.to_bytes(4, "big") + b"\x01"
    chunk_type = b"pHYs"
    crc = _crc(chunk_type + data)
    chunk = len(data).to_bytes(4, "big") + chunk_type + data + crc.to_bytes(4, "big")
    # Insert before the first IDAT.
    marker = png.find(b"IDAT")
    if marker < 4:
        return png
    start = marker - 4
    return png[:start] + chunk + png[start:]


def _crc(payload: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF


def jpeg_pdf(jpeg: bytes, img_w: int, img_h: int) -> bytes:
    """One-page PDF that embeds the JPEG at its pixel size mapped from 300 dpi.

    A PDF point is 1/72 inch. At 300 dpi, one pixel is 72/300 points, so the
    black square keeps its 50 mm physical size when printed at 100 percent.
    """

    points_per_px = 72.0 / 300.0
    page_w = img_w * points_per_px
    page_h = img_h * points_per_px
    content = f"q {page_w:.2f} 0 0 {page_h:.2f} 0 0 cm /Im1 Do Q".encode("ascii")
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>")
    objects.append(
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w:.2f} {page_h:.2f}] "
        f"/Contents 4 0 R /Resources << /XObject << /Im1 5 0 R >> >> >>".encode("ascii")
    )
    objects.append(b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream")
    image_obj = (
        f"<< /Type /XObject /Subtype /Image /Width {img_w} /Height {img_h} "
        f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
        f"/Length {len(jpeg)} >>\nstream\n".encode("ascii")
        + jpeg
        + b"\nendstream"
    )
    objects.append(image_obj)

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    )
    return bytes(out)


def marker_pdf_bytes() -> bytes:
    page = marker_page_bgr()
    jpeg = jpeg_bytes(page, max_side=4000, quality=92)
    return jpeg_pdf(jpeg, page.shape[1], page.shape[0])


def marker_mm_default() -> float:
    return MARKER_MM
