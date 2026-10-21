from mandilens.pipeline.grade import confidence, defect_band, grade_fruit, size_band


def test_size_and_defect_bands():
    assert size_band(60) == "A"
    assert size_band(55) == "A"
    assert size_band(40) == "B"
    assert size_band(39) == "C"
    assert defect_band(1) == "A"
    assert defect_band(4) == "B"
    assert defect_band(12) == "C"


def test_worst_band_wins_and_shape_can_drop_a_grade():
    grade, size, defect = grade_fruit(70, 1, 0.97)
    assert (grade, size, defect) == ("A", "A", "A")
    grade, _, _ = grade_fruit(70, 9, 0.97)
    assert grade == "B"
    grade, _, _ = grade_fruit(70, 1, 0.70)
    assert grade == "B"


def test_border_fruit_is_low_confidence():
    score = confidence(60, 0, 0.98, "red", touches_border=True)
    assert score < 0.70
    sure = confidence(60, 0, 0.98, "red", touches_border=False)
    assert sure > 0.90
