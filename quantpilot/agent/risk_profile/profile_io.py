"""Persist and load scored risk profiles."""

from __future__ import annotations

import json
from pathlib import Path

from quantpilot.agent.risk_profile.scoring import RiskProfileResult

DEFAULT_PROFILE_DIR = Path("storage/profiles")


def save_profile(
    result: RiskProfileResult,
    path: Path | None = None,
    *,
    profile_id: str,
) -> Path:
    """Write profile JSON; return the path written."""
    out = path or (DEFAULT_PROFILE_DIR / f"{profile_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = result.model_dump()
    payload["profile_id"] = profile_id
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    out.write_text(text, encoding="utf-8")
    return out


def load_profile(path: Path) -> RiskProfileResult:
    """Load a previously saved RiskProfileResult (extra keys ignored)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid profile file: {path}")
    return RiskProfileResult.model_validate(data)
