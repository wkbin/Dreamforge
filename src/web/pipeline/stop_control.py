from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def assert_run_not_stopped(
    manifest_path: Path,
    *,
    message: str,
    current_character: str,
    load_manifest: Callable[[Path], dict[str, Any] | None],
    write_json: Callable[[Path, dict[str, Any]], None],
    utc_now: Callable[[], str],
    is_stop_requested: Callable[[Path], bool],
    stopped_error_type: type[BaseException],
) -> None:
    if not is_stop_requested(manifest_path):
        return
    manifest = load_manifest(manifest_path) or {}
    control = manifest.setdefault("control", {})
    if not str(control.get("stop_acknowledged_at", "")).strip():
        control["stop_acknowledged_at"] = utc_now()
        manifest["updated_at"] = utc_now()
        write_json(manifest_path, manifest)
    if current_character:
        raise stopped_error_type(f"已停止蒸馏，停在 {current_character}。")
    raise stopped_error_type(message)
