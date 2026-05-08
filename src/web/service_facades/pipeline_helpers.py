from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.core.config import Config
from src.utils.text_parser import split_sentences
from src.web.artifacts import load_profile_source, load_relations_source, render_profile_md
from src.web.pipeline import (
    build_distill_chunk_payloads,
    build_relation_chunk_payloads,
    chunk_parallel_workers,
    generate_character_profile_markdown,
    generate_character_profile_markdown_chunked,
    generate_relation_markdown,
    generate_relation_markdown_chunked,
    run_distill_chunk_drafts,
    run_relation_chunk_drafts,
    should_use_chunking,
    split_text_into_chunks,
)
from src.web.prompts import (
    build_chunk_distill_guidance,
    build_dialogue_style_guidance,
    build_distill_priority_guidance,
    build_excerpt_stage_guidance,
    build_relation_chunk_guidance,
    compose_distill_completion_messages,
    compose_distill_llm_messages,
    compose_distill_merge_messages,
    compose_distill_repair_messages,
    compose_relation_llm_messages,
    compose_relation_merge_messages,
    compose_relation_repair_messages,
)
from src.web.review import (
    collect_profile_completion_groups,
    collect_profile_repair_targets,
    maybe_repair_generated_profile,
    maybe_repair_generated_relations,
    profile_field_is_effectively_empty,
)


