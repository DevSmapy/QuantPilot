"""Load Grable–Lytton and capacity questionnaire items from package data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    points: int
    bucket: str | None = None


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    choices: tuple[Choice, ...]
    domain: str  # "willingness" | "capacity"


def _load_json(name: str) -> dict[str, Any]:
    path = _DATA_DIR / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid questionnaire data: {name}")
    return data


def load_grable_lytton_questions() -> list[Question]:
    data = _load_json("grable_lytton_items.json")
    items: list[Question] = []
    for raw in data["items"]:
        choices = tuple(
            Choice(id=c["id"], label=c["label"], points=int(c["points"]))
            for c in raw["choices"]
        )
        items.append(
            Question(
                id=str(raw["id"]),
                prompt=str(raw["prompt"]),
                choices=choices,
                domain="willingness",
            )
        )
    return items


def load_capacity_questions() -> list[Question]:
    data = _load_json("capacity_items.json")
    items: list[Question] = []
    for raw in data["items"]:
        choices = tuple(
            Choice(
                id=c["id"],
                label=c["label"],
                points=int(c["points"]),
                bucket=str(c.get("bucket")) if c.get("bucket") is not None else None,
            )
            for c in raw["choices"]
        )
        items.append(
            Question(
                id=str(raw["id"]),
                prompt=str(raw["prompt"]),
                choices=choices,
                domain="capacity",
            )
        )
    return items


def load_all_questions() -> list[Question]:
    return load_grable_lytton_questions() + load_capacity_questions()


def load_gl_meta() -> dict[str, Any]:
    return _load_json("grable_lytton_items.json")


def question_by_id(question_id: str) -> Question:
    for q in load_all_questions():
        if q.id == question_id:
            return q
    raise KeyError(question_id)
