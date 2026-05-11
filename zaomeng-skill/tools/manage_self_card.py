#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))

from _skill_support.persona_review import (  # noqa: E402
    SELF_CARD_FIELD_LABELS,
    SELF_CARD_FIELDS,
    SELF_CARD_REQUIRED_FIELDS,
    blank_self_card_fields,
    build_random_self_card_messages,
    delete_self_card_payload,
    list_self_cards_payload,
    load_self_card_payload,
    parse_random_self_card_response,
    save_self_card_payload,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_output(payload: dict[str, object], output: str) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


def _load_fields_from_args(args: argparse.Namespace) -> dict[str, object]:
    if args.fields_file:
        return json.loads(Path(args.fields_file).read_text(encoding="utf-8"))
    if args.response_file:
        return parse_random_self_card_response(Path(args.response_file).read_text(encoding="utf-8"))
    raise ValueError("save mode requires --fields-file or --response-file")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage self-insert cards for host-driven insert dialogue.")
    parser.add_argument(
        "--mode",
        choices=("blank", "list", "get", "save", "delete", "build-random-payload", "parse-random-response"),
        required=True,
        help="Operation mode",
    )
    parser.add_argument("--cards-root", default="data/self_cards", help="Self card root directory")
    parser.add_argument("--card-id", default="", help="Card id for get/save/delete")
    parser.add_argument("--fields-file", default="", help="JSON file containing self card fields for save mode")
    parser.add_argument("--response-file", default="", help="LLM response text file for parse-random-response or save mode")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    cards_root = Path(args.cards_root)
    if args.mode == "blank":
        payload = {
            "kind": "self_card_schema",
            "fields": blank_self_card_fields(),
            "field_order": list(SELF_CARD_FIELDS),
            "required_fields": list(SELF_CARD_REQUIRED_FIELDS),
            "field_labels": dict(SELF_CARD_FIELD_LABELS),
        }
    elif args.mode == "list":
        payload = {"kind": "self_card_list", "items": list_self_cards_payload(cards_root)}
    elif args.mode == "get":
        payload = {"kind": "self_card", **load_self_card_payload(cards_root, args.card_id)}
    elif args.mode == "save":
        fields = _load_fields_from_args(args)
        payload = {"kind": "self_card", **save_self_card_payload(cards_root, card_id=args.card_id, fields=fields, utc_now=_utc_now)}
    elif args.mode == "delete":
        payload = {"kind": "self_card_delete", **delete_self_card_payload(cards_root, args.card_id)}
    elif args.mode == "build-random-payload":
        payload = {
            "kind": "self_card_random_payload",
            "mode": "random_self_card",
            "messages": build_random_self_card_messages(),
            "expected_fields": list(SELF_CARD_FIELDS),
            "required_fields": list(SELF_CARD_REQUIRED_FIELDS),
            "field_labels": dict(SELF_CARD_FIELD_LABELS),
            "host_hint": "Call the host LLM with messages, then pass the raw response into --mode parse-random-response or --mode save --response-file.",
        }
    else:
        if not args.response_file:
            raise ValueError("parse-random-response mode requires --response-file")
        fields = parse_random_self_card_response(Path(args.response_file).read_text(encoding="utf-8"))
        payload = {
            "kind": "self_card_random_result",
            "fields": fields,
            "preview": {
                "display_name": fields["display_name"],
                "scene_identity": fields["scene_identity"],
                "core_identity": fields["core_identity"],
                "story_role": fields["story_role"],
                "temperament_type": fields["temperament_type"],
                "speech_style": fields["speech_style"],
                "soul_goal": fields["soul_goal"],
            },
        }

    _write_output(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
