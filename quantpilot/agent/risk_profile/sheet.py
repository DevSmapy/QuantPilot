"""Answer sheet schemas for risk-profile elicitation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChoiceAnswer(BaseModel):
    """One selected choice for a questionnaire item."""

    question_id: str
    choice_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AnswerSheet(BaseModel):
    """Collected answers for willingness + capacity items."""

    answers: list[ChoiceAnswer] = Field(default_factory=list)

    def as_map(self) -> dict[str, ChoiceAnswer]:
        return {a.question_id: a for a in self.answers}

    def with_answer(self, answer: ChoiceAnswer) -> AnswerSheet:
        mapping = self.as_map()
        mapping[answer.question_id] = answer
        return AnswerSheet(answers=list(mapping.values()))
