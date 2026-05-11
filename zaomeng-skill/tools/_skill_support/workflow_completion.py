#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REQUIRED_PERSONA_FILES = (
    "PROFILE.generated.md",
    "SOUL.generated.md",
    "IDENTITY.generated.md",
    "BACKGROUND.generated.md",
    "CAPABILITY.generated.md",
    "BONDS.generated.md",
    "CONFLICTS.generated.md",
    "ROLE.generated.md",
    "AGENTS.generated.md",
    "MEMORY.generated.md",
    "NAVIGATION.generated.md",
)

STANDARD_PROGRESS_STAGES = (
    "characters_locked",
    "distill_payload_ready",
    "relation_payload_ready",
    "chunk_started",
    "chunk_completed",
    "merge_started",
    "merge_completed",
    "character_started",
    "character_completed",
    "graph_export_started",
    "graph_export_completed",
    "workflow_verified",
)


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def infer_novel_id(novel_path: str | Path, explicit: str = "") -> str:
    if str(explicit or "").strip():
        return str(explicit).strip()
    return Path(novel_path).stem.strip()


def build_capability_status(
    capability: str,
    *,
    status: str,
    success: bool,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    novel_id: str = "",
    character: str = "",
    manifest_path: str | Path | None = None,
    message: str = "",
) -> dict[str, Any]:
    return {
        "kind": "host_capability_status",
        "capability": capability,
        "novel_id": novel_id,
        "character": character,
        "status": status,
        "success": bool(success),
        "message": message,
        "inputs": dict(inputs or {}),
        "outputs": dict(outputs or {}),
        "manifest_path": str(Path(manifest_path).resolve()) if manifest_path else "",
        "updated_at": utc_now(),
    }


def default_status_path(
    capability: str,
    *,
    output_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    character: str = "",
) -> Path:
    if output_path:
        base = Path(output_path)
        suffix = "".join(base.suffixes)
        if suffix:
            return base.with_name(base.name[: -len(suffix)] + ".status.json")
        return base.with_name(base.name + ".status.json")
    if output_dir:
        stem = f"{character}_{capability}" if character else capability
        return Path(output_dir) / f"{stem}.status.json"
    if manifest_path:
        return Path(manifest_path).resolve().parent / f"{capability}.status.json"
    return Path.cwd() / f"{capability}.status.json"


def initialize_run_manifest(
    manifest_path: str | Path,
    *,
    novel_path: str | Path,
    characters: list[str] | None = None,
    novel_id: str = "",
) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    locked_characters = [str(item).strip() for item in list(characters or []) if str(item).strip()]
    resolved_novel_id = infer_novel_id(novel_path, explicit=novel_id)
    payload = {
        "kind": "zaomeng_host_run",
        "schema_version": 1,
        "run_id": manifest_file.stem,
        "novel_id": resolved_novel_id,
        "novel_path": str(Path(novel_path).resolve()),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "running",
        "success": False,
        "locked_characters": locked_characters,
        "progress": {
            "stage": "characters_locked",
            "message": "locked characters",
            "current_character": "",
            "completed_characters": [],
            "total_characters": len(locked_characters),
            "completed_count": 0,
            "graph_status": "pending",
            "chunking": {},
        },
        "capabilities": {
            "distill": {},
            "materialize": {},
            "export_graph": {},
            "verify_workflow": {},
        },
        "artifacts": {
            "payloads": {},
            "status_files": {},
            "character_dirs": {},
            "relation_graph": {},
        },
        "summary": {
            "characters_total": len(locked_characters),
            "characters_completed": 0,
            "graph_status": "pending",
            "status_text": "waiting_for_distill",
        },
        "events": [],
    }
    _append_event(payload, stage="characters_locked", status="running", message="locked characters")
    write_json(manifest_file, payload)
    return payload


