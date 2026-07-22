"""SQL helpers for DuckDB queries."""

from __future__ import annotations

from pathlib import Path


def sql_string_literal(value: str | Path) -> str:
    """Escape a value for safe inclusion in a DuckDB SQL string literal."""
    text = str(value).replace("'", "''")
    return f"'{text}'"
