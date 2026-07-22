"""Trading-day simulation clock."""

from __future__ import annotations

from datetime import date


class SimulationClock:
    """Advance through a fixed list of session dates."""

    def __init__(self, session_dates: list[date]) -> None:
        if not session_dates:
            raise ValueError("session_dates must not be empty")
        self._dates = list(session_dates)
        self._idx = 0

    @property
    def as_of(self) -> date:
        return self._dates[self._idx]

    @property
    def session_index(self) -> int:
        return self._idx

    @property
    def session_count(self) -> int:
        return len(self._dates)

    @property
    def remaining_sessions(self) -> int:
        return len(self._dates) - self._idx - 1

    def is_last_day(self) -> bool:
        return self._idx >= len(self._dates) - 1

    def is_decision_day(self, every_n: int) -> bool:
        if every_n < 1:
            raise ValueError("every_n must be >= 1")
        return self._idx % every_n == 0

    def advance(self) -> bool:
        """Move to the next session. Return False if already on the last day."""
        if self.is_last_day():
            return False
        self._idx += 1
        return True
