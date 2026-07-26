"""Tests for risk-profile questionnaire localization."""

from __future__ import annotations

import pytest

from quantpilot.agent.risk_profile.i18n import (
    localize_questions,
    normalize_lang,
    ui_text,
)
from quantpilot.agent.risk_profile.questionnaire import collect_answer_sheet_from_maps
from quantpilot.agent.risk_profile.questions import load_all_questions
from quantpilot.agent.risk_profile.scoring import score_answer_sheet


def test_normalize_lang() -> None:
    assert normalize_lang("ko") == "ko"
    assert normalize_lang("KO-KR") == "ko"
    assert normalize_lang("en") == "en"
    with pytest.raises(ValueError):
        normalize_lang("ja")


def test_korean_overlay_covers_all_items() -> None:
    en = load_all_questions()
    ko = localize_questions(en, "ko")
    assert len(ko) == len(en)
    for eng, kor in zip(en, ko, strict=True):
        assert eng.id == kor.id
        assert eng.domain == kor.domain
        assert len(eng.choices) == len(kor.choices)
        for ec, kc in zip(eng.choices, kor.choices, strict=True):
            assert ec.id == kc.id
            assert ec.points == kc.points
            assert kc.label  # non-empty
        # Korean prompts should differ from English for G&L/capacity items
        assert kor.prompt != eng.prompt or kor.id.startswith("unused")


def test_korean_ui_and_summary() -> None:
    assert "성향" in ui_text("title", "ko")
    answers = {q.id: q.choices[0].id for q in load_all_questions()}
    result = score_answer_sheet(collect_answer_sheet_from_maps(answers))
    lines = result.summary_lines("ko")
    assert any("페르소나" in line for line in lines)


def test_scoring_unchanged_by_locale_labels() -> None:
    en = load_all_questions()
    ko = localize_questions(en, "ko")
    answers = {q.id: max(q.choices, key=lambda c: c.points).id for q in en}
    r_en = score_answer_sheet(collect_answer_sheet_from_maps(answers, questions=en))
    r_ko = score_answer_sheet(collect_answer_sheet_from_maps(answers, questions=ko))
    assert r_en.willingness_score == r_ko.willingness_score
    assert r_en.persona_id == r_ko.persona_id
