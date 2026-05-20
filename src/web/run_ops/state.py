from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def derive_summary_graph_status(manifest: dict[str, Any]) -> str:
    progress = dict(manifest.get("progress", {}) or {})
    progress_graph_status = str(progress.get("graph_status", "")).strip()
    if progress_graph_status:
        return progress_graph_status
    summary_graph_status = str((manifest.get("summary", {}) or {}).get("graph_status", "")).strip()
    return summary_graph_status


def derive_summary_status_text(manifest: dict[str, Any]) -> str:
    status = str(manifest.get("status", "")).strip()
    progress = dict(manifest.get("progress", {}) or {})
    control = dict(manifest.get("control", {}) or {})
    stage = str(progress.get("stage", "")).strip()
    total_characters = max(0, _safe_int(progress.get("total_characters", 0)))
    completed_characters = max(0, _safe_int(progress.get("completed_count", 0)))
    graph_status = derive_summary_graph_status(manifest)
    locked_characters = list(manifest.get("locked_characters", []) or [])
    if total_characters <= 0 and locked_characters:
        total_characters = len(locked_characters)

    if status == "ready":
        return "workflow_complete"
    if status == "failed":
        return "failed"
    if status == "stopped":
        return "stopped"
    if status == "running":
        if bool(control.get("stop_requested", False)):
            return "stop_requested"
        if stage == "relation_payload_ready":
            return "waiting_for_host_generation"
        if graph_status == "complete":
            if total_characters > 0 and completed_characters >= total_characters:
                return "waiting_for_verification"
            return "graph_ready"
        if total_characters > 0 and completed_characters >= total_characters and graph_status in {"", "pending", "running"}:
            return "graph_pending"
        return "waiting_for_payloads"
    return str((manifest.get("summary", {}) or {}).get("status_text", "")).strip() or "waiting_for_payloads"


def project_manifest_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    summary = manifest.setdefault("summary", {})
    progress = dict(manifest.get("progress", {}) or {})
    total_characters = max(0, _safe_int(progress.get("total_characters", 0)))
    completed_characters = max(0, _safe_int(progress.get("completed_count", 0)))
    if total_characters <= 0:
        total_characters = len(list(manifest.get("locked_characters", []) or []))
    summary["characters_total"] = total_characters
    summary["characters_completed"] = completed_characters
    summary["graph_status"] = derive_summary_graph_status(manifest) or "pending"
    summary["status_text"] = derive_summary_status_text(manifest)
    timing = dict(manifest.get("timing", {}) or {})
    elapsed_text = str(timing.get("elapsed_text", "")).strip()
    if elapsed_text:
        summary["elapsed_text"] = elapsed_text
    return summary


def format_elapsed_text(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, remain = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if remain or not parts:
        parts.append(f"{remain}秒")
    return "".join(parts)


def finalize_manifest_timing(manifest: dict[str, Any], *, outcome: str, now_text: str) -> None:
    timing = manifest.setdefault("timing", {})
    started_at = str(timing.get("started_at", "")).strip()
    finished_key = {
        "completed": "completed_at",
        "failed": "failed_at",
        "stopped": "stopped_at",
    }.get(str(outcome or "").strip(), "failed_at")
    timing[finished_key] = now_text
    if started_at:
        try:
            started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            finished = datetime.fromisoformat(now_text.replace("Z", "+00:00"))
            elapsed_seconds = max(0.0, (finished - started).total_seconds())
        except Exception:
            elapsed_seconds = 0.0
    else:
        elapsed_seconds = 0.0
    timing["elapsed_seconds"] = round(elapsed_seconds, 3)
    timing["elapsed_text"] = format_elapsed_text(elapsed_seconds)


def is_stop_requested(
    manifest_path: Path,
    *,
    load_manifest: Callable[[Path], dict[str, Any] | None],
) -> bool:
    manifest = load_manifest(manifest_path) or {}
    return bool((manifest.get("control", {}) or {}).get("stop_requested", False))
