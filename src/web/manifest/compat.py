from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def coerce_manifest_path(value: Any) -> Path | None:
    if isinstance(value, Path):
        candidate = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        candidate = Path(text)
    else:
        return None
    try:
        if not candidate.exists():
            return None
    except (OSError, ValueError):
        return None
    return candidate


def relative_to_run_dir(path: Path, run_dir: Path) -> Path | None:
    for candidate_path, candidate_run_dir in relative_candidates(path, run_dir):
        try:
            return candidate_path.relative_to(candidate_run_dir)
        except ValueError:
            continue

    path_parts = normalized_parts(path)
    run_parts = normalized_parts(run_dir)
    if len(path_parts) < len(run_parts) or path_parts[: len(run_parts)] != run_parts:
        return None

    actual_path = Path(path).resolve(strict=False)
    actual_parts = actual_path.parts
    if len(actual_parts) < len(run_parts):
        return None
    relative_parts = actual_parts[len(run_parts) :]
    return Path(*relative_parts) if relative_parts else Path()


def rewrite_run_root_paths(value: Any, *, source_root: Path, target_root: Path) -> Any:
    if isinstance(value, dict):
        return {key: rewrite_run_root_paths(item, source_root=source_root, target_root=target_root) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_run_root_paths(item, source_root=source_root, target_root=target_root) for item in value]
    if isinstance(value, str):
        return rewrite_string_path(value, source_root=source_root, target_root=target_root)
    return value


def rewrite_string_path(text: str, *, source_root: Path, target_root: Path) -> str:
    raw = str(text or "")
    candidates = {
        str(source_root),
        str(source_root).replace("\\", "/"),
        str(source_root).replace("/", "\\"),
    }
    for candidate in sorted(candidates, key=len, reverse=True):
        if candidate and raw.startswith(candidate):
            suffix = raw[len(candidate) :].lstrip("\\/")
            if not suffix:
                return str(target_root)
            return str(target_root / Path(*suffix.replace("\\", "/").split("/")))
    return raw


def apply_imported_run_semantics(
    manifest: dict[str, Any],
    *,
    target_root: Path,
    new_run_id: str,
    imported_at: str,
    package_filename: str,
    builtin_source: bool,
) -> dict[str, Any]:
    rewritten = manifest
    rewritten["run_id"] = new_run_id
    rewritten["created_at"] = imported_at
    rewritten["updated_at"] = imported_at
    rewritten["entrypoint"] = "builtin" if builtin_source else "import"
    rewritten["control"] = {
        "stop_requested": False,
        "stop_requested_at": "",
        "stop_acknowledged_at": "",
    }
    rewritten.setdefault("timing", {})
    rewritten["timing"]["started_at"] = ""
    rewritten["timing"]["completed_at"] = ""
    rewritten["timing"]["failed_at"] = ""
    rewritten["timing"]["stopped_at"] = ""
    rewritten["timing"]["elapsed_seconds"] = 0.0
    rewritten["timing"]["elapsed_text"] = ""
    rewritten["imported_from"] = {
        "package_filename": package_filename,
        "builtin_source": builtin_source,
        "imported_at": imported_at,
    }
    rewritten.setdefault("webui", {})
    novel_id = str(rewritten.get("novel_id", "")).strip()
    rewritten["webui"]["run_dir"] = str(target_root)
    rewritten["webui"]["input_dir"] = str((target_root / "input").resolve())
    rewritten["webui"]["payload_dir"] = str((target_root / "payloads").resolve())
    rewritten["webui"]["artifact_dir"] = str((target_root / "artifacts").resolve())
    rewritten["webui"]["workspace"] = {
        "characters_root": str((target_root / "artifacts" / "characters" / novel_id).resolve()),
        "relations_root": str((target_root / "artifacts" / "relations").resolve()),
    }
    rewritten.pop("file_urls", None)
    rewritten.setdefault("events", []).append(
        {
            "stage": "builtin_cloned" if builtin_source else "run_imported",
            "status": "complete",
            "message": "已从内置书卷创建本地副本。" if builtin_source else "已导入小说包并生成本地书卷。",
            "character": "",
            "capability": "verify_workflow",
            "timestamp": imported_at,
        }
    )
    return rewritten


def relative_candidates(path: Path, run_dir: Path) -> list[tuple[Path, Path]]:
    path_obj = Path(path)
    run_dir_obj = Path(run_dir)
    pairs = [
        (path_obj, run_dir_obj),
        (path_obj.resolve(strict=False), run_dir_obj.resolve(strict=False)),
        (Path(os.path.realpath(os.fspath(path_obj))), Path(os.path.realpath(os.fspath(run_dir_obj)))),
    ]
    ordered: list[tuple[Path, Path]] = []
    seen: set[tuple[str, str]] = set()
    for candidate_path, candidate_run_dir in pairs:
        key = (os.fspath(candidate_path), os.fspath(candidate_run_dir))
        if key in seen:
            continue
        seen.add(key)
        ordered.append((candidate_path, candidate_run_dir))
    return ordered


def normalized_parts(path: Path) -> tuple[str, ...]:
    resolved = Path(path).resolve(strict=False)
    return tuple(part.casefold() for part in resolved.parts)


def reconcile_discovered_artifacts(
    manifest: dict[str, Any],
    *,
    character_index: list[dict[str, Any]],
    relation_graph: dict[str, Any] | None,
) -> dict[str, Any]:
    updated = manifest
    artifacts = updated.setdefault("artifacts", {})
    artifact_index = updated.setdefault("artifact_index", {})
    progress = updated.setdefault("progress", {})

    cards = [item for item in list(character_index or []) if isinstance(item, dict)]
    artifact_index["characters"] = cards
    artifacts["character_dirs"] = {
        str(item.get("name", "")).strip(): str(item.get("persona_dir", "")).strip()
        for item in cards
        if str(item.get("name", "")).strip() and str(item.get("persona_dir", "")).strip()
    }

    completed_names = [str(item.get("name", "")).strip() for item in cards if str(item.get("name", "")).strip()]
    progress["completed_characters"] = completed_names
    progress["completed_count"] = len(completed_names)
    locked_characters = [str(item).strip() for item in list(updated.get("locked_characters", []) or []) if str(item).strip()]
    if locked_characters and len(completed_names) >= len(locked_characters):
        progress["current_character"] = ""

    if relation_graph:
        relation = dict(relation_graph)
        artifacts["relation_graph"] = relation
        artifact_index["relation_graph"] = relation
        progress["graph_status"] = "complete"
    else:
        artifacts["relation_graph"] = {}
        artifact_index["relation_graph"] = {}
        graph_status = str(progress.get("graph_status", "")).strip()
        if graph_status not in {"failed", "running"}:
            progress["graph_status"] = "pending"
    artifacts["payloads"] = _filter_existing_payloads(artifacts.get("payloads", {}))
    return updated


def _filter_existing_payloads(payloads: Any) -> dict[str, str]:
    if not isinstance(payloads, dict):
        return {}
    filtered: dict[str, str] = {}
    for key, value in payloads.items():
        name = str(key).strip()
        path_text = str(value).strip()
        if not name or not path_text:
            continue
        try:
            if not Path(path_text).exists():
                continue
        except (OSError, ValueError):
            continue
        filtered[name] = path_text
    return filtered
