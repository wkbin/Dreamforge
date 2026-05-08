from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.web.run_ops import (
    build_model_settings_response,
    delete_run_group,
    is_model_configured_payload,
    list_recent_sessions,
    list_runs,
    normalize_model_settings,
    refresh_run_manifest,
    stop_run_manifest,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RunServiceMixin:
    def get_model_settings(self) -> dict[str, Any]:
        payload = self._load_model_settings_payload()
        return build_model_settings_response(
            payload,
            configured=self._is_model_configured_payload(payload),
        )

    def save_model_settings(
        self,
        *,
        provider: str,
        model: str,
        base_url: str = "",
        api_key: str = "",
        max_tokens: int = 0,
    ) -> dict[str, Any]:
        normalized = normalize_model_settings(
            existing=self._load_model_settings_payload(),
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            max_tokens=max_tokens,
            utc_now=_utc_now,
        )
        self._write_json(self.settings_path, normalized)
        return self.get_model_settings()

    def model_is_configured(self) -> bool:
        return is_model_configured_payload(self._load_model_settings_payload())

    def list_runs(self) -> list[dict[str, Any]]:
        return list_runs(
            runs_root=self.runs_root,
            load_manifest=self._load_manifest,
            serialize_manifest=self._serialize_manifest,
        )

    def list_recent_sessions(self) -> list[dict[str, Any]]:
        return list_recent_sessions(
            runs_root=self.runs_root,
            load_manifest=self._load_manifest,
            list_sessions=self.dialogue.list_sessions,
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        payload = self._load_manifest(manifest_path)
        if not payload:
            raise FileNotFoundError(run_id)
        return self._serialize_manifest(payload)

    def refresh_run(self, run_id: str) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)
        refreshed = refresh_run_manifest(
            manifest,
            discover_artifacts=self._discover_artifacts,
            utc_now=_utc_now,
        )
        self._write_json(manifest_path, refreshed)
        return self._serialize_manifest(refreshed)

    def stop_run(self, run_id: str) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)
        manifest = stop_run_manifest(manifest, utc_now=_utc_now)
        self._write_json(manifest_path, manifest)
        return self._serialize_manifest(manifest)

    def delete_run_group(self, run_id: str) -> dict[str, Any]:
        return delete_run_group(
            run_id=run_id,
            runs_root=self.runs_root,
            require_manifest=self._require_manifest,
            load_manifest=self._load_manifest,
        )

    def create_run(
        self,
        *,
        novel_name: str,
        novel_content_base64: str,
        characters: list[str],
        max_sentences: int = 120,
        max_chars: int = 50_000,
        auto_run: bool = False,
    ) -> dict[str, Any]:
        if not self.model_is_configured():
            raise ValueError("Model is not configured yet.")
        prepared = self._prepare_create_run(
            novel_name=novel_name,
            novel_content_base64=novel_content_base64,
            characters=characters,
        )
        locked_characters = prepared["locked_characters"]
        manifest = prepared["manifest"]
        manifest_path = prepared["manifest_path"]
        novel_path = prepared["novel_path"]

        if auto_run:
            self._write_json(manifest_path, manifest)
            self._start_background_run(
                manifest_path=manifest_path,
                novel_path=novel_path,
                locked_characters=locked_characters,
                max_sentences=max_sentences,
                max_chars=max_chars,
            )
            return self._serialize_manifest(self._load_manifest(manifest_path) or manifest)

        manifest = self._prepare_manual_run_manifest(
            manifest=manifest,
            manifest_path=manifest_path,
            novel_path=novel_path,
            payload_dir=prepared["payload_dir"],
            characters_root=prepared["characters_root"],
            locked_characters=locked_characters,
            max_sentences=max_sentences,
            max_chars=max_chars,
        )
        self._write_json(manifest_path, manifest)
        return self._serialize_manifest(manifest)

    def restart_run_distill(
        self,
        run_id: str,
        *,
        characters: list[str],
        novel_name: str = "",
        novel_content_base64: str = "",
        max_sentences: int = 120,
        max_chars: int = 50_000,
    ) -> dict[str, Any]:
        if not self.model_is_configured():
            raise ValueError("Model is not configured yet.")
        prepared = self._prepare_restart_run(
            run_id,
            characters=characters,
            novel_name=novel_name,
            novel_content_base64=novel_content_base64,
        )
        manifest = prepared["manifest"]
        manifest_path = prepared["manifest_path"]
        novel_path = prepared["novel_path"]
        locked_characters = prepared["locked_characters"]
        relation_characters = prepared["relation_characters"]
        self._write_json(manifest_path, manifest)
        self._start_background_run(
            manifest_path=manifest_path,
            novel_path=novel_path,
            locked_characters=locked_characters,
            relation_characters=relation_characters,
            max_sentences=max_sentences,
            max_chars=max_chars,
        )
        return self._serialize_manifest(self._load_manifest(manifest_path) or manifest)
