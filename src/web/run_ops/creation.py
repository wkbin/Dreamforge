from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .state import project_manifest_summary


def ensure_run_workspace(run_dir: Path) -> dict[str, Path]:
    input_dir = run_dir / "input"
    payload_dir = run_dir / "payloads"
    artifact_dir = run_dir / "artifacts"
    for directory in (input_dir, payload_dir, artifact_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "run_dir": run_dir,
        "input_dir": input_dir,
        "payload_dir": payload_dir,
        "artifact_dir": artifact_dir,
    }


def build_initial_run_manifest(
    *,
    run_id: str,
    novel_id: str,
    novel_path: Path,
    novel_source_entry: dict[str, Any],
    model_settings: dict[str, Any],
    locked_characters: list[str],
    workspace: dict[str, Path],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    now = utc_now()
    manifest = {
        "kind": "zaomeng_web_run",
        "schema_version": 1,
        "run_id": run_id,
        "novel_id": novel_id,
        "novel_path": str(novel_path.resolve()),
        "novel_sources": [novel_source_entry],
        "created_at": now,
        "updated_at": now,
        "status": "running",
        "success": False,
        "entrypoint": "webui",
        "timing": {
            "started_at": now,
            "completed_at": "",
            "failed_at": "",
            "stopped_at": "",
            "elapsed_seconds": 0.0,
            "elapsed_text": "",
        },
        "model_settings": model_settings,
        "locked_characters": locked_characters,
        "progress": {
            "stage": "characters_locked",
            "message": "已锁定待蒸馏角色",
            "current_character": "",
            "completed_characters": [],
            "total_characters": len(locked_characters),
            "completed_count": 0,
            "graph_status": "pending",
            "chunking": {},
        },
        "capabilities": {
            "distill": {"status": "preparing", "success": False, "updated_at": now},
            "materialize": {"status": "pending", "success": False, "updated_at": now},
            "export_graph": {"status": "preparing", "success": False, "updated_at": now},
            "verify_workflow": {"status": "pending", "success": False, "updated_at": now},
        },
        "artifacts": {
            "payloads": {},
            "status_files": {},
            "character_dirs": {},
            "relation_graph": {},
            "chunking": {},
        },
        "summary": {
            "characters_total": len(locked_characters),
            "characters_completed": 0,
            "graph_status": "pending",
            "status_text": "waiting_for_payloads",
            "chunking": {},
        },
        "quality": {
            "excerpt_focus": {
                "matched_characters": [],
                "missing_characters": [],
                "strategy": "",
            },
            "stage_presence": [],
            "character_focus": {},
            "profile_repairs": {"count": 0, "characters": []},
            "relation_repairs": {"count": 0, "pairs": []},
        },
        "events": [
            {
                "stage": "characters_locked",
                "status": "running",
                "message": "已锁定待蒸馏角色",
                "character": "",
                "capability": "distill",
                "timestamp": now,
            }
        ],
        "control": {
            "stop_requested": False,
            "stop_requested_at": "",
            "stop_acknowledged_at": "",
        },
        "webui": {
            "run_dir": str(workspace["run_dir"].resolve()),
            "input_dir": str(workspace["input_dir"].resolve()),
            "payload_dir": str(workspace["payload_dir"].resolve()),
            "artifact_dir": str(workspace["artifact_dir"].resolve()),
        },
    }
    project_manifest_summary(manifest)
    return manifest


def attach_workspace_roots(manifest: dict[str, Any], *, characters_root: Path, relations_root: Path) -> None:
    manifest.setdefault("webui", {})["workspace"] = {
        "characters_root": str(characters_root.resolve()),
        "relations_root": str(relations_root.resolve()),
    }


def apply_manual_payload_manifest_state(
    manifest: dict[str, Any],
    *,
    distill_payload: dict[str, Any],
    relation_payload: dict[str, Any],
    distill_payload_path: Path,
    relation_payload_path: Path,
    locked_characters: list[str],
    chunk_overview_from_payload: Callable[[dict[str, Any]], dict[str, Any]],
    build_progress_chunking_from_artifacts: Callable[[dict[str, Any] | None], dict[str, Any]],
    build_summary_chunking: Callable[[dict[str, Any] | None], dict[str, Any]],
    build_quality_snapshot: Callable[..., dict[str, Any]],
    stage_presence: Callable[[dict[str, Any] | None], list[str]],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    now = utc_now()
    manifest["progress"]["stage"] = "relation_payload_ready"
    manifest["progress"]["message"] = "蒸馏与关系提取 payload 已准备完成"
    manifest["updated_at"] = now
    manifest["capabilities"]["distill"] = {
        "status": "ready",
        "success": False,
        "updated_at": now,
        "message": "distill payload ready",
    }
    manifest["capabilities"]["export_graph"] = {
        "status": "ready",
        "success": False,
        "updated_at": now,
        "message": "relation payload ready",
    }
    manifest["artifacts"]["payloads"] = {
        "distill": str(distill_payload_path.resolve()),
        "relation": str(relation_payload_path.resolve()),
    }
    manifest["artifacts"]["chunking"] = {
        "distill": chunk_overview_from_payload(distill_payload),
        "relation": chunk_overview_from_payload(relation_payload),
    }
    manifest["progress"]["chunking"] = build_progress_chunking_from_artifacts(manifest["artifacts"]["chunking"])
    manifest["summary"]["chunking"] = build_summary_chunking(manifest["progress"]["chunking"])
    excerpt_focus = dict(distill_payload.get("request", {}).get("excerpt_focus", {}) or {})
    excerpt_stages = dict(distill_payload.get("request", {}).get("excerpt_stages", {}) or {})
    matched_characters = list(excerpt_focus.get("matched_characters", []) or [])
    missing_characters = list(excerpt_focus.get("missing_characters", []) or [])
    strategy = str(excerpt_focus.get("strategy", "")).strip()
    manifest["excerpt_focus"] = {
        "matched_characters": matched_characters,
        "missing_characters": missing_characters,
        "strategy": strategy,
    }
    manifest["quality"] = build_quality_snapshot(
        matched_characters=matched_characters,
        missing_characters=missing_characters,
        strategy=strategy,
        excerpt_stages=excerpt_stages,
        character_focus={
            name: {
                "matched": name in matched_characters,
                "missing": name in missing_characters,
                "stage_presence": stage_presence(excerpt_stages),
            }
            for name in locked_characters
        },
    )
    manifest.setdefault("events", []).append(
        {
            "stage": "distill_payload_ready",
            "status": "running",
            "message": "蒸馏 payload 已生成，等待宿主 LLM 执行",
            "character": "",
            "capability": "distill",
            "timestamp": now,
        }
    )
    manifest["events"].append(
        {
            "stage": "relation_payload_ready",
            "status": "running",
            "message": "关系图谱 payload 已生成，等待宿主 LLM 执行",
            "character": "",
            "capability": "export_graph",
            "timestamp": now,
        }
    )
    project_manifest_summary(manifest)
    return manifest
