"""Locale overlays for risk-profile questionnaire UI (scoring stays on choice ids)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from quantpilot.agent.risk_profile.questions import Choice, Question

Lang = Literal["en", "ko"]
SUPPORTED_LANGS: tuple[Lang, ...] = ("en", "ko")

_DATA_DIR = Path(__file__).resolve().parent / "data"

_UI_EN: dict[str, str] = {
    "title": "QuantPilot risk profile assessment",
    "intro": (
        "Willingness: Grable & Lytton (1999). "
        "You will not be asked to self-label as conservative/aggressive."
    ),
    "confirm": "Use this policy for simulations?",
    "confirm_title": "Derived policy:",
    "aborted": "Aborted; profile not saved.",
    "saved": "Saved profile → {path}",
    "use_with": "Use with: --profile {path}",
    "citation": "Citation: {citation}",
    "asking": "Asking {qid}…",
    "pick_one": "(Please pick one)",
    "cancelled": "Cancelled",
    "streamlit_expander": "Risk profile assessment (Q&A)",
    "streamlit_caption": (
        "Willingness uses Grable & Lytton (1999). "
        "No self-label questions (you are not asked if you are aggressive)."
    ),
    "streamlit_score_btn": "Score & save profile",
    "streamlit_saved": "Saved {path}",
    "lang_label": "Language",
    "persona": "Persona: {persona}",
    "willingness": ("Willingness (Grable–Lytton): score={score} → {bucket}"),
    "capacity": "Capacity: score={score} → {bucket}",
    "flag_exceeds": (
        "Note: attitude is more aggressive than capacity; "
        "the more conservative policy is applied."
    ),
}


def normalize_lang(lang: str | None) -> Lang:
    """Return a supported language code; unknown values fall back to English."""
    if lang is None:
        return "en"
    key = lang.strip().lower().replace("_", "-")
    if key in ("ko", "ko-kr", "korean", "kr"):
        return "ko"
    if key in ("en", "en-us", "en-gb", "english"):
        return "en"
    raise ValueError(
        f"Unsupported language {lang!r}; expected one of {SUPPORTED_LANGS}"
    )


def _load_ko_pack() -> dict[str, Any]:
    path = _DATA_DIR / "locale_ko.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid locale_ko.json")
    return data


def ui_text(key: str, lang: Lang = "en", **kwargs: object) -> str:
    """Return a UI chrome string for the locale."""
    if lang == "ko":
        pack = _load_ko_pack()
        template = str(pack.get("ui", {}).get(key, _UI_EN.get(key, key)))
    else:
        template = _UI_EN.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template


def localize_questions(questions: list[Question], lang: Lang = "en") -> list[Question]:
    """Overlay translated prompts/labels; keep ids/points/buckets unchanged."""
    if lang == "en":
        return list(questions)

    pack = _load_ko_pack()
    qmap: dict[str, Any] = pack.get("questions", {})
    localized: list[Question] = []
    for q in questions:
        entry = qmap.get(q.id)
        if not isinstance(entry, dict):
            localized.append(q)
            continue
        choice_labels = entry.get("choices", {})
        if not isinstance(choice_labels, dict):
            choice_labels = {}
        choices = tuple(
            Choice(
                id=c.id,
                label=str(choice_labels.get(c.id, c.label)),
                points=c.points,
                bucket=c.bucket,
            )
            for c in q.choices
        )
        localized.append(
            Question(
                id=q.id,
                prompt=str(entry.get("prompt", q.prompt)),
                choices=choices,
                domain=q.domain,
            )
        )
    return localized
