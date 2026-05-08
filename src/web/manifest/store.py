from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def manifest_path(runs_root: Path, run_id: str) -> Path:
    return runs_root / run_id / "run_manifest.json"


def require_manifest(
    run_id: str,
    *,
    loader: Callable[[Path], dict[str, Any] | None],
    runs_root: Path,
) -> dict[str, Any]:
    payload = loader(manifest_path(runs_root, run_id))
    if not payload:
        raise FileNotFoundError(run_id)
    return payload


def ensure_run_exists(runs_root: Path, run_id: str) -> None:
    if not manifest_path(runs_root, run_id).exists():
        raise FileNotFoundError(run_id)


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest(
    manifest_path_value: Path,
    *,
    reconcile: Callable[[Path, dict[str, Any]], tuple[dict[str, Any], bool]],
    writer: Callable[[Path, dict[str, Any]], None],
) -> dict[str, Any] | None:
    if not manifest_path_value.exists():
        return None
    payload = json.loads(manifest_path_value.read_text(encoding="utf-8"))
    payload, changed = reconcile(manifest_path_value, payload)
    if changed:
        writer(manifest_path_value, payload)
    return payload


def reconcile_loaded_manifest(
    manifest_path_value: Path,
    payload: dict[str, Any],
    *,
    is_thread_alive: Callable[[str], bool],
    utc_now: Callable[[], str],
    finalize_manifest_timing: Callable[[dict[str, Any], str], None],
) -> tuple[dict[str, Any], bool]:
    manifest = dict(payload or {})
    run_id = str(manifest.get("run_id", "")).strip() or manifest_path_value.parent.name
    status = str(manifest.get("status", "")).strip()
    control = dict(manifest.get("control", {}) or {})
    thread_alive = is_thread_alive(run_id)
    if status == "running" and bool(control.get("stop_requested", False)) and not thread_alive:
        now_text = utc_now()
        manifest["status"] = "stopped"
        manifest["success"] = False
        manifest["updated_at"] = now_text
        progress = manifest.setdefault("progress", {})
        progress["stage"] = "stopped"
        current_character = str(progress.get("current_character", "")).strip()
        progress["message"] = f"已停止蒸馏，停在 {current_character}。" if current_character else "这次蒸馏已停止。"
        summary = manifest.setdefault("summary", {})
        summary["status_text"] = "stopped"
        control["stop_acknowledged_at"] = str(control.get("stop_acknowledged_at", "")).strip() or now_text
        manifest["control"] = control
        finalize_manifest_timing(manifest, "stopped")
        if manifest.get("timing", {}).get("elapsed_text"):
            summary["elapsed_text"] = manifest["timing"]["elapsed_text"]
        manifest.setdefault("capabilities", {})["verify_workflow"] = {
            "status": "stopped",
            "success": False,
            "updated_at": now_text,
            "message": "automatic workflow stopped after restart reconciliation",
        }
        events = manifest.setdefault("events", [])
        if not any(str(item.get("stage", "")).strip() == "stopped" for item in events if isinstance(item, dict)):
            events.append(
                {
                    "stage": "stopped",
                    "status": "stopped",
                    "message": progress["message"],
                    "character": current_character,
                    "capability": "verify_workflow",
                    "timestamp": now_text,
                }
            )
        return manifest, True
    return manifest, False
