import cv2 as cv

from mandilens.pipeline.inspect import inspect_image
from mandilens.pipeline.marker import detect_marker
from mandilens.pipeline.rectify import rectify
from mandilens.synth import (
    blurry_lot,
    dark_lot,
    glare_lot,
    morning_lot,
    no_marker_lot,
    red_tray_lot,
    tilted_lot,
    warm_lot,
)


def test_opencv_major_is_5():
    assert cv.__version__.startswith("5.")


def test_morning_lot_diameters_ripeness_and_bruise():
    scene = morning_lot()
    inspection = inspect_image(scene.image)
    assert inspection.marker_found
    assert inspection.quality_ok
    assert len(inspection.fruits) == len(scene.fruits)
    got = sorted(fruit.diameter_mm for fruit in inspection.fruits)
    expected = sorted(spec.diameter_mm for spec in scene.fruits)
    for measured, truth in zip(got, expected):
        assert abs(measured - truth) <= 3.0
    assert sorted(fruit.ripeness for fruit in inspection.fruits) == sorted(spec.ripeness for spec in scene.fruits)
    bruised = max(inspection.fruits, key=lambda fruit: fruit.diameter_mm)
    assert bruised.defect_pct >= 4
    assert bruised.grade == "B"
    assert any(fruit.grade == "C" for fruit in inspection.fruits)
    assert any(fruit.grade == "A" for fruit in inspection.fruits)


def test_top_down_marker_is_not_warped():
    scene = morning_lot()
    hit = detect_marker(scene.image)
    flat = rectify(scene.image, hit, 50)
    assert flat is not None
    assert flat.warped is False
    assert abs(flat.mm_per_px - (50 / hit.side_px)) < 1e-6


def test_mild_tilt_keeps_diameter():
    scene = tilted_lot()
    inspection = inspect_image(scene.image)
    assert inspection.marker_found
    assert len(inspection.fruits) == len(scene.fruits)
    got = sorted(fruit.diameter_mm for fruit in inspection.fruits)
    expected = sorted(spec.diameter_mm for spec in scene.fruits)
    for measured, truth in zip(got, expected):
        assert abs(measured - truth) <= 4.0


def test_quality_gate_names_the_failure():
    assert "blur" in inspect_image(blurry_lot().image).reasons
    assert "dark" in inspect_image(dark_lot().image).reasons
    assert "glare" in inspect_image(glare_lot().image).reasons
    assert "marker" in inspect_image(no_marker_lot().image).reasons
    red = inspect_image(red_tray_lot().image)
    assert "background" in red.reasons
    assert red.fruits == []


def test_warm_cast_still_finds_fruit():
    inspection = inspect_image(warm_lot().image)
    assert inspection.quality_ok
    assert len(inspection.fruits) == 3