def update_run_manifest(
    manifest_path: str | Path,
    *,
    stage: str,
    status: str = "running",
    message: str = "",
    character: str = "",
    capability: str = "",
    capability_status: dict[str, Any] | None = None,
    artifact_updates: dict[str, Any] | None = None,
    status_file: str | Path | None = None,
    total_characters: int | None = None,
    graph_status: str = "",
    chunk_progress: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    payload = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}
    payload.setdefault("kind", "zaomeng_host_run")
    payload.setdefault("schema_version", 1)
    payload.setdefault("locked_characters", [])
    payload.setdefault("capabilities", {})
    payload.setdefault("artifacts", {})
    payload.setdefault("summary", {})
    payload.setdefault("events", [])
    progress = payload.setdefault("progress", {})
    progress["stage"] = stage
    progress["message"] = message or progress.get("message", "")
    if total_characters is not None:
        progress["total_characters"] = int(total_characters)
    elif "total_characters" not in progress:
        progress["total_characters"] = len(payload.get("locked_characters", []))
    progress.setdefault("completed_characters", [])
    progress.setdefault("completed_count", len(progress["completed_characters"]))
    progress.setdefault("graph_status", "pending")
    progress.setdefault("chunking", {})

    if character:
        if stage == "character_started":
            progress["current_character"] = character
        elif stage == "character_completed":
            progress["current_character"] = ""
            if character not in progress["completed_characters"]:
                progress["completed_characters"].append(character)
        else:
            progress["current_character"] = character

    if graph_status:
        progress["graph_status"] = graph_status
    elif stage == "graph_export_started":
        progress["graph_status"] = "running"
    elif stage == "graph_export_completed":
        progress["graph_status"] = "complete"

    progress["completed_count"] = len(progress["completed_characters"])

    if capability:
        payload["capabilities"].setdefault(capability, {})
        if capability_status:
            payload["capabilities"][capability] = dict(capability_status)
        else:
            payload["capabilities"][capability].update({"status": status, "updated_at": utc_now()})
        if status_file:
            payload["artifacts"].setdefault("status_files", {})[capability] = str(Path(status_file).resolve())

    if artifact_updates:
        _deep_merge(payload["artifacts"], artifact_updates)

    if chunk_progress:
        _update_chunk_progress(progress, chunk_progress)

    _sync_chunking_overview_from_artifacts(payload)

    if extra:
        payload.update(dict(extra))

    payload["updated_at"] = utc_now()
    _refresh_summary(payload, status=status)
    _append_event(
        payload,
        stage=stage,
        status=status,
        message=message,
        character=character,
        capability=capability,
    )
    write_json(manifest_file, payload)
    return payload


def sync_manifest_character_dir(manifest_path: str | Path, *, character: str, persona_dir: str | Path) -> dict[str, Any]:
    return update_run_manifest(
        manifest_path,
        stage="character_completed",
        status="running",
        message=f"{character} materialized",
        character=character,
        capability="materialize",
        artifact_updates={"character_dirs": {character: str(Path(persona_dir).resolve())}},
    )


def build_persona_completion_status(persona_dir: str | Path, *, name: str = "", novel_id: str = "") -> dict[str, Any]:
    root = Path(persona_dir)
    present_files = sorted(path.name for path in root.iterdir() if path.is_file()) if root.exists() else []
    missing_required = [filename for filename in REQUIRED_PERSONA_FILES if not (root / filename).exists()]
    return {
        "kind": "persona_bundle",
        "capability": "materialize",
        "character": name or root.name,
        "novel_id": novel_id,
        "persona_dir": str(root.resolve()) if root.exists() else str(root),
        "status": "complete" if not missing_required else "incomplete",
        "success": not missing_required,
        "required_files": list(REQUIRED_PERSONA_FILES),
        "missing_required_files": missing_required,
        "present_files": present_files,
    }


def build_relation_completion_status(
    relations_file: str | Path,
    *,
    novel_id: str,
    html_path: str | Path,
    mermaid_path: str | Path,
) -> dict[str, Any]:
    relation_path = Path(relations_file)
    html_file = Path(html_path)
    mermaid_file = Path(mermaid_path)
    required = [str(mermaid_file.name), str(html_file.name)]
    missing = []
    if not mermaid_file.exists():
        missing.append(mermaid_file.name)
    if not html_file.exists():
        missing.append(html_file.name)
    return {
        "kind": "relation_graph",
        "capability": "export_graph",
        "novel_id": novel_id,
        "relations_file": str(relation_path.resolve()) if relation_path.exists() else str(relation_path),
        "status": "complete" if not missing else "incomplete",
        "success": not missing,
        "required_files": required,
        "missing_required_files": missing,
        "html_path": str(html_file.resolve()) if html_file.exists() else str(html_file),
        "mermaid_path": str(mermaid_file.resolve()) if mermaid_file.exists() else str(mermaid_file),
    }


