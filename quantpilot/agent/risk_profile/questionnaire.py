"""questionary-based fixed questionnaire (no self-label prompts)."""

from __future__ import annotations

from collections.abc import Callable

import questionary

from quantpilot.agent.risk_profile.questions import Question, load_all_questions
from quantpilot.agent.risk_profile.sheet import AnswerSheet, ChoiceAnswer


def collect_answer_sheet_questionary(
    *,
    questions: list[Question] | None = None,
) -> AnswerSheet:
    """Run the full fixed questionnaire via questionary select prompts."""
    items = questions if questions is not None else load_all_questions()
    sheet = AnswerSheet()
    for item in items:
        choice_map = {f"{c.id}: {c.label}": c.id for c in item.choices}
        selected = questionary.select(
            item.prompt,
            choices=list(choice_map.keys()),
        ).ask()
        if selected is None:
            raise KeyboardInterrupt("Questionnaire cancelled")
        sheet = sheet.with_answer(
            ChoiceAnswer(question_id=item.id, choice_id=choice_map[selected])
        )
    return sheet


def collect_answer_sheet_from_maps(
    answers: dict[str, str],
    *,
    questions: list[Question] | None = None,
) -> AnswerSheet:
    """Build a sheet from question_id → choice_id (for tests / Streamlit)."""
    items = questions if questions is not None else load_all_questions()
    sheet = AnswerSheet()
    for item in items:
        if item.id not in answers:
            raise ValueError(f"Missing answer for {item.id}")
        choice_id = answers[item.id]
        if choice_id not in {c.id for c in item.choices}:
            raise ValueError(f"Invalid choice {choice_id!r} for {item.id}")
        sheet = sheet.with_answer(
            ChoiceAnswer(question_id=item.id, choice_id=choice_id)
        )
    return sheet


def confirm_profile(
    summary_lines: list[str],
    ask_confirm: Callable[[str], bool] | None = None,
) -> bool:
    """Ask the user to confirm applying the derived policy."""
    text = "Derived policy:\n" + "\n".join(f"  {line}" for line in summary_lines)
    print(text)
    if ask_confirm is not None:
        return ask_confirm("Use this policy for simulations?")
    return bool(
        questionary.confirm(
            "Use this policy for simulations?",
            default=True,
        ).ask()
    )
