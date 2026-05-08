from __future__ import annotations

from typing import Any, Callable


def stage_presence(excerpt_stages: dict[str, Any] | None) -> list[str]:
    stages = dict(excerpt_stages or {})
    labels: list[str] = []
    mapping = {"start": "前段", "mid": "中段", "end": "后段"}
    for key, label in mapping.items():
        if str(stages.get(key, "")).strip():
            labels.append(label)
    return labels


def build_quality_snapshot(
    *,
    matched_characters: list[str],
    missing_characters: list[str],
    strategy: str,
    excerpt_stages: dict[str, Any] | None,
    character_focus: dict[str, Any] | None = None,
    profile_repairs: dict[str, Any] | None = None,
    relation_repairs: dict[str, Any] | None = None,
    normalize_characters: Callable[[list[str]], list[str]],
) -> dict[str, Any]:
    return {
        "excerpt_focus": {
            "matched_characters": normalize_characters(matched_characters),
            "missing_characters": normalize_characters(missing_characters),
            "strategy": str(strategy or "").strip(),
        },
        "stage_presence": stage_presence(excerpt_stages),
        "character_focus": dict(character_focus or {}),
        "profile_repairs": {
            "count": int((profile_repairs or {}).get("count", 0) or 0),
            "characters": normalize_characters((profile_repairs or {}).get("characters", [])),
        },
        "relation_repairs": {
            "count": int((relation_repairs or {}).get("count", 0) or 0),
            "pairs": [str(item).strip() for item in list((relation_repairs or {}).get("pairs", [])) if str(item).strip()],
        },
    }


def chunk_overview_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    request = dict(payload.get("request", {}) or {})
    meta = dict(payload.get("meta", {}) or {})
    return {
        "chunk_mode": str(request.get("chunk_mode", "single")).strip() or "single",
        "chunk_count": int(meta.get("chunk_count", 0) or 0),
        "merge_required": bool(meta.get("merge_required", False)),
    }


def build_progress_chunking_from_artifacts(chunking: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for capability, item in dict(chunking or {}).items():
        if not isinstance(item, dict):
            continue
        result[capability] = {
            "capability": capability,
            "mode": str(item.get("chunk_mode", "single")).strip() or "single",
            "chunk_count": int(item.get("chunk_count", 0) or 0),
            "current_chunk": 0,
            "current_label": "",
            "status": "pending",
            "merge_required": bool(item.get("merge_required", False)),
            "merge_status": "pending",
        }
    return result


def build_summary_chunking(chunking: dict[str, Any] | None) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for capability, item in dict(chunking or {}).items():
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


def update_manifest_chunk_progress(
    manifest: dict[str, Any],
    *,
    capability: str,
    mode: str = "",
    chunk_count: int | None = None,
    current_chunk: int | None = None,
    current_label: str = "",
    status: str = "",
    merge_required: bool | None = None,
    merge_status: str = "",
    extras: dict[str, Any] | None = None,
) -> None:
    artifacts = manifest.setdefault("artifacts", {})
    artifact_chunking = artifacts.setdefault("chunking", {})
    artifact_current = dict(artifact_chunking.get(capability, {}))
    if mode:
        artifact_current["chunk_mode"] = mode
    if chunk_count is not None:
        artifact_current["chunk_count"] = int(chunk_count or 0)
    if merge_required is not None:
        artifact_current["merge_required"] = bool(merge_required)
    if extras:
        artifact_current.update(dict(extras))
    artifact_chunking[capability] = artifact_current

    progress = manifest.setdefault("progress", {})
    progress_chunking = progress.setdefault("chunking", {})
    progress_current = dict(progress_chunking.get(capability, {}))
    progress_current["capability"] = capability
    if mode:
        progress_current["mode"] = mode
    if chunk_count is not None:
        progress_current["chunk_count"] = int(chunk_count or 0)
    if current_chunk is not None:
        progress_current["current_chunk"] = int(current_chunk or 0)
    if current_label or current_label == "":
        progress_current["current_label"] = str(current_label or "")
    if status:
        progress_current["status"] = status
    if merge_required is not None:
        progress_current["merge_required"] = bool(merge_required)
    if merge_status:
        progress_current["merge_status"] = merge_status
    progress_chunking[capability] = progress_current
    manifest.setdefault("summary", {})["chunking"] = build_summary_chunking(progress_chunking)
