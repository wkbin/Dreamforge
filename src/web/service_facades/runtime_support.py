from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
import logging
import threading
from pathlib import Path
from typing import Any, Callable, ContextManager

from src.core.config import Config
from src.web.manifest import load_json_file, write_json_file
from src.web.pipeline import (
    build_background_run_kwargs,
    prepare_background_manifest,
    run_pipeline_safely,
    start_background_thread,
)
from src.web.run_ops import (
    build_runtime_config_for_run,
    decode_base64_text,
    is_model_configured_payload,
    new_run_id,
    normalize_characters,
)

logger = logging.getLogger(__name__)


class RuntimeSupportMixin:
    def _start_background_run(
        self,
        *,
        manifest_path: Path,
        novel_path: Path,
        locked_characters: list[str],
        relation_characters: list[str] | None = None,
        max_sentences: int,
        max_chars: int,
    ) -> None:
        manifest = prepare_background_manifest(self._load_manifest(manifest_path) or {}, utc_now=_utc_now)
        self._write_json(manifest_path, manifest)

        run_id = str(manifest.get("run_id", "")).strip() or manifest_path.parent.name
        start_background_thread(
            active_run_threads=self._active_run_threads,
            target=self._run_automatic_pipeline_safely,
            kwargs=build_background_run_kwargs(
                manifest_path=manifest_path,
                novel_path=novel_path,
                run_id=run_id,
                locked_characters=locked_characters,
                relation_characters=relation_characters,
                max_sentences=max_sentences,
                max_chars=max_chars,
            ),
            run_id=run_id,
        )

    def _run_automatic_pipeline_safely(self, **kwargs: Any) -> None:
        run_pipeline_safely(
            kwargs=kwargs,
            run_pipeline=self._run_automatic_pipeline,
            active_run_threads=self._active_run_threads,
            logger=logger,
        )

    def _build_runtime_config_for_run(self, *, run_dir: Path) -> Config:
        return build_runtime_config_for_run(
            run_dir=run_dir,
            project_root=self.project_root,
            model_payload=self._load_model_settings_payload(),
        )

    def _manifest_lock_context(self, path: Path) -> ContextManager[object]:
        run_id = self._manifest_run_id(path)
        if not run_id:
            return nullcontext()
        return self._manifest_lock_for_run(run_id)

    def _manifest_lock_for_run(self, run_id: str) -> threading.RLock:
        with self._run_manifest_locks_guard:
            lock = self._run_manifest_locks.get(run_id)
            if lock is None:
                lock = threading.RLock()
                self._run_manifest_locks[run_id] = lock
            return lock

    def _manifest_run_id(self, path: Path) -> str:
        target = Path(path)
        if target.name != "run_manifest.json":
            return ""
        try:
            relative = target.resolve(strict=False).relative_to(self.runs_root.resolve(strict=False))
        except ValueError:
            return ""
        parts = relative.parts
        if len(parts) != 2 or parts[1] != "run_manifest.json":
            return ""
        return str(parts[0]).strip()

    @staticmethod
    def _merge_manifest_control(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        existing_control = dict(existing.get("control", {}) or {})
        if not existing_control:
            return incoming
        merged = dict(incoming)
        incoming_control = dict(merged.get("control", {}) or {})
        if bool(existing_control.get("stop_requested", False)):
            incoming_control["stop_requested"] = True
        for key in ("stop_requested_at", "stop_acknowledged_at"):
            existing_value = str(existing_control.get(key, "")).strip()
            incoming_value = str(incoming_control.get(key, "")).strip()
            if existing_value and not incoming_value:
                incoming_control[key] = existing_value
        merged["control"] = incoming_control
        return merged

    def _update_manifest(
        self,
        path: Path,
        updater: Callable[[dict[str, Any]], dict[str, Any] | None],
        *,
        create_if_missing: bool = False,
    ) -> dict[str, Any]:
        target = Path(path)
        with self._manifest_lock_context(target):
            existing = load_json_file(target)
            if not isinstance(existing, dict):
                if not create_if_missing:
                    raise FileNotFoundError(self._manifest_run_id(target) or target.parent.name)
                existing = {}

            current = deepcopy(existing)
            updated = updater(current)
            next_payload = current if updated is None else updated
            if not isinstance(next_payload, dict):
                raise ValueError("Manifest updater must return a dict payload.")

            payload_to_write = next_payload
            if target.name == "run_manifest.json":
                payload_to_write = self._merge_manifest_control(existing, next_payload)
            write_json_file(target, payload_to_write)
            return payload_to_write

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        target = Path(path)
        with self._manifest_lock_context(target):
            merged_payload = payload
            if target.name == "run_manifest.json":
                existing = load_json_file(target)
                if isinstance(existing, dict):
                    merged_payload = self._merge_manifest_control(existing, payload)
            write_json_file(target, merged_payload)

    @staticmethod
    def _normalize_characters(characters: list[str]) -> list[str]:
        return normalize_characters(characters)

    @staticmethod
    def _decode_base64(value: str) -> bytes:
        return decode_base64_text(value)

    @staticmethod
    def _new_run_id() -> str:
        return new_run_id()

    @staticmethod
    def _is_model_configured_payload(payload: dict[str, Any]) -> bool:
        return is_model_configured_payload(payload)


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
