#!/usr/bin/env python3
"""Interactive risk-profile assessment (Grable-Lytton + capacity)."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import questionary

from quantpilot.agent.risk_profile.i18n import normalize_lang, ui_text
from quantpilot.agent.risk_profile.interviewer import interview_collect_sheet
from quantpilot.agent.risk_profile.profile_io import DEFAULT_PROFILE_DIR, save_profile
from quantpilot.agent.risk_profile.questionnaire import (
    collect_answer_sheet_questionary,
    confirm_profile,
)
from quantpilot.agent.risk_profile.scoring import score_answer_sheet
from quantpilot.console import configure_stdio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Derive a trading persona from Q&A (not self-label). "
            "Willingness uses Grable & Lytton (1999); capacity is a short supplement."
        )
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help="Profile id / filename stem (default: today's date + 'profile')",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_PROFILE_DIR,
        help="Directory for saved profiles",
    )
    parser.add_argument(
        "--lang",
        choices=["ko", "en"],
        default="ko",
        help="Questionnaire UI language (default: ko)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Ollama interviewer via instructor; select fallback if unclear",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama model for --llm",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    return parser.parse_args()


def main() -> None:
    configure_stdio()
    args = parse_args()
    lang = normalize_lang(args.lang)
    profile_id = args.profile_id or f"{date.today().isoformat()}-profile"

    print(ui_text("title", lang))
    print(ui_text("intro", lang))
    print("=" * 60)

    try:
        if args.llm:

            def ask_free(prompt: str) -> str:
                text = questionary.text(prompt).ask()
                if text is None:
                    raise KeyboardInterrupt(ui_text("cancelled", lang))
                return text

            def ask_select(prompt: str, choices: list[str]) -> str:
                selected = questionary.select(prompt, choices=choices).ask()
                if selected is None:
                    raise KeyboardInterrupt(ui_text("cancelled", lang))
                return selected

            sheet = interview_collect_sheet(
                ask_free_text=ask_free,
                ask_select=ask_select,
                model=args.model,
                on_status=print,
                lang=lang,
            )
            source = "llm_interview"
        else:
            sheet = collect_answer_sheet_questionary(lang=lang)
            source = "questionnaire"
    except KeyboardInterrupt:
        print(ui_text("cancelled", lang))
        raise SystemExit(1) from None

    result = score_answer_sheet(sheet, source=source)
    for line in result.summary_lines(lang):
        print(line)
    if result.citation:
        print(ui_text("citation", lang, citation=result.citation))

    if not args.yes and not confirm_profile(result.summary_lines(lang), lang=lang):
        print(ui_text("aborted", lang))
        raise SystemExit(1)

    path = save_profile(
        result,
        args.out_dir / f"{profile_id}.json",
        profile_id=profile_id,
    )
    print(ui_text("saved", lang, path=path))
    print(ui_text("use_with", lang, path=path))


if __name__ == "__main__":
    main()
