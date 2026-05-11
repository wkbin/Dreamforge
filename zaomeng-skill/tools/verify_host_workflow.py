#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))

from _skill_support.workflow_completion import (
    build_capability_status,
    build_relation_completion_status,
    default_status_path,
    update_run_manifest,
    verify_host_workflow,
    write_json,
)


def _split_characters(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify whether a host-driven distillation run produced a complete artifact set."
    )
    parser.add_argument("--characters-root", required=True, help="Novel character root directory")
    parser.add_argument("--characters", help="Optional comma-separated character names")
    parser.add_argument("--relations-file", help="Optional relation markdown file to validate graph artifacts")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--status-output", help="Optional status JSON output path")
    parser.add_argument("--run-manifest", help="Optional run_manifest.json path")
    args = parser.parse_args()

    relation_status = None
    if args.relations_file:
        relation_path = Path(args.relations_file)
        base_name = relation_path.stem
        relation_status = build_relation_completion_status(
            relation_path,
            novel_id=relation_path.parent.name,
            html_path=relation_path.parent / f"{base_name}.html",
            mermaid_path=relation_path.parent / f"{base_name}.mermaid.md",
        )

    payload = verify_host_workflow(
        args.characters_root,
        characters=_split_characters(args.characters),
        relation_status=relation_status,
    )
    status_payload = build_capability_status(
        "verify_workflow",
        status=str(payload.get("status", "incomplete")),
        success=bool(payload.get("success")),
        novel_id=Path(args.characters_root).name,
        inputs={
            "characters_root": str(Path(args.characters_root).resolve()),
            "characters": _split_characters(args.characters),
            "relations_file": str(Path(args.relations_file).resolve()) if args.relations_file else "",
        },
        outputs={
            "characters_root": payload.get("characters_root", ""),
            "character_count": len(payload.get("characters", [])),
            "relation_graph_status": payload.get("relation_graph", {}).get("status", ""),
        },
        manifest_path=args.run_manifest,
        message="workflow verified",
    )
    status_path = default_status_path(
        "verify_workflow",
        output_path=args.output,
        manifest_path=args.run_manifest,
        output_dir=Path(args.characters_root),
    )
    if args.status_output:
        status_path = Path(args.status_output)
    write_json(status_path, status_payload)
    payload["status_path"] = str(status_path.resolve())
    rendered = json.dumps(payload, ensure_ascii=True, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.run_manifest:
        character_dirs = {
            item.get("character", ""): item.get("persona_dir", "")
            for item in payload.get("characters", [])
            if str(item.get("character", "")).strip() and str(item.get("persona_dir", "")).strip()
        }
        update_run_manifest(
            args.run_manifest,
            stage="workflow_verified",
            status="complete" if payload.get("success") else "running",
            message="workflow verified",
            capability="verify_workflow",
            capability_status=status_payload,
            artifact_updates={
                "character_dirs": character_dirs,
                "relation_graph": payload.get("relation_graph", {}),
                "status_files": {"verify_workflow": str(status_path.resolve())},
            },
            status_file=status_path,
        )
    return 0 if payload.get("status") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
