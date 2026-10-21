from mandilens.agent.bedrock import tool_config
from mandilens.agent.loop import apply_review, grade_lot
from mandilens.config import BLUR_MIN
from mandilens.synth import blurry_lot, dark_lot, mandi_lot, morning_lot, processing_lot, review_lot


def _tools(result):
    return [step.tool for step in result.steps]


def test_blur_tries_sharpen_then_asks_for_a_retake():
    result = grade_lot(blurry_lot().image)
    assert result.status == "retake"
    assert _tools(result) == ["inspect", "enhance", "inspect", "request_retake"]
    assert result.steps[1].arguments["op"] == "sharpen"
    assert result.steps[0].metrics["blur_score"] < BLUR_MIN
    assert result.steps[2].metrics["blur_score"] < BLUR_MIN
    assert "steady" in result.reason


def test_dark_photo_is_lifted_then_routed():
    result = grade_lot(dark_lot().image)
    assert result.status == "routed"
    assert result.steps[1].arguments["op"] == "gamma"
    assert result.steps[2].metrics["brightness"] > result.steps[0].metrics["brightness"]
    assert result.destination == "local"
    assert len(result.fruits) == 6


def test_clean_lots_route_from_the_grade_mix():
    assert grade_lot(mandi_lot().image).destination == "mandi"
    assert grade_lot(processing_lot().image).destination == "processing"
    assert grade_lot(morning_lot().image).destination == "local"


def test_low_confidence_fruit_blocks_routing_until_a_person_decides():
    result = grade_lot(review_lot().image)
    assert result.status == "needs_review"
    assert result.destination is None
    assert result.review_ids
    assert "ask_human" in _tools(result)
    accepted = apply_review(
        grade_lot(review_lot().image),
        [{"fruit_id": fruit_id, "grade": "B"} for fruit_id in result.review_ids],
    )
    assert accepted.status == "routed"
    assert accepted.destination == "mandi"
    assert accepted.steps[-1].tool == "route_lot"
    overridden = apply_review(
        grade_lot(review_lot().image),
        [{"fruit_id": fruit_id, "grade": "C"} for fruit_id in result.review_ids],
    )
    assert overridden.destination == "local"
    assert overridden.destination != accepted.destination


def test_bedrock_tool_list_matches_the_loop():
    names = [tool["toolSpec"]["name"] for tool in tool_config()["tools"]]
    assert names == ["inspect", "enhance", "request_retake", "ask_human", "record_lot", "route_lot"]


def test_bedrock_failure_falls_back_to_the_rule_planner(monkeypatch):
    monkeypatch.setenv("BEDROCK_ENABLED", "true")

    def boom(*_args, **_kwargs):
        raise RuntimeError("no credentials")

    monkeypatch.setattr("mandilens.agent.bedrock.converse", boom)
    result = grade_lot(morning_lot().image)
    assert result.planner == "policy"
    assert "Bedrock" in result.note
    assert result.status == "routed"
