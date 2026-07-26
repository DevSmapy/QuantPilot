"""Deterministic scoring: G&L willingness + capacity reconcile."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from quantpilot.agent.persona import PERSONA_IDS, TradingPersona, get_persona
from quantpilot.agent.risk_profile.questions import (
    load_all_questions,
    load_capacity_questions,
    load_gl_meta,
    load_grable_lytton_questions,
)
from quantpilot.agent.risk_profile.sheet import AnswerSheet

PersonaId = Literal["conservative", "balanced", "aggressive"]

_BUCKET_RANK: dict[str, int] = {
    "conservative": 0,
    "balanced": 1,
    "aggressive": 2,
}
_RANK_BUCKET: dict[int, PersonaId] = {
    0: "conservative",
    1: "balanced",
    2: "aggressive",
}


class RiskProfileResult(BaseModel):
    """Scored risk profile mapped to a TradingPersona id."""

    persona_id: PersonaId
    willingness_score: int
    capacity_score: int
    willingness_bucket: PersonaId
    capacity_bucket: PersonaId
    flags: list[str] = Field(default_factory=list)
    answers: list[dict[str, str]] = Field(default_factory=list)
    source: str = "questionnaire"
    citation: str = ""

    def persona(self) -> TradingPersona:
        return get_persona(self.persona_id)

    def summary_lines(self) -> list[str]:
        lines = [
            f"Persona: {self.persona_id}",
            f"Willingness (Grable–Lytton): score={self.willingness_score} "
            f"→ {self.willingness_bucket}",
            f"Capacity: score={self.capacity_score} → {self.capacity_bucket}",
        ]
        if "willingness_exceeds_capacity" in self.flags:
            lines.append(
                "Note: attitude is more aggressive than capacity; "
                "the more conservative policy is applied."
            )
        return lines


def willingness_bucket_from_score(score: int) -> PersonaId:
    """Map G&L total to persona using published-style bands.

    Bands (score 13–47): ≤22 conservative, ≤28 balanced, else aggressive.
    (Combines low/below-avg → conservative; average → balanced;
    above-avg/high → aggressive.)
    """
    meta = load_gl_meta()
    for band in meta["bands"]:
        if score <= int(band["max_inclusive"]):
            persona = str(band["persona_id"])
            if persona not in PERSONA_IDS:
                raise ValueError(f"Invalid band persona_id: {persona}")
            return persona  # type: ignore[return-value]
    return "aggressive"


def capacity_bucket_from_score(score: int, *, max_score: int) -> PersonaId:
    """Map capacity points to a bucket by tertile of possible score."""
    if max_score <= 0:
        return "balanced"
    ratio = score / max_score
    if ratio <= 1 / 3:
        return "conservative"
    if ratio <= 2 / 3:
        return "balanced"
    return "aggressive"


def score_answer_sheet(
    sheet: AnswerSheet,
    *,
    source: str = "questionnaire",
) -> RiskProfileResult:
    """Score a complete answer sheet; missing required items raise ValueError."""
    gl_items = load_grable_lytton_questions()
    cap_items = load_capacity_questions()
    answers = sheet.as_map()

    willingness = 0
    for item in gl_items:
        ans = answers.get(item.id)
        if ans is None:
            raise ValueError(f"Missing answer for {item.id}")
        choice = next((c for c in item.choices if c.id == ans.choice_id), None)
        if choice is None:
            raise ValueError(f"Invalid choice {ans.choice_id!r} for {item.id}")
        willingness += choice.points

    capacity = 0
    cap_max = 0
    for item in cap_items:
        ans = answers.get(item.id)
        if ans is None:
            raise ValueError(f"Missing answer for {item.id}")
        choice = next((c for c in item.choices if c.id == ans.choice_id), None)
        if choice is None:
            raise ValueError(f"Invalid choice {ans.choice_id!r} for {item.id}")
        capacity += choice.points
        cap_max += max(c.points for c in item.choices)

    will_bucket = willingness_bucket_from_score(willingness)
    cap_bucket = capacity_bucket_from_score(capacity, max_score=cap_max)

    flags: list[str] = []
    if _BUCKET_RANK[will_bucket] > _BUCKET_RANK[cap_bucket]:
        flags.append("willingness_exceeds_capacity")
    final_rank = min(_BUCKET_RANK[will_bucket], _BUCKET_RANK[cap_bucket])
    final = _RANK_BUCKET[final_rank]

    meta = load_gl_meta()
    return RiskProfileResult(
        persona_id=final,
        willingness_score=willingness,
        capacity_score=capacity,
        willingness_bucket=will_bucket,
        capacity_bucket=cap_bucket,
        flags=flags,
        answers=[
            {"question_id": a.question_id, "choice_id": a.choice_id}
            for a in sheet.answers
        ],
        source=source,
        citation=str(meta.get("citation", "")),
    )


def assert_no_self_label_prompts() -> None:
    """Guardrail: questionnaire must not ask users to self-label a persona."""
    banned = ("aggressive", "conservative", "balanced", "risk tolerance level")
    for q in load_all_questions():
        lower = q.prompt.lower()
        if "are you an" in lower or "your risk profile" in lower:
            raise AssertionError(f"Self-label prompt forbidden: {q.id}")
        for word in banned:
            if lower.strip() in {f"i am {word}", f"are you {word}?"}:
                raise AssertionError(f"Self-label prompt forbidden: {q.id}")
