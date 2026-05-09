from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.skill_support.prompt_payloads import build_distill_prompt_payload, build_relation_prompt_payload
from src.utils.file_utils import safe_filename
from src.web.pipeline import (
    build_progress_chunking_from_artifacts,
    build_quality_snapshot,
    build_summary_chunking,
    chunk_overview_from_payload,
    stage_presence,
)
from src.web.run_ops import (
    apply_manual_payload_manifest_state,
    apply_restart_manifest_state,
    attach_workspace_roots,
    build_initial_run_manifest,
    build_novel_source_entry,
    classify_requested_characters,
    ensure_run_workspace,
    prepare_restart_novel_source,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RunPreparationMixin:
    def _build_quality_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return build_quality_snapshot(
            **kwargs,
            normalize_characters=self._normalize_characters,
        )

    def _build_novel_source_entry(
        self,
        source_path: Path,
        *,
        source_name: str,
        kind: str,
        raw_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        return build_novel_source_entry(
            source_path,
            source_name=source_name,
            kind=kind,
            raw_bytes=raw_bytes,
            utc_now=_utc_now,
        )

    def _prepare_create_run(
        self,
        *,
        novel_name: str,
        novel_content_base64: str,
        characters: list[str],
    ) -> dict[str, Any]:
        locked_characters = self._normalize_characters(characters)
        if not locked_characters:
            raise ValueError("At least one character is required.")

        file_name = safe_filename(novel_name or "novel.txt")
        raw_bytes = self._decode_base64(novel_content_base64)
        if not raw_bytes:
            raise ValueError("Novel content is empty.")

        run_id = self._new_run_id()
        run_dir = self.runs_root / run_id
        workspace = ensure_run_workspace(run_dir)
        payload_dir = workspace["payload_dir"]
        artifact_dir = workspace["artifact_dir"]

        novel_path = workspace["input_dir"] / file_name
        novel_path.write_bytes(raw_bytes)
        novel_id = Path(file_name).stem.strip() or run_id

        manifest = build_initial_run_manifest(
            run_id=run_id,
            novel_id=novel_id,
            novel_path=novel_path,
            novel_source_entry=self._build_novel_source_entry(
                novel_path,
                source_name=file_name,
                kind="initial",
                raw_bytes=raw_bytes,
            ),
            model_settings=self.get_model_settings(),
            locked_characters=locked_characters,
            workspace=workspace,
            utc_now=_utc_now,
        )

        manifest_path = self._manifest_path(run_id)
        self._write_json(manifest_path, manifest)

        characters_root = artifact_dir / "characters" / novel_id
        attach_workspace_roots(
            manifest,
            characters_root=characters_root,
            relations_root=artifact_dir / "relations",
        )
        return {
            "artifact_dir": artifact_dir,
            "characters_root": characters_root,
            "locked_characters": locked_characters,
            "manifest": manifest,
            "manifest_path": manifest_path,
            "novel_path": novel_path,
            "payload_dir": payload_dir,
        }

    def _prepare_manual_run_manifest(
        self,
        *,
        manifest: dict[str, Any],
        manifest_path: Path,
        novel_path: Path,
        payload_dir: Path,
        characters_root: Path,
        locked_characters: list[str],
        max_sentences: int,
        max_chars: int,
    ) -> dict[str, Any]:
        distill_payload = build_distill_prompt_payload(
            novel_path,
            characters=locked_characters,
            max_sentences=max_sentences,
            max_chars=max_chars,
            characters_root=characters_root,
            manifest_path=manifest_path,
            update_mode="auto",
        )
        relation_payload = build_relation_prompt_payload(
            novel_path,
            max_sentences=min(max_sentences, 80),
            max_chars=min(max_chars, 12_000),
        )

        distill_payload_path = payload_dir / "distill_payload.json"
        relation_payload_path = payload_dir / "relation_payload.json"
        self._write_json(distill_payload_path, distill_payload)
        self._write_json(relation_payload_path, relation_payload)

        return apply_manual_payload_manifest_state(
            manifest,
            distill_payload=distill_payload,
            relation_payload=relation_payload,
            distill_payload_path=distill_payload_path,
            relation_payload_path=relation_payload_path,
            locked_characters=locked_characters,
            chunk_overview_from_payload=chunk_overview_from_payload,
            build_progress_chunking_from_artifacts=build_progress_chunking_from_artifacts,
            build_summary_chunking=build_summary_chunking,
            build_quality_snapshot=self._build_quality_snapshot,
            stage_presence=stage_presence,
            utc_now=_utc_now,
        )

    def _prepare_restart_run(
        self,
        run_id: str,
        *,
        characters: list[str],
        novel_name: str,
        novel_content_base64: str,
    ) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)

        locked_characters = self._normalize_characters(characters) or list(manifest.get("locked_characters", []))
        if not locked_characters:
            raise ValueError("At least one character is required.")

        character_plan = classify_requested_characters(
            manifest,
            locked_characters=locked_characters,
            normalize_characters=self._normalize_characters,
        )
        existing_requested = character_plan["existing_requested"]
        new_requested = character_plan["new_requested"]
        relation_characters = character_plan["relation_characters"]

        source_update = prepare_restart_novel_source(
            runs_root=self.runs_root,
            run_id=run_id,
            manifest=manifest,
            novel_name=novel_name,
            novel_content_base64=novel_content_base64,
            decode_base64=self._decode_base64,
            utc_now=_utc_now,
        )
        using_new_source = bool(source_update["using_new_source"])
        novel_path = source_update["novel_path"]
        raw_bytes = source_update["raw_bytes"]
        resume_completed_characters: list[str] = []
        pending_characters = list(locked_characters)
        if using_new_source:
            redistill_summary = f"继续蒸馏：新增 {len(new_requested)} 人，增量 {len(existing_requested)} 人"
        elif pending_characters:
            redistill_summary = f"继续蒸馏：重新整理 {len(pending_characters)} 人"
        else:
            redistill_summary = "继续蒸馏：人物档案已完成，准备继续关系图谱"
        novel_source_entry = None
        if using_new_source and raw_bytes is not None:
            novel_source_entry = self._build_novel_source_entry(
                novel_path,
                source_name=Path(novel_path).name,
                kind="incremental_update",
                raw_bytes=raw_bytes,
            )

        manifest = apply_restart_manifest_state(
            manifest,
            locked_characters=locked_characters,
            novel_path=novel_path,
            using_new_source=using_new_source,
            new_requested=new_requested,
            existing_requested=existing_requested,
            pending_characters=pending_characters,
            resume_completed_characters=resume_completed_characters,
            relation_characters=relation_characters,
            redistill_summary=redistill_summary,
            novel_source_entry=novel_source_entry,
            utc_now=_utc_now,
        )
        return {
            "locked_characters": locked_characters,
            "manifest": manifest,
            "manifest_path": manifest_path,
            "novel_path": novel_path,
            "relation_characters": relation_characters,
        }
