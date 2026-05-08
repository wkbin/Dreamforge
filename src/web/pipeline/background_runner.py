from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable


def prepare_background_manifest(manifest: dict[str, Any], *, utc_now: Callable[[], str]) -> dict[str, Any]:
    manifest["updated_at"] = utc_now()
    manifest.setdefault("progress", {})["stage"] = "queued"
    manifest["progress"]["message"] = "已开始蒸馏任务"
    manifest.setdefault("summary", {})["status_text"] = "waiting_for_payloads"
    manifest.setdefault("events", []).append(
        {
            "stage": "queued",
            "status": "running",
            "message": "已开始蒸馏任务",
            "character": "",
            "capability": "verify_workflow",
            "timestamp": utc_now(),
        }
    )
    return manifest


def start_background_thread(
    *,
    active_run_threads: dict[str, threading.Thread],
    target: Callable[..., None],
    kwargs: dict[str, Any],
    run_id: str,
) -> None:
    thread = threading.Thread(
        target=target,
        kwargs=kwargs,
        daemon=True,
    )
    active_run_threads[run_id] = thread
    thread.start()


def run_pipeline_safely(
    *,
    kwargs: dict[str, Any],
    run_pipeline: Callable[..., Any],
    active_run_threads: dict[str, threading.Thread],
    logger: logging.Logger,
) -> None:
    run_id = str(kwargs.get("run_id", "")).strip()
    try:
        run_pipeline(**kwargs)
    except Exception as exc:
        logger.warning("Background distill run failed: %s", exc)
    finally:
        if run_id:
            thread = active_run_threads.get(run_id)
            if thread is threading.current_thread():
                active_run_threads.pop(run_id, None)


def build_background_run_kwargs(
    *,
    manifest_path: Path,
    novel_path: Path,
    run_id: str,
    locked_characters: list[str],
    relation_characters: list[str] | None,
    max_sentences: int,
    max_chars: int,
) -> dict[str, Any]:
    return {
        "manifest_path": manifest_path,
        "novel_path": novel_path,
        "run_id": run_id,
        "locked_characters": locked_characters,
        "relation_characters": relation_characters,
        "max_sentences": max_sentences,
        "max_chars": max_chars,
    }
