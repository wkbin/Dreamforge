from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.core.config import Config
from src.web.manifest import write_json_file
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

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        write_json_file(path, payload)

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
