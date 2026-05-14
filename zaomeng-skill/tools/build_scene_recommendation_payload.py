#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))

from _skill_support.scene_recommendations import build_scene_recommendation_bundle  # noqa: E402


def _write_output(payload: dict[str, object], output: str) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a host-managed dialogue scene recommendation bundle with transition and auto-continue hints."
    )
    parser.add_argument("--context-file", required=True, help="JSON context file for building a scene recommendation bundle")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    context = json.loads(Path(args.context_file).read_text(encoding="utf-8"))
    payload = build_scene_recommendation_bundle(context)
    _write_output(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
