#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))

from _skill_support.persona_review import (  # noqa: E402
    PERSONA_AUTOFILLABLE_FIELDS,
    PERSONA_REVIEW_FIELD_LABELS,
    build_persona_field_completion_messages,
    build_persona_field_retry_messages,
    collect_persona_web_references,
    load_persona_review_payload,
    parse_persona_field_completion_response,
)


def _write_output(payload: dict[str, object], output: str) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or parse persona field autofill payloads for host-managed LLM execution.")
    parser.add_argument("--persona-dir", default="", help="Persona directory containing PROFILE.md or PROFILE.generated.md")
    parser.add_argument("--field", default="", help="Target persona review field")
    parser.add_argument("--strategy", choices=("auto", "model_knowledge", "web_fallback"), default="auto", help="Payload strategy")
    parser.add_argument("--response-file", default="", help="Parse a model response instead of building a payload")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    parser.add_argument("--collect-web", action="store_true", help="Collect Bing result snippets for web fallback")
    args = parser.parse_args()

    if args.response_file:
        payload = {
            "kind": "persona_autofill_result",
            "parsed": parse_persona_field_completion_response(Path(args.response_file).read_text(encoding="utf-8")),
        }
        _write_output(payload, args.output)
        return 0

    if not args.persona_dir or not args.field:
        raise ValueError("build mode requires --persona-dir and --field")
    if args.field not in PERSONA_AUTOFILLABLE_FIELDS:
        raise ValueError("This field does not support AI autofill.")

    review = load_persona_review_payload(args.persona_dir)
    character = str(review.get("name", "")).strip() or Path(args.persona_dir).name
    novel_title = str(review.get("novel_title", "")).strip()
    current_fields = dict(review.get("fields", {}) or {})

    steps: list[dict[str, object]] = []
    if args.strategy in {"auto", "model_knowledge"}:
        steps.append(
            {
                "name": "model_knowledge",
                "source_mode": "model_knowledge",
                "messages": build_persona_field_completion_messages(
                    character=character,
                    field=args.field,
                    novel_title=novel_title,
                    current_fields=current_fields,
                    use_model_knowledge=True,
                ),
                "retry_messages": build_persona_field_retry_messages(
                    character=character,
                    field=args.field,
                    novel_title=novel_title,
                    current_fields=current_fields,
                    use_model_knowledge=True,
                ),
            }
        )

    if args.strategy in {"auto", "web_fallback"}:
        references = collect_persona_web_references(character=character, novel_title=novel_title) if args.collect_web else []
        steps.append(
            {
                "name": "web_fallback",
                "source_mode": "web_fallback",
                "references": references,
                "messages": build_persona_field_completion_messages(
                    character=character,
                    field=args.field,
                    novel_title=novel_title,
                    current_fields=current_fields,
                    references=references,
                    use_model_knowledge=False,
                ),
                "retry_messages": build_persona_field_retry_messages(
                    character=character,
                    field=args.field,
                    novel_title=novel_title,
                    current_fields=current_fields,
                    references=references,
                    use_model_knowledge=False,
                ),
            }
        )

    payload = {
        "kind": "persona_autofill_plan",
        "character": character,
        "field": args.field,
        "label": PERSONA_REVIEW_FIELD_LABELS.get(args.field, args.field),
        "strategy": args.strategy,
        "persona_dir": str(Path(args.persona_dir).resolve()),
        "current_fields": current_fields,
        "steps": steps,
        "host_hint": (
            "Run step[0] first. If parsed result is insufficient or format-invalid and a later step exists, "
            "continue to the next step. Use --response-file to parse the model output."
        ),
    }
    _write_output(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
