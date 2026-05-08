from __future__ import annotations

from pathlib import Path
from typing import Any

from src.web.artifacts import load_profile_source, render_profile_md
from src.web.review import (
    apply_profile_missing_fallbacks,
    collect_relation_repair_issues,
    extract_dialogue_evidence,
    finalize_generated_profile_source,
    looks_generic_style_scalar,
    looks_like_dialogue_sentence,
    looks_like_thought_or_evaluation_sentence,
    looks_like_unstable_profile_scalar,
    looks_like_unstable_relation_scalar,
    merge_profile_patch,
    parse_profile_metric_map,
    profile_evidence_from_payload,
    profile_list_value,
    split_profile_list_value,
)


class ReviewHelpersMixin:
    def _finalize_generated_profile_source(
        self,
        source_path: Path,
        *,
        payload: dict[str, Any],
        chunk_count: int,
    ) -> None:
        finalize_generated_profile_source(
            source_path,
            payload=payload,
            chunk_count=chunk_count,
            load_profile_source=load_profile_source,
            render_profile_md=render_profile_md,
        )

    def _profile_evidence_from_payload(self, payload: dict[str, Any], *, chunk_count: int) -> dict[str, Any]:
        return profile_evidence_from_payload(payload, chunk_count=chunk_count)

    @staticmethod
    def _looks_like_dialogue_sentence(text: str) -> bool:
        return looks_like_dialogue_sentence(text)

    @staticmethod
    def _looks_like_thought_or_evaluation_sentence(text: str) -> bool:
        return looks_like_thought_or_evaluation_sentence(text)

    def _collect_relation_repair_issues(self, relation_payload: dict[str, Any]) -> list[str]:
        return collect_relation_repair_issues(
            relation_payload,
            rewrite_fields=self.RELATION_REWRITE_FIELDS,
        )

    @staticmethod
    def _looks_like_unstable_relation_scalar(value: str) -> bool:
        return looks_like_unstable_relation_scalar(value)

    def _merge_profile_patch(self, profile: dict[str, Any], patch_text: str) -> None:
        merge_profile_patch(
            profile,
            patch_text,
            profile_list_fields=self.PROFILE_LIST_FIELDS,
            profile_map_fields=self.PROFILE_MAP_FIELDS,
        )

    def _apply_profile_missing_fallbacks(self, profile: dict[str, Any]) -> None:
        apply_profile_missing_fallbacks(
            profile,
            completion_fields=self.PROFILE_COMPLETION_FIELDS,
            profile_list_fields=self.PROFILE_LIST_FIELDS,
            profile_map_fields=self.PROFILE_MAP_FIELDS,
        )

    @staticmethod
    def _split_profile_list_value(value: str) -> list[str]:
        return split_profile_list_value(value)

    @staticmethod
    def _parse_profile_metric_map(value: str) -> dict[str, Any]:
        return parse_profile_metric_map(value)

    @staticmethod
    def _profile_list_value(profile: dict[str, Any], key: str) -> list[str]:
        return profile_list_value(profile, key)

    @staticmethod
    def _looks_generic_style_scalar(value: str) -> bool:
        return looks_generic_style_scalar(value)

    def _extract_dialogue_evidence(self, payload: dict[str, Any], *, character: str) -> list[str]:
        return extract_dialogue_evidence(payload, character=character)

    @staticmethod
    def _looks_like_unstable_profile_scalar(value: str) -> bool:
        return looks_like_unstable_profile_scalar(value)
