from __future__ import annotations

from pathlib import Path
from typing import Any

from src.web.artifacts import export_relations_source, load_relations_source, materialize_profile_source
from src.web.pipeline import (
    apply_distill_progress,
    apply_relation_progress,
    build_quality_snapshot,
    finalize_workflow_failed,
    finalize_workflow_success_without_graph,
    finalize_workflow_stopped,
    finalize_workflow_success,
    process_distill_character,
    process_relation_graph,
    stage_presence,
    update_manifest_chunk_progress,
)


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AutomaticPipelineMixin:
    def _run_automatic_pipeline(
        self,
        *,
        manifest_path: Path,
        novel_path: Path,
        locked_characters: list[str],
        relation_characters: list[str] | None = None,
        max_sentences: int,
        max_chars: int,
        run_id: str = "",
    ) -> dict[str, Any]:
        manifest = self._load_manifest(manifest_path) or {}
        run_dir = manifest_path.parent
        novel_id = str(manifest.get("novel_id", "")).strip() or run_dir.name
        config = self._build_runtime_config_for_run(run_dir=run_dir)
        parts = self._build_runtime_parts(config)
        pending_characters = list(locked_characters)
        graph_cast = self._normalize_characters(relation_characters or locked_characters)
        stopped_error_type = self.STOPPED_ERROR_TYPE

        def on_distill(stage: str, payload: dict[str, Any]) -> None:
            current = self._load_manifest(manifest_path) or manifest
            apply_distill_progress(
                current,
                stage=stage,
                payload=payload,
                utc_now=_utc_now,
                update_manifest_chunk_progress=update_manifest_chunk_progress,
            )
            self._write_json(manifest_path, current)

        def on_relation(stage: str, payload: dict[str, Any]) -> None:
            current = self._load_manifest(manifest_path) or manifest
            apply_relation_progress(
                current,
                stage=stage,
                payload=payload,
                utc_now=_utc_now,
                update_manifest_chunk_progress=update_manifest_chunk_progress,
            )
            self._write_json(manifest_path, current)

        try:
            if not hasattr(parts.llm, "chat_completion"):
                raise ValueError("Configured model does not support distill generation.")

            characters_root = parts.path_provider.characters_root(novel_id)
            payload_dir = run_dir / "payloads"
            host_output_root = run_dir / "host_output" / novel_id
            host_output_root.mkdir(parents=True, exist_ok=True)
            payload_dir.mkdir(parents=True, exist_ok=True)

            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止。")
            on_distill("text_loaded", {"source_path": str(novel_path.resolve())})
            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止。")
            on_distill("characters_ready", {"total": len(pending_characters), "characters": pending_characters})

            distill_payload_paths: dict[str, str] = {}
            character_dirs: dict[str, str] = dict(manifest.get("artifacts", {}).get("character_dirs", {}) or {})
            distill_chunk_by_character: dict[str, Any] = {}
            quality_focus: dict[str, Any] = {}
            quality_matched: set[str] = set()
            quality_missing: set[str] = set()
            quality_stage_presence: set[str] = set()
            profile_repair_characters: list[str] = []
            for character in pending_characters:
                process_distill_character(
                    character=character,
                    locked_characters=locked_characters,
                    novel_path=novel_path,
                    characters_root=characters_root,
                    manifest_path=manifest_path,
                    payload_dir=payload_dir,
                    host_output_root=host_output_root,
                    run_dir=run_dir,
                    novel_id=novel_id,
                    parts=parts,
                    config=config,
                    manifest_seed=manifest,
                    max_sentences=max_sentences,
                    max_chars=max_chars,
                    on_distill=on_distill,
                    assert_run_not_stopped=self._assert_run_not_stopped,
                    write_json=self._write_json,
                    load_manifest=self._load_manifest,
                    generate_character_profile_markdown=self._generate_character_profile_markdown,
                    maybe_repair_generated_profile=self._maybe_repair_generated_profile,
                    finalize_generated_profile_source=self._finalize_generated_profile_source,
                    materialize_profile_source=materialize_profile_source,
                    update_manifest_chunk_progress=update_manifest_chunk_progress,
                    build_quality_snapshot=self._build_quality_snapshot,
                    utc_now=_utc_now,
                    stage_presence=stage_presence,
                    relation_repairs_getter=lambda current: (current.get("quality", {}) or {}).get("relation_repairs", {}),
                    aggregates={
                        "distill_payload_paths": distill_payload_paths,
                        "character_dirs": character_dirs,
                        "distill_chunk_by_character": distill_chunk_by_character,
                        "quality_focus": quality_focus,
                        "quality_matched": quality_matched,
                        "quality_missing": quality_missing,
                        "quality_stage_presence": quality_stage_presence,
                        "profile_repair_characters": profile_repair_characters,
                    },
                )

            refreshed = self._discover_artifacts(self._load_manifest(manifest_path) or manifest)
            try:
                process_relation_graph(
                    novel_path=novel_path,
                    graph_cast=graph_cast,
                    max_sentences=max_sentences,
                    max_chars=max_chars,
                    manifest_path=manifest_path,
                    manifest_seed=manifest,
                    payload_dir=payload_dir,
                    novel_id=novel_id,
                    parts=parts,
                    config=config,
                    on_relation=on_relation,
                    assert_run_not_stopped=self._assert_run_not_stopped,
                    write_json=self._write_json,
                    load_manifest=self._load_manifest,
                    build_quality_snapshot=self._build_quality_snapshot,
                    update_manifest_chunk_progress=update_manifest_chunk_progress,
                    generate_relation_markdown=self._generate_relation_markdown,
                    maybe_repair_generated_relations=self._maybe_repair_generated_relations,
                    load_relations_source=load_relations_source,
                    export_relations_source=export_relations_source,
                    utc_now=_utc_now,
                    relation_repairs_state=(manifest.get("quality", {}) or {}).get("relation_repairs", {}),
                    quality_matched=quality_matched,
                    quality_missing=quality_missing,
                    quality_focus=quality_focus,
                    profile_repair_characters=profile_repair_characters,
                )
                refreshed = self._discover_artifacts(self._load_manifest(manifest_path) or manifest)
                finalize_workflow_success(
                    refreshed,
                    utc_now=_utc_now,
                    finalize_manifest_timing=lambda target, outcome: self._finalize_manifest_timing(target, outcome=outcome),
                )
            except stopped_error_type:
                raise
            except Exception as relation_exc:
                refreshed = self._discover_artifacts(self._load_manifest(manifest_path) or manifest)
                finalize_workflow_success_without_graph(
                    refreshed,
                    graph_error=str(relation_exc),
                    utc_now=_utc_now,
                    finalize_manifest_timing=lambda target, outcome: self._finalize_manifest_timing(target, outcome=outcome),
                )
            self._write_json(manifest_path, refreshed)
            return self._serialize_manifest(refreshed)
        except stopped_error_type as exc:
            stopped = self._load_manifest(manifest_path) or manifest
            finalize_workflow_stopped(
                stopped,
                message=str(exc),
                utc_now=_utc_now,
                finalize_manifest_timing=lambda target, outcome: self._finalize_manifest_timing(target, outcome=outcome),
            )
            self._write_json(manifest_path, stopped)
            return self._serialize_manifest(stopped)
        except Exception as exc:
            failed = self._load_manifest(manifest_path) or manifest
            finalize_workflow_failed(
                failed,
                message=str(exc),
                utc_now=_utc_now,
                finalize_manifest_timing=lambda target, outcome: self._finalize_manifest_timing(target, outcome=outcome),
            )
            self._write_json(manifest_path, failed)
            raise
