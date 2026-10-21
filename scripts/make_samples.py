"""Write the tray photos the web demo can open without a camera."""

from pathlib import Path

import cv2 as cv

from mandilens.synth import blurry_lot, dark_lot, morning_lot, no_marker_lot, red_tray_lot, review_lot

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples"

SCENES = {
    "morning.png": morning_lot,
    "soft.png": blurry_lot,
    "dark.png": dark_lot,
    "marker.png": no_marker_lot,
    "cutoff.png": review_lot,
    "red-tray.png": red_tray_lot,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, builder in SCENES.items():
        scene = builder()
        ok = cv.imwrite(str(OUT / name), scene.image)
        if not ok:
            raise RuntimeError(f"Could not write {name}")
        print(name)


if __name__ == "__main__":
    main()
