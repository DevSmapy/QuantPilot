"""Persist and load scored risk profiles."""

from __future__ import annotations

import json
import re
from pathlib import Path

from quantpilot.agent.risk_profile.scoring import RiskProfileResult

DEFAULT_PROFILE_DIR = Path("storage/profiles")
_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_profile_id(profile_id: str) -> str:
    """Reject path separators, traversal, and invalid identifier characters."""
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id must be a non-empty identifier")
    if (
        "/" in profile_id
        or "\\" in profile_id
        or ".." in profile_id
        or profile_id in {".", ".."}
    ):
        raise ValueError(
            f"Invalid profile_id {profile_id!r}: path separators/traversal not allowed"
        )
    if not _PROFILE_ID_RE.fullmatch(profile_id):
        raise ValueError(
            f"Invalid profile_id {profile_id!r}: use letters, digits, . _ - only"
        )
    return profile_id


def save_profile(
    result: RiskProfileResult,
    path: Path | None = None,
    *,
    profile_id: str,
) -> Path:
    """Write profile JSON under a safe directory; return the path written."""
    safe_id = validate_profile_id(profile_id)
    target_name = f"{safe_id}.json"
    if path is None:
        base_dir = DEFAULT_PROFILE_DIR
    else:
        base_dir = path.parent
    base_resolved = base_dir.expanduser().resolve()
    out = (base_resolved / target_name).resolve()
    if out.parent != base_resolved:
        raise ValueError(f"Profile path escapes target directory: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    stored = result.model_copy(update={"profile_id": safe_id})
    text = json.dumps(stored.model_dump(), indent=2, ensure_ascii=False) + "\n"
    out.write_text(text, encoding="utf-8")
    return out


def load_profile(path: Path) -> RiskProfileResult:
    """Load a previously saved RiskProfileResult (extra keys ignored)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid profile file: {path}")
    return RiskProfileResult.model_validate(data)
