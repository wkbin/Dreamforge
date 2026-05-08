from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable


def list_runs(
    *,
    runs_root: Path,
    load_manifest: Callable[[Path], dict[str, Any] | None],
    serialize_manifest: Callable[[dict[str, Any]], dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for manifest_path in sorted(runs_root.glob("*/run_manifest.json"), reverse=True):
        payload = load_manifest(manifest_path)
        if payload:
            items.append(serialize_manifest(payload))
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return items


def list_recent_sessions(
    *,
    runs_root: Path,
    load_manifest: Callable[[Path], dict[str, Any] | None],
    list_sessions: Callable[[str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for manifest_path in sorted(runs_root.glob("*/run_manifest.json"), reverse=True):
        manifest = load_manifest(manifest_path)
        if not manifest:
            continue
        run_id = str(manifest.get("run_id", "")).strip()
        novel_id = str(manifest.get("novel_id", "")).strip()
        if not run_id:
            continue
        for session in list_sessions(run_id):
            session["novel_id"] = novel_id
            items.append(session)
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return items


def delete_run_group(
    *,
    run_id: str,
    runs_root: Path,
    require_manifest: Callable[[str], dict[str, Any]],
    load_manifest: Callable[[Path], dict[str, Any] | None],
) -> dict[str, Any]:
    manifest = require_manifest(run_id)
    target_novel_id = str(manifest.get("novel_id", "")).strip()
    if not target_novel_id:
        raise ValueError("Run is missing novel_id.")

    targets: list[Path] = []
    deleted_run_ids: list[str] = []
    deleted_sessions = 0
    blocked_runs: list[str] = []
    for manifest_path in sorted(runs_root.glob("*/run_manifest.json")):
        payload = load_manifest(manifest_path)
        if not payload:
            continue
        if str(payload.get("novel_id", "")).strip() != target_novel_id:
            continue
        if str(payload.get("status", "")).strip() == "running":
            blocked_runs.append(str(payload.get("run_id", "")).strip() or manifest_path.parent.name)
            continue
        targets.append(manifest_path.parent)

    if blocked_runs:
        raise ValueError("这本书还在整理中，暂时不能删除。请等这一轮结束后再删。")
    if not targets:
        raise FileNotFoundError(run_id)

    for run_dir in targets:
        manifest_path = run_dir / "run_manifest.json"
        payload = load_manifest(manifest_path) or {}
        deleted_run_ids.append(str(payload.get("run_id", "")).strip() or run_dir.name)
        dialogue_dir = run_dir / "dialogue"
        if dialogue_dir.exists():
            deleted_sessions += len([path for path in dialogue_dir.iterdir() if path.is_dir()])
        shutil.rmtree(run_dir, ignore_errors=False)

    return {
        "status": "deleted",
        "novel_id": target_novel_id,
        "deleted_run_count": len(deleted_run_ids),
        "deleted_session_count": deleted_sessions,
        "deleted_run_ids": deleted_run_ids,
    }
