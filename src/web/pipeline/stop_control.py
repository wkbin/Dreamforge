from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def assert_run_not_stopped(
    manifest_path: Path,
    *,
    message: str,
    current_character: str,
    update_manifest: Callable[[Path, Callable[[dict[str, Any]], dict[str, Any] | None]], dict[str, Any]],
    utc_now: Callable[[], str],
    is_stop_requested: Callable[[Path], bool],
    stopped_error_type: type[BaseException],
) -> None:
    if not is_stop_requested(manifest_path):
        return

    def _ack_stop_requested(current: dict[str, Any]) -> dict[str, Any]:
        control = current.setdefault("control", {})
        if not str(control.get("stop_acknowledged_at", "")).strip():
            control["stop_acknowledged_at"] = utc_now()
            current["updated_at"] = utc_now()
        return current

    update_manifest(manifest_path, _ack_stop_requested)
    if current_character:
        raise stopped_error_type(f"已停止蒸馏，停在 {current_character}。")
    raise stopped_error_type(message)
