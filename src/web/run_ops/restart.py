from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from src.utils.file_utils import safe_filename


def classify_requested_characters(
    manifest: dict[str, Any],
    *,
    locked_characters: list[str],
    normalize_characters: Callable[[list[str]], list[str]],
) -> dict[str, Any]:
    existing_character_names: set[str] = set()
    artifact_index = manifest.get("artifact_index", {}).get("characters", [])
    if isinstance(artifact_index, list):
        existing_character_names.update(
            str(item.get("name", "")).strip() for item in artifact_index if isinstance(item, dict)
        )
    character_dirs = manifest.get("artifacts", {}).get("character_dirs", {})
    if isinstance(character_dirs, dict):
        existing_character_names.update(str(name).strip() for name in character_dirs.keys())
    existing_requested = [name for name in locked_characters if name in existing_character_names]
    new_requested = [name for name in locked_characters if name not in existing_character_names]
    relation_characters = normalize_characters([*existing_character_names, *locked_characters])
    return {
        "existing_character_names": sorted(existing_character_names),
        "existing_requested": existing_requested,
        "new_requested": new_requested,
        "relation_characters": relation_characters,
    }


def prepare_restart_novel_source(
    *,
    runs_root: Path,
    run_id: str,
    manifest: dict[str, Any],
    novel_name: str,
    novel_content_base64: str,
    decode_base64: Callable[[str], bytes],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    using_new_source = bool(str(novel_content_base64 or "").strip())
    if using_new_source:
        run_dir = runs_root / run_id
        updates_dir = run_dir / "input" / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        file_name = safe_filename(novel_name or "novel-update.txt")
        raw_bytes = decode_base64(novel_content_base64)
        if not raw_bytes:
            raise ValueError("Novel content is empty.")
        stamped_name = f"{utc_now().replace(':', '').replace('-', '')}_{file_name}"
        novel_path = updates_dir / stamped_name
        novel_path.write_bytes(raw_bytes)
        return {
            "using_new_source": True,
            "novel_path": novel_path,
            "raw_bytes": raw_bytes,
        }

    novel_path = Path(str(manifest.get("novel_path", "")).strip())
    if not novel_path.exists():
        raise ValueError("Novel source file is missing for this run.")
    return {
        "using_new_source": False,
        "novel_path": novel_path,
        "raw_bytes": None,
    }


def apply_restart_manifest_state(
    manifest: dict[str, Any],
    *,
    locked_characters: list[str],
    novel_path: Path,
    using_new_source: bool,
    new_requested: list[str],
    existing_requested: list[str],
    pending_characters: list[str],
    resume_completed_characters: list[str],
    relation_characters: list[str],
    redistill_summary: str,
    novel_source_entry: dict[str, Any] | None,
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    now = utc_now()
    progress = manifest.setdefault("progress", {})
    progress.update(
        {
            "stage": "characters_locked",
            "message": redistill_summary,
            "current_character": "",
            "completed_characters": resume_completed_characters,
            "total_characters": len(locked_characters),
            "completed_count": len(resume_completed_characters),
            "graph_status": "pending",
            "chunking": {},
        }
    )
    manifest["locked_characters"] = locked_characters
    manifest["novel_path"] = str(novel_path.resolve())
    manifest["redistill"] = {
        "requested_characters": locked_characters,
        "new_characters": new_requested,
        "existing_characters": existing_requested,
        "pending_characters": pending_characters,
        "resume_completed_characters": resume_completed_characters,
        "relation_characters": relation_characters,
        "summary": redistill_summary,
        "used_new_source": using_new_source,
        "source_name": Path(novel_path).name,
    }
    if using_new_source and novel_source_entry is not None:
        sources = list(manifest.get("novel_sources", []))
        sources.append(novel_source_entry)
        manifest["novel_sources"] = sources
    manifest["status"] = "running"
    manifest["success"] = False
    manifest["updated_at"] = now
    manifest["timing"] = {
        "started_at": now,
        "completed_at": "",
        "failed_at": "",
        "stopped_at": "",
        "elapsed_seconds": 0.0,
        "elapsed_text": "",
    }
    manifest["control"] = {
        "stop_requested": False,
        "stop_requested_at": "",
        "stop_acknowledged_at": "",
    }
    manifest["quality"] = {
        "excerpt_focus": {
            "matched_characters": [],
            "missing_characters": [],
            "strategy": "",
        },
        "stage_presence": [],
        "character_focus": {},
        "profile_repairs": {"count": 0, "characters": []},
        "relation_repairs": {"count": 0, "pairs": []},
    }
    manifest.setdefault("summary", {}).update(
        {
            "characters_total": len(locked_characters),
            "characters_completed": len(resume_completed_characters),
            "graph_status": "pending",
            "status_text": "waiting_for_payloads",
            "chunking": {},
        }
    )
    manifest.setdefault("artifacts", {}).setdefault("chunking", {})
    manifest.setdefault("capabilities", {})["distill"] = {
        "status": "preparing",
        "success": False,
        "updated_at": now,
        "message": "incremental distill requested",
        "outputs": {
            "update_mode": "incremental" if existing_requested else "refresh",
            "used_new_source": using_new_source,
        },
    }
    manifest["capabilities"]["export_graph"] = {
        "status": "preparing",
        "success": False,
        "updated_at": now,
        "message": "graph regeneration requested",
    }
    manifest["events"] = [
        {
            "stage": "redistill_requested",
            "status": "running",
            "message": redistill_summary,
            "character": "",
            "capability": "distill",
            "timestamp": now,
        }
    ]
    if using_new_source:
        manifest["events"].append(
            {
                "stage": "source_updated",
                "status": "running",
                "message": f"已换入新的书段：{Path(novel_path).name}",
                "character": "",
                "capability": "distill",
                "timestamp": now,
            }
        )
    return manifest
