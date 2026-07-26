"""Optional LLM interviewer that fills the same AnswerSheet schema."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, Field

from quantpilot.agent.risk_profile.i18n import Lang, localize_questions, ui_text
from quantpilot.agent.risk_profile.questions import Question, load_all_questions
from quantpilot.agent.risk_profile.sheet import AnswerSheet, ChoiceAnswer
from quantpilot.ai.structured import extract_structured

LOW_CONFIDENCE = 0.55


class ExtractedChoice(BaseModel):
    """Structured mapping from free-text to a questionnaire choice."""

    question_id: str
    choice_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    needs_clarification: bool = False


def _choice_catalog(question: Question) -> str:
    lines = [f"- {c.id}: {c.label}" for c in question.choices]
    return "\n".join(lines)


def extract_choice_from_text(
    question: Question,
    user_text: str,
    *,
    model: str | None = None,
) -> ExtractedChoice:
    """Map free-text to a choice id via instructor (does not pick persona)."""
    messages = [
        {
            "role": "system",
            "content": (
                "Map the user's answer to exactly one choice_id from the catalog. "
                "Do not invent choice ids. If unclear, set needs_clarification=true "
                "and confidence below 0.55."
            ),
        },
        {
            "role": "user",
            "content": (
                f"question_id: {question.id}\n"
                f"prompt: {question.prompt}\n"
                f"choices:\n{_choice_catalog(question)}\n\n"
                f"user_answer: {user_text}\n"
            ),
        },
    ]
    result = extract_structured(ExtractedChoice, messages=messages, model=model)
    valid_ids = {c.id for c in question.choices}
    if result.choice_id not in valid_ids:
        return ExtractedChoice(
            question_id=question.id,
            choice_id=question.choices[0].id,
            confidence=0.0,
            needs_clarification=True,
        )
    if result.question_id != question.id:
        result = result.model_copy(update={"question_id": question.id})
    return result


def interview_collect_sheet(
    *,
    ask_free_text: Callable[[str], str],
    ask_select: Callable[[str, list[str]], str],
    model: str | None = None,
    on_status: Callable[[str], None] | None = None,
    lang: Lang = "en",
    questions: list[Question] | None = None,
) -> AnswerSheet:
    """Walk all questions with LLM extraction; fall back to select on low confidence.

    ``ask_free_text(prompt) -> str`` and ``ask_select(prompt, choices) -> choice_id``
    are injected so CLI (questionary) and tests can share this flow.
    """
    sheet = AnswerSheet()
    items = (
        questions
        if questions is not None
        else localize_questions(load_all_questions(), lang)
    )
    for question in items:
        if on_status:
            on_status(ui_text("asking", lang, qid=question.id))
        free = ask_free_text(question.prompt)
        try:
            extracted = extract_choice_from_text(question, free, model=model)
        except Exception:
            extracted = ExtractedChoice(
                question_id=question.id,
                choice_id=question.choices[0].id,
                confidence=0.0,
                needs_clarification=True,
            )
        if (
            extracted.needs_clarification
            or extracted.confidence < LOW_CONFIDENCE
            or extracted.choice_id not in {c.id for c in question.choices}
        ):
            labels = [f"{c.id}: {c.label}" for c in question.choices]
            selected = ask_select(
                f"{question.prompt}\n{ui_text('pick_one', lang)}",
                labels,
            )
            choice_id = str(selected).split(":", 1)[0].strip()
            sheet = sheet.with_answer(
                ChoiceAnswer(
                    question_id=question.id,
                    choice_id=choice_id,
                    confidence=1.0,
                )
            )
        else:
            sheet = sheet.with_answer(
                ChoiceAnswer(
                    question_id=extracted.question_id,
                    choice_id=extracted.choice_id,
                    confidence=extracted.confidence,
                )
            )
    return sheet