class PipelineHelpersMixin:
    @staticmethod
    def _sanitize_markdown_output(content: str) -> str:
        text = str(content or "").strip()
        if not text:
            return ""
        fenced = re.search(r"```(?:markdown|md)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return text

    def _llm_cap(self, config: Config, key: str, fallback: int) -> int:
        configured = int(config.get(key, 0) or 0)
        if configured > 0:
            return min(configured, fallback)
        return fallback

    def _generate_character_profile_markdown(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        payload: dict[str, Any],
        character: str,
        peer_characters: list[str],
        progress_hook: Any | None = None,
    ) -> tuple[str, dict[str, Any]]:
        return generate_character_profile_markdown(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            payload=payload,
            character=character,
            peer_characters=peer_characters,
            progress_hook=progress_hook,
            assert_run_not_stopped=self._assert_run_not_stopped,
            should_use_chunked_distill=self._should_use_chunked_distill,
            generate_character_profile_markdown_chunked=self._generate_character_profile_markdown_chunked,
            build_distill_llm_messages=self._build_distill_llm_messages,
            sanitize_markdown_output=self._sanitize_markdown_output,
            llm_cap=self._llm_cap,
            distill_single_max_tokens=self.DISTILL_SINGLE_MAX_TOKENS,
        )

    def _generate_character_profile_markdown_chunked(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        payload: dict[str, Any],
        character: str,
        peer_characters: list[str],
        progress_hook: Any | None = None,
        fallback_reason: str = "",
    ) -> tuple[str, dict[str, Any]]:
        return generate_character_profile_markdown_chunked(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            payload=payload,
            character=character,
            peer_characters=peer_characters,
            progress_hook=progress_hook,
            fallback_reason=fallback_reason,
            build_distill_chunk_payloads=self._build_distill_chunk_payloads,
            assert_run_not_stopped=self._assert_run_not_stopped,
            build_distill_llm_messages=self._build_distill_llm_messages,
            sanitize_markdown_output=self._sanitize_markdown_output,
            llm_cap=self._llm_cap,
            distill_single_max_tokens=self.DISTILL_SINGLE_MAX_TOKENS,
            chunk_parallel_workers=self._chunk_parallel_workers,
            run_distill_chunk_drafts=self._run_distill_chunk_drafts,
            build_distill_merge_messages=self._build_distill_merge_messages,
            distill_merge_max_tokens=self.DISTILL_MERGE_MAX_TOKENS,
        )

    def _generate_relation_markdown(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        payload: dict[str, Any],
        characters: list[str],
        progress_hook: Any | None = None,
    ) -> tuple[str, dict[str, Any]]:
        return generate_relation_markdown(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            payload=payload,
            characters=characters,
            progress_hook=progress_hook,
            assert_run_not_stopped=self._assert_run_not_stopped,
            should_use_chunked_relation=self._should_use_chunked_relation,
            generate_relation_markdown_chunked=self._generate_relation_markdown_chunked,
            build_relation_llm_messages=self._build_relation_llm_messages,
            sanitize_markdown_output=self._sanitize_markdown_output,
            llm_cap=self._llm_cap,
            relation_single_max_tokens=self.RELATION_SINGLE_MAX_TOKENS,
        )

    def _generate_relation_markdown_chunked(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        payload: dict[str, Any],
        characters: list[str],
        progress_hook: Any | None = None,
        fallback_reason: str = "",
    ) -> tuple[str, dict[str, Any]]:
        return generate_relation_markdown_chunked(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            payload=payload,
            characters=characters,
            progress_hook=progress_hook,
            fallback_reason=fallback_reason,
            build_relation_chunk_payloads=self._build_relation_chunk_payloads,
            assert_run_not_stopped=self._assert_run_not_stopped,
            build_relation_llm_messages=self._build_relation_llm_messages,
            sanitize_markdown_output=self._sanitize_markdown_output,
            llm_cap=self._llm_cap,
            relation_single_max_tokens=self.RELATION_SINGLE_MAX_TOKENS,
            chunk_parallel_workers=self._chunk_parallel_workers,
            run_relation_chunk_drafts=self._run_relation_chunk_drafts,
            build_relation_merge_messages=self._build_relation_merge_messages,
            relation_merge_max_tokens=self.RELATION_MERGE_MAX_TOKENS,
        )

    def _build_distill_llm_messages(
        self,
        payload: dict[str, Any],
        *,
        character: str,
        peer_characters: list[str] | None = None,
        chunk_label: str = "",
        chunk_index: int = 0,
        chunk_total: int = 0,
        chunk_mode: str = "",
    ) -> list[dict[str, str]]:
        return compose_distill_llm_messages(
            payload,
            character=character,
            peer_characters=peer_characters,
            normalize_characters=self._normalize_characters,
            build_excerpt_stage_guidance=self._build_excerpt_stage_guidance,
            build_dialogue_style_guidance=self._build_dialogue_style_guidance,
            build_distill_priority_guidance=self._build_distill_priority_guidance,
            build_chunk_distill_guidance=self._build_chunk_distill_guidance,
            chunk_label=chunk_label,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chunk_mode=chunk_mode,
        )

    def _build_distill_merge_messages(
        self,
        payload: dict[str, Any],
        *,
        character: str,
        peer_characters: list[str] | None,
        chunk_drafts: list[dict[str, str]],
        fallback_reason: str = "",
    ) -> list[dict[str, str]]:
        return compose_distill_merge_messages(
            payload,
            character=character,
            peer_characters=peer_characters,
            chunk_drafts=chunk_drafts,
            fallback_reason=fallback_reason,
            normalize_characters=self._normalize_characters,
            build_excerpt_stage_guidance=self._build_excerpt_stage_guidance,
            build_dialogue_style_guidance=self._build_dialogue_style_guidance,
            build_distill_priority_guidance=self._build_distill_priority_guidance,
        )

    def _build_distill_chunk_payloads(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return build_distill_chunk_payloads(payload, chunk_excerpt_text=self._chunk_excerpt_text)

    def _chunk_parallel_workers(self, *, config: Config, chunk_total: int) -> int:
        return chunk_parallel_workers(config=config, chunk_total=chunk_total)

    def _run_distill_chunk_drafts(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        chunk_entries: list[dict[str, Any]],
        character: str,
        peer_characters: list[str],
        progress_hook: Any | None,
        workers: int,
    ) -> list[dict[str, str]]:
        return run_distill_chunk_drafts(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            chunk_entries=chunk_entries,
            character=character,
            peer_characters=peer_characters,
            progress_hook=progress_hook,
            workers=workers,
            assert_not_stopped=self._assert_run_not_stopped,
            build_distill_llm_messages=self._build_distill_llm_messages,
            chat_completion=lambda messages, temperature, max_tokens: parts.llm.chat_completion(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            sanitize_markdown_output=self._sanitize_markdown_output,
            llm_cap=self._llm_cap,
            chunk_max_tokens=self.DISTILL_CHUNK_MAX_TOKENS,
            stopped_error_type=self.STOPPED_ERROR_TYPE,
        )

    def _run_relation_chunk_drafts(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        chunk_entries: list[dict[str, Any]],
        characters: list[str],
        progress_hook: Any | None,
        workers: int,
    ) -> list[dict[str, str]]:
        return run_relation_chunk_drafts(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            chunk_entries=chunk_entries,
            characters=characters,
            progress_hook=progress_hook,
            workers=workers,
            assert_not_stopped=self._assert_run_not_stopped,
            build_relation_llm_messages=self._build_relation_llm_messages,
            chat_completion=lambda messages, temperature, max_tokens: parts.llm.chat_completion(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            sanitize_markdown_output=self._sanitize_markdown_output,
            llm_cap=self._llm_cap,
            chunk_max_tokens=self.RELATION_CHUNK_MAX_TOKENS,
            stopped_error_type=self.STOPPED_ERROR_TYPE,
        )

    def _should_use_chunked_distill(self, payload: dict[str, Any]) -> bool:
        request = dict(payload.get("request", {}) or {})
        return should_use_chunking(
            str(request.get("excerpt", "")).strip(),
            trigger_chars=self.DISTILL_CHUNK_TRIGGER_CHARS,
            trigger_sentences=self.DISTILL_CHUNK_TRIGGER_SENTENCES,
            sentence_splitter=split_sentences,
        )

    def _chunk_excerpt_text(self, text: str) -> list[str]:
        return split_text_into_chunks(
            text,
            max_chars=self.DISTILL_CHUNK_MAX_CHARS,
            max_sentences=self.DISTILL_CHUNK_MAX_SENTENCES,
            sentence_splitter=split_sentences,
        )

    @staticmethod
    def _build_chunk_distill_guidance(
        *,
        chunk_label: str = "",
        chunk_index: int = 0,
        chunk_total: int = 0,
        chunk_mode: str = "",
    ) -> str:
        return build_chunk_distill_guidance(
            chunk_label=chunk_label,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chunk_mode=chunk_mode,
        )

    def _maybe_repair_generated_relations(
        self,
        *,
        parts: Any,
        config: Config,
        payload: dict[str, Any],
        characters: list[str],
        relations_file: Path,
        relation_markdown: str,
    ) -> str | None:
        return maybe_repair_generated_relations(
            parts=parts,
            config=config,
            payload=payload,
            characters=characters,
            relations_file=relations_file,
            relation_markdown=relation_markdown,
            load_relations_source=load_relations_source,
            collect_relation_repair_issues=self._collect_relation_repair_issues,
            build_relation_repair_messages=self._build_relation_repair_messages,
            sanitize_markdown_output=self._sanitize_markdown_output,
            llm_cap=self._llm_cap,
            relation_repair_max_tokens=self.RELATION_REPAIR_MAX_TOKENS,
        )

    def _build_relation_repair_messages(
        self,
        payload: dict[str, Any],
        *,
        characters: list[str],
        relation_markdown: str,
        issues: list[str],
    ) -> list[dict[str, str]]:
        return compose_relation_repair_messages(
            payload,
            characters=characters,
            relation_markdown=relation_markdown,
            issues=issues,
            build_relation_llm_messages_fn=self._build_relation_llm_messages,
        )

    def _maybe_repair_generated_profile(
        self,
        *,
        parts: Any,
        config: Config,
        payload: dict[str, Any],
        character: str,
        peer_characters: list[str],
        source_path: Path,
    ) -> str | None:
        return maybe_repair_generated_profile(
            parts=parts,
            config=config,
            payload=payload,
            character=character,
            peer_characters=peer_characters,
            source_path=source_path,
            load_profile_source=load_profile_source,
            extract_dialogue_evidence=self._extract_dialogue_evidence,
            collect_profile_repair_targets=self._collect_profile_repair_targets,
            collect_profile_completion_groups=self._collect_profile_completion_groups,
            build_distill_repair_messages=self._build_distill_repair_messages,
            build_distill_completion_messages=self._build_distill_completion_messages,
            sanitize_markdown_output=self._sanitize_markdown_output,
            merge_profile_patch=self._merge_profile_patch,
            apply_profile_missing_fallbacks=self._apply_profile_missing_fallbacks,
            render_profile_md=render_profile_md,
            llm_cap=self._llm_cap,
            profile_completion_group_limit=self.PROFILE_COMPLETION_GROUP_LIMIT,
            profile_repair_max_tokens=self.PROFILE_REPAIR_MAX_TOKENS,
            profile_completion_max_tokens=self.PROFILE_COMPLETION_MAX_TOKENS,
        )

    def _collect_profile_repair_targets(
        self,
        profile: dict[str, Any],
        *,
        dialogue_evidence: list[str] | None = None,
    ) -> dict[str, str]:
        return collect_profile_repair_targets(
            profile,
            rewrite_fields=self.PROFILE_REWRITE_FIELDS,
            dialogue_evidence=dialogue_evidence,
        )

    def _collect_profile_completion_groups(
        self,
        profile: dict[str, Any],
        *,
        repair_targets: dict[str, str] | None = None,
    ) -> list[tuple[str, tuple[str, ...], dict[str, str]]]:
        return collect_profile_completion_groups(
            profile,
            completion_groups=self.PROFILE_COMPLETION_GROUPS,
            repair_targets=repair_targets,
        )

    def _profile_field_is_effectively_empty(self, profile: dict[str, Any], field: str) -> bool:
        return profile_field_is_effectively_empty(profile, field)

    def _build_distill_repair_messages(
        self,
        payload: dict[str, Any],
        *,
        character: str,
        peer_characters: list[str],
        profile: dict[str, Any],
        group_name: str,
        fields: tuple[str, ...],
        repair_targets: dict[str, str],
        dialogue_evidence: list[str] | None = None,
    ) -> list[dict[str, str]]:
        return compose_distill_repair_messages(
            payload,
            character=character,
            peer_characters=peer_characters,
            profile=profile,
            group_name=group_name,
            fields=fields,
            repair_targets=repair_targets,
            dialogue_evidence=dialogue_evidence,
            build_distill_llm_messages_fn=self._build_distill_llm_messages,
            render_profile_md=render_profile_md,
        )

    def _build_distill_completion_messages(
        self,
        payload: dict[str, Any],
        *,
        character: str,
        peer_characters: list[str],
        profile: dict[str, Any],
        group_name: str,
        fields: tuple[str, ...],
        dialogue_evidence: list[str] | None = None,
    ) -> list[dict[str, str]]:
        return compose_distill_completion_messages(
            payload,
            character=character,
            peer_characters=peer_characters,
            profile=profile,
            group_name=group_name,
            fields=fields,
            dialogue_evidence=dialogue_evidence,
            build_distill_llm_messages_fn=self._build_distill_llm_messages,
            render_profile_md=render_profile_md,
        )

    def _build_relation_llm_messages(
        self,
        payload: dict[str, Any],
        *,
        characters: list[str],
        chunk_label: str = "",
        chunk_index: int = 0,
        chunk_total: int = 0,
        chunk_mode: str = "",
    ) -> list[dict[str, str]]:
        return compose_relation_llm_messages(
            payload,
            characters=characters,
            normalize_characters=self._normalize_characters,
            build_relation_chunk_guidance=self._build_relation_chunk_guidance,
            chunk_label=chunk_label,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chunk_mode=chunk_mode,
        )

    def _build_relation_merge_messages(
        self,
        payload: dict[str, Any],
        *,
        characters: list[str],
        chunk_drafts: list[dict[str, str]],
        fallback_reason: str = "",
    ) -> list[dict[str, str]]:
        return compose_relation_merge_messages(
            payload,
            characters=characters,
            chunk_drafts=chunk_drafts,
            fallback_reason=fallback_reason,
            normalize_characters=self._normalize_characters,
        )

    def _build_relation_chunk_payloads(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return build_relation_chunk_payloads(payload, chunk_relation_text=self._chunk_relation_text)

    def _should_use_chunked_relation(self, payload: dict[str, Any]) -> bool:
        request = dict(payload.get("request", {}) or {})
        return should_use_chunking(
            str(request.get("excerpt", "")).strip(),
            trigger_chars=self.RELATION_CHUNK_TRIGGER_CHARS,
            trigger_sentences=self.RELATION_CHUNK_TRIGGER_SENTENCES,
            sentence_splitter=split_sentences,
        )

    def _chunk_relation_text(self, text: str) -> list[str]:
        return split_text_into_chunks(
            text,
            max_chars=self.RELATION_CHUNK_MAX_CHARS,
            max_sentences=self.RELATION_CHUNK_MAX_SENTENCES,
            sentence_splitter=split_sentences,
        )

    @staticmethod
    def _build_relation_chunk_guidance(
        *,
        chunk_label: str = "",
        chunk_index: int = 0,
        chunk_total: int = 0,
        chunk_mode: str = "",
    ) -> str:
        return build_relation_chunk_guidance(
            chunk_label=chunk_label,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chunk_mode=chunk_mode,
        )

    @staticmethod
    def _build_distill_priority_guidance(character: str) -> str:
        return build_distill_priority_guidance(character)

    def _build_dialogue_style_guidance(self, request: dict[str, Any], character: str) -> str:
        evidence_lines = self._extract_dialogue_evidence({"request": request}, character=character)
        return build_dialogue_style_guidance(evidence_lines)

    @staticmethod
    def _build_excerpt_stage_guidance(excerpt_stages: dict[str, Any]) -> str:
        return build_excerpt_stage_guidance(excerpt_stages)
