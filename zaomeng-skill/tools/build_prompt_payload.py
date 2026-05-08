#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))

from _skill_support.prompt_payloads import build_distill_prompt_payload, build_relation_prompt_payload
from _skill_support.workflow_completion import (
    build_capability_status,
    default_status_path,
    infer_novel_id,
    update_run_manifest,
    write_json,
)


def _warning_code(message: str) -> str:
    text = str(message).strip()
    if "未匹配到任何目标角色" in text:
        return "no_character_match"
    if "部分目标角色未匹配到" in text:
        return "partial_character_match"
    if "目标角色命中较稀疏" in text:
        return "sparse_character_hits"
    if "chunk 分块" in text:
        return "chunk_fallback"
    return "general"


def _stderr(message: str) -> None:
    print(str(message), file=sys.stderr)


def _warning_messages(payload: dict[str, object]) -> list[str]:
    meta = dict(payload.get("meta", {}) or {})
    return [str(item).strip() for item in list(meta.get("warnings", [])) if str(item).strip()]


def _emit_warnings(payload: dict[str, object]) -> None:
    for message in _warning_messages(payload):
        _stderr(f"[build_prompt_payload] warning({_warning_code(message)}): {message}")


def _emit_verbose_summary(
    *,
    args: argparse.Namespace,
    payload: dict[str, object],
    output_path: Path | None,
    status_path: Path,
) -> None:
    request = dict(payload.get("request", {}) or {})
    meta = dict(payload.get("meta", {}) or {})
    excerpt_focus = dict(request.get("excerpt_focus", {}) or {})
    _stderr(
        "[build_prompt_payload] "
        f"mode={args.mode} novel={Path(args.novel).resolve()} output={output_path.resolve() if output_path else '<stdout>'}"
    )
    _stderr(
        "[build_prompt_payload] "
        f"status={status_path.resolve()} chunk_mode={request.get('chunk_mode', '')} "
        f"chunk_count={meta.get('chunk_count', 0)} merge_required={meta.get('merge_required', False)}"
    )
    _stderr(
        "[build_prompt_payload] "
        f"requested={excerpt_focus.get('requested_characters', [])} "
        f"matched={excerpt_focus.get('matched_characters', [])} "
        f"missing={excerpt_focus.get('missing_characters', [])} "
        f"strategy={excerpt_focus.get('strategy', '')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a prompt-first payload for host-side LLM execution."
    )
    parser.add_argument("--mode", choices=["distill", "relation"], required=True, help="Prompt payload mode")
    parser.add_argument("--novel", required=True, help="Novel file path (.txt or .epub)")
    parser.add_argument("--characters", help="Comma-separated characters for distill mode")
    parser.add_argument("--characters-root", help="Optional characters root or <characters>/<novel_id> directory for incremental distill context")
    parser.add_argument("--update-mode", choices=["auto", "create", "incremental"], default="auto", help="How distill payload should treat existing persona artifacts")
    parser.add_argument("--max-sentences", type=int, default=120, help="Maximum sentence count")
    parser.add_argument("--max-chars", type=int, default=50000, help="Maximum character count")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--status-output", help="Optional status JSON output path")
    parser.add_argument("--run-manifest", help="Optional run_manifest.json path")
    parser.add_argument("--verbose", action="store_true", help="Emit diagnostic summary to stderr")
    args = parser.parse_args()

    max_sentences = max(1, int(args.max_sentences))
    max_chars = max(200, int(args.max_chars))
    if args.mode == "distill":
        characters = [item.strip() for item in str(args.characters or "").split(",") if item.strip()]
        payload = build_distill_prompt_payload(
            args.novel,
            characters=characters,
            max_sentences=max_sentences,
            max_chars=max_chars,
            characters_root=args.characters_root,
            manifest_path=args.run_manifest,
            update_mode=args.update_mode,
        )
    else:
        payload = build_relation_prompt_payload(
            args.novel,
            max_sentences=max_sentences,
            max_chars=max_chars,
            characters=[item.strip() for item in str(args.characters or "").split(",") if item.strip()],
        )

    rendered = json.dumps(payload, ensure_ascii=True, indent=2)
    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.write_text(rendered + "\n", encoding="utf-8")

    capability = "distill" if args.mode == "distill" else "relation"
    status_name = capability
    status_payload = build_capability_status(
        capability,
        status="ready",
        success=True,
        novel_id=infer_novel_id(args.novel),
        inputs={
            "novel": str(Path(args.novel).resolve()),
            "characters": [item.strip() for item in str(args.characters or "").split(",") if item.strip()],
            "max_sentences": max_sentences,
            "max_chars": max_chars,
        },
        outputs={
            "payload_path": str(output_path.resolve()) if output_path else "",
            "mode": args.mode,
            "update_mode": str(payload.get("request", {}).get("update_mode", "")) if isinstance(payload.get("request", {}), dict) else "",
            "existing_character_count": int(payload.get("meta", {}).get("existing_character_count", 0)) if isinstance(payload.get("meta", {}), dict) else 0,
            "chunk_mode": str(payload.get("request", {}).get("chunk_mode", "")) if isinstance(payload.get("request", {}), dict) else "",
            "chunk_count": int(payload.get("meta", {}).get("chunk_count", 0)) if isinstance(payload.get("meta", {}), dict) else 0,
            "merge_required": bool(payload.get("meta", {}).get("merge_required", False)) if isinstance(payload.get("meta", {}), dict) else False,
            "locked_characters": list(payload.get("request", {}).get("characters", []))
            if isinstance(payload.get("request", {}), dict)
            else [],
        },
        manifest_path=args.run_manifest,
        message=f"{capability} payload ready",
    )
    status_path = default_status_path(
        status_name,
        output_path=output_path,
        manifest_path=args.run_manifest,
        output_dir=output_path.parent if output_path else None,
    )
    if args.status_output:
        status_path = Path(args.status_output)
    write_json(status_path, status_payload)

    if args.run_manifest:
        artifact_key = "distill_payload" if args.mode == "distill" else "relation_payload"
        stage = "distill_payload_ready" if args.mode == "distill" else "relation_payload_ready"
        payload_request = payload.get("request", {}) if isinstance(payload.get("request", {}), dict) else {}
        payload_meta = payload.get("meta", {}) if isinstance(payload.get("meta", {}), dict) else {}
        distill_context = {}
        if args.mode == "distill":
            distill_context = {
                "update_mode": str(payload_request.get("update_mode", "")),
                "existing_character_count": int(payload_meta.get("existing_character_count", 0)),
                "characters_root": str(payload_meta.get("characters_root", "")),
                "chunk_mode": str(payload_request.get("chunk_mode", "")),
                "chunk_count": int(payload_meta.get("chunk_count", 0)),
                "merge_required": bool(payload_meta.get("merge_required", False)),
                "existing_profile_paths": dict(payload_meta.get("existing_profile_paths", {}))
                if isinstance(payload_meta.get("existing_profile_paths", {}), dict)
                else {},
            }
        update_run_manifest(
            args.run_manifest,
            stage=stage,
            status="running",
            message=f"{capability} payload ready",
            capability="distill" if args.mode == "distill" else "",
            capability_status=status_payload if args.mode == "distill" else None,
            artifact_updates={
                "payloads": {artifact_key: str(output_path.resolve()) if output_path else ""},
                "status_files": {status_name: str(status_path.resolve())},
                "distill_context": distill_context,
                "chunking": {
                    capability: {
                        "chunk_mode": str(payload_request.get("chunk_mode", "")),
                        "chunk_count": int(payload_meta.get("chunk_count", 0)),
                        "merge_required": bool(payload_meta.get("merge_required", False)),
                    }
                },
            },
            total_characters=len(status_payload["outputs"].get("locked_characters", []))
            if args.mode == "distill"
            else None,
        )

    _emit_warnings(payload)
    if args.verbose:
        _emit_verbose_summary(
            args=args,
            payload=payload,
            output_path=output_path,
            status_path=status_path,
        )

    if not output_path:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
