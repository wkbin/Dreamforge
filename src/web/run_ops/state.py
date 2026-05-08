from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable


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