def verify_host_workflow(
    characters_root: str | Path,
    *,
    characters: list[str] | None = None,
    relation_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(characters_root)
    if characters:
        names = list(characters)
    elif root.exists():
        names = sorted(path.name for path in root.iterdir() if path.is_dir())
    else:
        names = []

    persona_statuses = [
        build_persona_completion_status(root / name, name=name, novel_id=root.name if root.exists() else "")
        for name in names
    ]
    missing_characters = [name for name in names if not (root / name).exists()]
    ok = not missing_characters and all(item["status"] == "complete" for item in persona_statuses)
    if relation_status is not None:
        ok = ok and relation_status.get("status") == "complete"

    return {
        "kind": "host_workflow",
        "capability": "verify_workflow",
        "characters_root": str(root.resolve()) if root.exists() else str(root),
        "status": "complete" if ok else "incomplete",
        "success": ok,
        "characters": persona_statuses,
        "missing_character_dirs": missing_characters,
        "relation_graph": relation_status or {},
    }


def _refresh_summary(payload: dict[str, Any], *, status: str) -> None:
    progress = payload.setdefault("progress", {})
    completed = list(progress.get("completed_characters", []))
    total = int(progress.get("total_characters", len(payload.get("locked_characters", []))))
    graph_status = str(progress.get("graph_status", "pending"))
    verify = payload.get("capabilities", {}).get("verify_workflow", {})
    verified_complete = verify.get("status") == "complete" and bool(verify.get("success"))

    summary = payload.setdefault("summary", {})
    summary["characters_total"] = total
    summary["characters_completed"] = len(completed)
    summary["graph_status"] = graph_status
    summary["chunking"] = _summarize_chunking(progress.get("chunking", {}))
    if verified_complete:
        payload["status"] = "complete"
        payload["success"] = True
        summary["status_text"] = "workflow_complete"
    elif status == "failed":
        payload["status"] = "failed"
        payload["success"] = False
        summary["status_text"] = "workflow_failed"
    else:
        payload["status"] = "running"
        payload["success"] = False
        if graph_status == "complete" and len(completed) >= total > 0:
            summary["status_text"] = "waiting_for_verification"
        elif graph_status == "running":
            summary["status_text"] = "graph_export_running"
        elif progress.get("current_character"):
            summary["status_text"] = "character_in_progress"
        elif payload.get("capabilities", {}).get("distill", {}).get("status") in {"ready", "complete"}:
            summary["status_text"] = "waiting_for_host_generation"
        else:
            summary["status_text"] = "waiting_for_distill"


def _update_chunk_progress(progress: dict[str, Any], chunk_progress: dict[str, Any]) -> None:
    capability = str(chunk_progress.get("capability", "")).strip()
    if not capability:
        return
    bucket = progress.setdefault("chunking", {})
    current = dict(bucket.get(capability, {}))
    current.update(
        {
            "capability": capability,
            "mode": str(chunk_progress.get("mode", current.get("mode", ""))).strip(),
            "chunk_count": int(chunk_progress.get("chunk_count", current.get("chunk_count", 0)) or 0),
            "current_chunk": int(chunk_progress.get("current_chunk", current.get("current_chunk", 0)) or 0),
            "current_label": str(chunk_progress.get("current_label", current.get("current_label", ""))).strip(),
            "status": str(chunk_progress.get("status", current.get("status", "pending"))).strip() or "pending",
            "merge_required": bool(chunk_progress.get("merge_required", current.get("merge_required", False))),
            "merge_status": str(chunk_progress.get("merge_status", current.get("merge_status", "pending"))).strip()
            or "pending",
            "updated_at": utc_now(),
        }
    )
    bucket[capability] = current


def _sync_chunking_overview_from_artifacts(payload: dict[str, Any]) -> None:
    artifacts = payload.setdefault("artifacts", {})
    chunking = artifacts.get("chunking", {})
    if not isinstance(chunking, dict):
        return
    progress = payload.setdefault("progress", {})
    progress.setdefault("chunking", {})
    for capability, item in chunking.items():
        if not isinstance(item, dict):
            continue
        existing = dict(progress["chunking"].get(capability, {}))
        progress["chunking"][capability] = {
            "capability": capability,
            "mode": str(existing.get("mode", item.get("chunk_mode", ""))).strip(),
            "chunk_count": int(existing.get("chunk_count", item.get("chunk_count", 0)) or 0),
            "current_chunk": int(existing.get("current_chunk", 0) or 0),
            "current_label": str(existing.get("current_label", "")).strip(),
            "status": str(existing.get("status", "pending")).strip() or "pending",
            "merge_required": bool(existing.get("merge_required", item.get("merge_required", False))),
            "merge_status": str(existing.get("merge_status", "pending")).strip() or "pending",
            "updated_at": existing.get("updated_at", utc_now()),
        }


def _summarize_chunking(chunking: Any) -> dict[str, Any]:
    if not isinstance(chunking, dict):
        return {}
    summary: dict[str, Any] = {}
    for capability, item in chunking.items():
        if not isinstance(item, dict):
            continue
        summary[capability] = {
            "mode": str(item.get("mode", "")).strip(),
            "chunk_count": int(item.get("chunk_count", 0) or 0),
            "current_chunk": int(item.get("current_chunk", 0) or 0),
            "status": str(item.get("status", "pending")).strip() or "pending",
            "merge_required": bool(item.get("merge_required", False)),
            "merge_status": str(item.get("merge_status", "pending")).strip() or "pending",
        }
    return summary


def _append_event(
    payload: dict[str, Any],
    *,
    stage: str,
    status: str,
    message: str = "",
    character: str = "",
    capability: str = "",
) -> None:
    payload.setdefault("events", []).append(
        {
            "stage": stage,
            "status": status,
            "message": message,
            "character": character,
            "capability": capability,
            "timestamp": utc_now(),
        }
    )


def _deep_merge(target: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
