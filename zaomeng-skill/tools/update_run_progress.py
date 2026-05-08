#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))

from _skill_support.workflow_completion import STANDARD_PROGRESS_STAGES, update_run_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append a standardized host progress event into run_manifest.json."
    )
    parser.add_argument("--run-manifest", required=True, help="run_manifest.json path")
    parser.add_argument("--stage", required=True, choices=list(STANDARD_PROGRESS_STAGES), help="Standard progress stage")
    parser.add_argument("--status", default="running", choices=["running", "complete", "failed"], help="Stage status")
    parser.add_argument("--message", default="", help="Optional user-facing progress message")
    parser.add_argument("--character", default="", help="Current character for character_started/completed")
    parser.add_argument("--total", type=int, help="Optional total character count override")
    parser.add_argument("--graph-status", default="", choices=["", "pending", "running", "complete"], help="Optional graph status override")
    parser.add_argument("--chunk-capability", default="", help="Optional chunk progress capability, e.g. distill or relation")
    parser.add_argument("--chunk-mode", default="", choices=["", "single", "chunked", "partial"], help="Optional chunk mode")
    parser.add_argument("--chunk-count", type=int, help="Optional total chunk count")
    parser.add_argument("--current-chunk", type=int, help="Optional current chunk index")
    parser.add_argument("--chunk-label", default="", help="Optional current chunk label")
    parser.add_argument("--chunk-status", default="", choices=["", "pending", "running", "complete"], help="Optional chunk progress status")
    parser.add_argument("--merge-required", action="store_true", help="Whether merge is required after chunk execution")
    parser.add_argument("--merge-status", default="", choices=["", "pending", "running", "complete"], help="Optional merge status")
    args = parser.parse_args()

    chunk_progress = None
    if args.chunk_capability:
        chunk_progress = {
            "capability": args.chunk_capability,
            "mode": args.chunk_mode,
            "chunk_count": args.chunk_count,
            "current_chunk": args.current_chunk,
            "current_label": args.chunk_label,
            "status": args.chunk_status or args.status,
            "merge_required": bool(args.merge_required),
            "merge_status": args.merge_status,
        }

    payload = update_run_manifest(
        args.run_manifest,
        stage=args.stage,
        status=args.status,
        message=args.message,
        character=args.character,
        total_characters=args.total,
        graph_status=args.graph_status,
        chunk_progress=chunk_progress,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
