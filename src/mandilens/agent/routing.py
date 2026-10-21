"""Where a trusted lot goes."""

from __future__ import annotations

from mandilens.config import ROUTE_A_SHARE, ROUTE_C_SHARE


def choose_destination(grades: list[str]) -> tuple[str, str]:
    count = len(grades)
    if count == 0:
        return "processing", "No fruit was graded, so this lot does not go to the mandi."
    grade_c = grades.count("C")
    grade_a = grades.count("A")
    grade_b = grades.count("B")
    if grade_c / count >= ROUTE_C_SHARE:
        return (
            "processing",
            f"{grade_c} of {count} fruit are grade C. Send the lot to a processing unit.",
        )
    if grade_c == 0 and grade_a / count >= ROUTE_A_SHARE:
        return (
            "mandi",
            f"{grade_a} of {count} fruit are grade A and none are grade C. This lot can go to the mandi.",
        )
    return (
        "local",
        f"Mixed lot: {grade_a} A, {grade_b} B, {grade_c} C. Local retail fits better than the wholesale mandi.",
    )
