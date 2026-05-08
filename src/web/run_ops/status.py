from __future__ import annotations

from typing import Any, Callable


def refresh_run_manifest(
    manifest: dict[str, Any],
    *,
    discover_artifacts: Callable[[dict[str, Any]], dict[str, Any]],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    refreshed = discover_artifacts(manifest)
    refreshed["updated_at"] = utc_now()
    return refreshed


def stop_run_manifest(
    manifest: dict[str, Any],
    *,
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    status = str(manifest.get("status", "")).strip()
    if status != "running":
        raise ValueError("只有正在蒸馏的书卷才能停止。")

    control = manifest.setdefault("control", {})
    if bool(control.get("stop_requested", False)):
        return manifest

    now_text = utc_now()
    control["stop_requested"] = True
    control["stop_requested_at"] = now_text
    progress = manifest.setdefault("progress", {})
    progress["message"] = "已收到停止请求，正在收束当前步骤"
    summary = manifest.setdefault("summary", {})
    summary["status_text"] = "stop_requested"
    manifest["updated_at"] = now_text
    manifest.setdefault("events", []).append(
        {
            "stage": "stop_requested",
            "status": "running",
            "message": "已收到停止请求，正在收束当前步骤",
            "character": str(progress.get("current_character", "")).strip(),
            "capability": "verify_workflow",
            "timestamp": now_text,
        }
    )
    return manifest
