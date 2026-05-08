#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))

from _skill_support.novel_preparation import build_excerpt_payload
from _skill_support.workflow_completion import build_capability_status, default_status_path, infer_novel_id, update_run_manifest, write_json


def _stderr(message: str) -> None:
    print(str(message), file=sys.stderr)


def _excerpt_warnings(payload: dict[str, object]) -> list[str]:
    requested = [str(item).strip() for item in list(payload.get("requested_characters", [])) if str(item).strip()]
    matched = [str(item).strip() for item in list(payload.get("matched_characters", [])) if str(item).strip()]
    missing = [str(item).strip() for item in list(payload.get("missing_characters", [])) if str(item).strip()]
    strategy = str(payload.get("excerpt_strategy", "")).strip()

    warnings: list[str] = []
    if requested and not matched:
        warnings.append("未匹配到任何目标角色，excerpt 已回退为开头片段；请检查角色名写法、简繁体或异体字。")
    elif missing:
        warnings.append(f"部分目标角色未匹配到：{'、'.join(missing)}。")
    if strategy == "character_windows_mixed":
        warnings.append("目标角色命中较稀疏，excerpt 已混入时间线/对话补充句来补足上下文。")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a prompt-sized novel excerpt for prompt-first skill workflows."
    )
    parser.add_argument("--novel", required=True, help="Novel file path (.txt or .epub)")
    parser.add_argument("--characters", help="Optional comma-separated character names for character-focused excerpt selection")
    parser.add_argument("--max-sentences", type=int, default=120, help="Maximum sentence count")
    parser.add_argument("--max-chars", type=int, default=50000, help="Maximum character count")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--status-output", help="Optional status JSON output path")
    parser.add_argument("--run-manifest", help="Optional run_manifest.json path")
    parser.add_argument("--verbose", action="store_true", help="Emit diagnostic summary to stderr")
    args = parser.parse_args()

    payload = build_excerpt_payload(
        args.novel,
        characters=[item.strip() for item in str(args.characters or "").split(",") if item.strip()],
        max_sentences=max(1, int(args.max_sentences)),
        max_chars=max(200, int(args.max_chars)),
    )
    rendered = json.dumps(payload, ensure_ascii=True, indent=2)
    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.write_text(rendered + "\n", encoding="utf-8")
    status_payload = build_capability_status(
        "excerpt",
        status="complete",
        success=True,
        novel_id=infer_novel_id(args.novel),
        inputs={
            "novel": str(Path(args.novel).resolve()),
            "characters": [item.strip() for item in str(args.characters or "").split(",") if item.strip()],
            "max_sentences": max(1, int(args.max_sentences)),
            "max_chars": max(200, int(args.max_chars)),
        },
        outputs={
            "excerpt_path": str(output_path.resolve()) if output_path else "",
            "source_name": str(payload.get("source_name", "")),
            "excerpt_strategy": str(payload.get("excerpt_strategy", "")),
            "matched_characters": list(payload.get("matched_characters", [])),
            "missing_characters": list(payload.get("missing_characters", [])),
        },
        manifest_path=args.run_manifest,
        message="excerpt prepared",
    )
    status_path = default_status_path(
        "excerpt",
        output_path=output_path,
        manifest_path=args.run_manifest,
        output_dir=output_path.parent if output_path else None,
    )
    if args.status_output:
        status_path = Path(args.status_output)
    write_json(status_path, status_payload)
    if args.run_manifest:
        update_run_manifest(
            args.run_manifest,
            stage="excerpt_prepared",
            status="running",
            message="excerpt prepared",
            capability="distill",
            artifact_updates={
                "payloads": {"excerpt": str(output_path.resolve()) if output_path else ""},
                "status_files": {"excerpt": str(status_path.resolve())},
            },
        )
    for message in _excerpt_warnings(payload):
        _stderr(f"[prepare_novel_excerpt] warning: {message}")
    if args.verbose:
        _stderr(
            "[prepare_novel_excerpt] "
            f"novel={Path(args.novel).resolve()} output={output_path.resolve() if output_path else '<stdout>'} "
            f"strategy={payload.get('excerpt_strategy', '')} matched={payload.get('matched_characters', [])} "
            f"missing={payload.get('missing_characters', [])} status={status_path.resolve()}"
        )
    if not output_path:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
