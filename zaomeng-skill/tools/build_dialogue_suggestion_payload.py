#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))

from _skill_support.dialogue_payloads import (  # noqa: E402
    build_dialogue_suggestion_llm_messages,
    build_dialogue_suggestion_payload,
    compact_dialogue_suggestion_payload,
    parse_dialogue_suggestion,
)


def _write_output(payload: dict[str, object], output: str) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or parse dialogue suggestion payloads for host-managed act/insert/observe suggestion generation.")
    parser.add_argument("--context-file", default="", help="JSON context file for building a suggestion payload")
    parser.add_argument("--response-file", default="", help="Parse a model response instead of building a payload")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    if args.response_file:
        payload = {
            "kind": "dialogue_suggestion_result",
            "suggestion": parse_dialogue_suggestion(Path(args.response_file).read_text(encoding="utf-8")),
        }
        _write_output(payload, args.output)
        return 0

    if not args.context_file:
        raise ValueError("build mode requires --context-file")

    context = json.loads(Path(args.context_file).read_text(encoding="utf-8"))
    payload = build_dialogue_suggestion_payload(context)
    compact_payload = compact_dialogue_suggestion_payload(payload)
    result = {
        "kind": "dialogue_suggestion_bundle",
        "payload": payload,
        "messages": build_dialogue_suggestion_llm_messages(payload, retry_on_empty=False),
        "retry_messages": build_dialogue_suggestion_llm_messages(payload, retry_on_empty=True),
        "compact_payload": compact_payload,
        "compact_messages": build_dialogue_suggestion_llm_messages(compact_payload, retry_on_empty=False),
        "compact_retry_messages": build_dialogue_suggestion_llm_messages(compact_payload, retry_on_empty=True),
        "host_hint": (
            "Use messages first. If the host returns a context-window or bad-request style failure, "
            "retry with compact_messages. Parse the model output with --response-file."
        ),
    }
    _write_output(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
