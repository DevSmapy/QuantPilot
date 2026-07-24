"""Strategy protocol for signal generation."""

from __future__ import annotations

from typing import Protocol

import polars as pl


class Strategy(Protocol):
    """Generate discrete trade-event signals from OHLCV prices.

    Implementations return a DataFrame with at least ``date`` and ``signal``
    where ``signal`` is one of ``{-1, 0, 1}``:

    * ``1`` — enter long (flat → long)
    * ``-1`` — exit long (long → flat)
    * ``0`` — hold
    """

    def run(self, prices: pl.DataFrame) -> pl.DataFrame:
        """Produce signal events aligned to price dates."""
        ...
