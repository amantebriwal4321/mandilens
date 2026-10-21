"""Turn measurements into a house grade and a confidence."""

from __future__ import annotations

from mandilens.config import (
    CONFIDENCE_REVIEW,
    DEFECT_A_PCT,
    DEFECT_B_PCT,
    SIZE_A_MM,
    SIZE_B_MM,
    SOLIDITY_DROP,
)


def size_band(diameter_mm: float) -> str:
    if diameter_mm >= SIZE_A_MM:
        return "A"
    if diameter_mm >= SIZE_B_MM:
        return "B"
    return "C"


def defect_band(defect_pct: float) -> str:
    if defect_pct < DEFECT_A_PCT:
        return "A"
    if defect_pct < DEFECT_B_PCT:
        return "B"
    return "C"


def _worse(left: str, right: str) -> str:
    rank = {"A": 0, "B": 1, "C": 2}
    return left if rank[left] >= rank[right] else right


def _drop(grade: str) -> str:
    return {"A": "B", "B": "C", "C": "C"}[grade]


def grade_fruit(diameter_mm: float, defect_pct: float, solidity: float) -> tuple[str, str, str]:
    size = size_band(diameter_mm)
    defect = defect_band(defect_pct)
    grade = _worse(size, defect)
    if solidity < SOLIDITY_DROP:
        grade = _drop(grade)
    return grade, size, defect


def confidence(
    diameter_mm: float,
    defect_pct: float,
    solidity: float,
    ripeness: str,
    touches_border: bool,
) -> float:
    score = 0.94
    if touches_border:
        score -= 0.34
    if ripeness == "unknown":
        score -= 0.25
    if solidity < 0.86:
        score -= 0.12
    if min(abs(diameter_mm - SIZE_A_MM), abs(diameter_mm - SIZE_B_MM)) < 2.0:
        score -= 0.16
    if min(abs(defect_pct - DEFECT_A_PCT), abs(defect_pct - DEFECT_B_PCT)) < 1.0:
        score -= 0.14
    return float(max(0.15, min(0.98, score)))


def needs_review(score: float) -> bool:
    return score < CONFIDENCE_REVIEW
