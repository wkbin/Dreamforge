from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.web.artifacts import discover_character_cards, discover_relation_graph
from src.web.chat import load_pending_turn_payload as load_dialogue_pending_turn_payload
from src.web.manifest import (
    build_file_urls,
    discover_artifacts,
    ensure_run_exists,
    file_url,
    load_json_file,
    load_manifest,
    manifest_path,
    reconcile_loaded_manifest,
    relative_to_run_dir,
    require_manifest,
    serialize_manifest,
)
from src.web.pipeline import assert_run_not_stopped, build_progress_chunking_from_artifacts, build_summary_chunking
from src.web.run_ops import finalize_manifest_timing, format_elapsed_text, is_stop_requested


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class CoreServiceMixin:
    def _serialize_manifest(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id", "")).strip()
        file_urls = self._build_file_urls(run_id, payload) if run_id else {}
        return serialize_manifest(payload, run_id=run_id, file_urls=file_urls)

    def _discover_artifacts(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return discover_artifacts(
            manifest,
            discover_character_cards=discover_character_cards,
            discover_relation_graph=discover_relation_graph,
            build_progress_chunking_from_artifacts=build_progress_chunking_from_artifacts,
            build_summary_chunking=build_summary_chunking,
        )

    @staticmethod
    def _format_elapsed_text(seconds: float) -> str:
        return format_elapsed_text(seconds)

    def _finalize_manifest_timing(self, manifest: dict[str, Any], *, outcome: str) -> None:
        finalize_manifest_timing(manifest, outcome=outcome, now_text=_utc_now())

    def _is_stop_requested(self, manifest_path: Path) -> bool:
        return is_stop_requested(manifest_path, load_manifest=self._load_manifest)

    def _assert_run_not_stopped(
        self,
        manifest_path: Path,
        *,
        message: str = "这次蒸馏已停止。",
        current_character: str = "",
    ) -> None:
        assert_run_not_stopped(
            manifest_path,
            message=message,
            current_character=current_character,
            load_manifest=self._load_manifest,
            write_json=self._write_json,
            utc_now=_utc_now,
            is_stop_requested=self._is_stop_requested,
            stopped_error_type=self.STOPPED_ERROR_TYPE,
        )

    def _build_file_urls(self, run_id: str, manifest: dict[str, Any]) -> dict[str, str]:
        current_manifest_path = self._manifest_path(run_id)
        run_dir = self.runs_root / run_id
        return build_file_urls(
            run_id=run_id,
            manifest=manifest,
            manifest_path=current_manifest_path,
            run_dir=run_dir,
        )

    def _file_url(self, run_id: str, relative_path: Path) -> str:
        return file_url(run_id, relative_path)

    @staticmethod
    def _relative_to_run_dir(path: Path, run_dir: Path) -> Path | None:
        return relative_to_run_dir(path, run_dir)

    def _manifest_path(self, run_id: str) -> Path:
        return manifest_path(self.runs_root, run_id)

    def _require_manifest(self, run_id: str) -> dict[str, Any]:
        return require_manifest(run_id, loader=self._load_manifest, runs_root=self.runs_root)

    def _ensure_run_exists(self, run_id: str) -> None:
        ensure_run_exists(self.runs_root, run_id)

    def _load_manifest(self, current_manifest_path: Path) -> dict[str, Any] | None:
        return load_manifest(
            current_manifest_path,
            reconcile=self._reconcile_loaded_manifest,
            writer=self._write_json,
        )

    def _reconcile_loaded_manifest(
        self,
        current_manifest_path: Path,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        return reconcile_loaded_manifest(
            current_manifest_path,
            payload,
            is_thread_alive=lambda run_id: bool((thread := self._active_run_threads.get(run_id)) and thread.is_alive()),
            utc_now=_utc_now,
            finalize_manifest_timing=lambda manifest, outcome: self._finalize_manifest_timing(manifest, outcome=outcome),
        )

    def _load_model_settings_payload(self) -> dict[str, Any]:
        return self._load_json_file(self.settings_path) or {}

    def _load_pending_turn_payload(self, run_id: str, session_id: str) -> dict[str, Any]:
        return load_dialogue_pending_turn_payload(
            runs_root=self.runs_root,
            run_id=run_id,
            session_id=session_id,
            load_json_file=self._load_json_file,
        )

    @staticmethod
    def _load_json_file(path: Path) -> dict[str, Any] | None:
        return load_json_file(path)
