"""Tests for Grable-Lytton + capacity scoring and profile I/O."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantpilot.agent.risk_profile.profile_io import load_profile, save_profile
from quantpilot.agent.risk_profile.questionnaire import collect_answer_sheet_from_maps
from quantpilot.agent.risk_profile.questions import (
    load_capacity_questions,
    load_grable_lytton_questions,
)
from quantpilot.agent.risk_profile.scoring import (
    assert_no_self_label_prompts,
    score_answer_sheet,
    willingness_bucket_from_score,
)


def _all_choice_a() -> dict[str, str]:
    answers = {q.id: "a" for q in load_grable_lytton_questions()}
    answers.update({q.id: "a" for q in load_capacity_questions()})
    return answers


def _all_max_risk() -> dict[str, str]:
    answers: dict[str, str] = {}
    for q in load_grable_lytton_questions():
        best = max(q.choices, key=lambda c: c.points)
        answers[q.id] = best.id
    for q in load_capacity_questions():
        best = max(q.choices, key=lambda c: c.points)
        answers[q.id] = best.id
    return answers


def test_gl_item_count_and_score_range() -> None:
    items = load_grable_lytton_questions()
    assert len(items) == 13
    # gl_01 choice a is high risk (4); build true minimum per item
    answers = {}
    for q in load_grable_lytton_questions():
        worst = min(q.choices, key=lambda c: c.points)
        answers[q.id] = worst.id
    for q in load_capacity_questions():
        answers[q.id] = "a"
    sheet = collect_answer_sheet_from_maps(answers)
    result = score_answer_sheet(sheet)
    assert result.willingness_score == 13
    assert result.willingness_bucket == "conservative"


def test_high_willingness_aggressive_bucket() -> None:
    sheet = collect_answer_sheet_from_maps(_all_max_risk())
    result = score_answer_sheet(sheet)
    assert result.willingness_score == 47
    assert result.willingness_bucket == "aggressive"
    assert result.persona_id == "aggressive"


def test_willingness_exceeds_capacity_flag() -> None:
    answers = _all_max_risk()
    for q in load_capacity_questions():
        answers[q.id] = "a"  # low capacity
    sheet = collect_answer_sheet_from_maps(answers)
    result = score_answer_sheet(sheet)
    assert "willingness_exceeds_capacity" in result.flags
    assert result.persona_id == "conservative"
    assert result.capacity_bucket == "conservative"


def test_band_thresholds() -> None:
    assert willingness_bucket_from_score(18) == "conservative"
    assert willingness_bucket_from_score(22) == "conservative"
    assert willingness_bucket_from_score(23) == "balanced"
    assert willingness_bucket_from_score(28) == "balanced"
    assert willingness_bucket_from_score(29) == "aggressive"


def test_no_self_label_prompts() -> None:
    assert_no_self_label_prompts()


def test_profile_roundtrip(tmp_path: Path) -> None:
    sheet = collect_answer_sheet_from_maps(_all_choice_a())
    result = score_answer_sheet(sheet)
    path = save_profile(result, tmp_path / "p.json", profile_id="p")
    loaded = load_profile(path)
    assert loaded.persona_id == result.persona_id
    assert loaded.willingness_score == result.willingness_score
    assert loaded.profile_id == "p"


def test_profile_id_rejects_traversal(tmp_path: Path) -> None:
    sheet = collect_answer_sheet_from_maps(_all_choice_a())
    result = score_answer_sheet(sheet)
    with pytest.raises(ValueError, match="Invalid profile_id"):
        save_profile(result, profile_id="../evil")
    with pytest.raises(ValueError, match="Invalid profile_id"):
        save_profile(result, profile_id="a/b")


def test_parse_selected_choice_id() -> None:
    from quantpilot.agent.risk_profile.interviewer import _parse_selected_choice_id
    from quantpilot.agent.risk_profile.questions import load_capacity_questions

    q = load_capacity_questions()[0]
    assert _parse_selected_choice_id("a: anything", q) == "a"
    assert _parse_selected_choice_id("b", q) == "b"
    with pytest.raises(ValueError, match="Unknown selection"):
        _parse_selected_choice_id("not-a-choice", q)
