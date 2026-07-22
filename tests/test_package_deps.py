"""Guard package dependency direction: environment must not import agent."""

from __future__ import annotations

import ast
from pathlib import Path


def test_environment_does_not_import_agent() -> None:
    root = Path(__file__).resolve().parents[1] / "quantpilot" / "environment"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("quantpilot.agent"), path
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("quantpilot.agent"), path
