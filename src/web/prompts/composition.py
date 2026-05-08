from __future__ import annotations

from typing import Any, Callable

from src.web.prompts.builders import (
    build_distill_completion_messages,
    build_distill_llm_messages,
    build_distill_merge_messages,
    build_distill_repair_messages,
    build_relation_llm_messages,
    build_relation_merge_messages,
)
from src.web.review.relation_repair import build_relation_repair_messages


def compose_distill_llm_messages(
    payload: dict[str, Any],
    *,
    character: str,
    peer_characters: list[str] | None,
    normalize_characters: Callable[[list[str]], list[str]],
    build_excerpt_stage_guidance: Callable[[dict[str, Any]], str],
    build_dialogue_style_guidance: Callable[[dict[str, Any], str], str],
    build_distill_priority_guidance: Callable[[str], str],
    build_chunk_distill_guidance: Callable[..., str],
    chunk_label: str = "",
    chunk_index: int = 0,
    chunk_total: int = 0,
    chunk_mode: str = "",
) -> list[dict[str, str]]:
    request = dict(payload.get("request", {}) or {})
    peers = [name for name in normalize_characters(peer_characters or []) if name != character]
    excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
    return build_distill_llm_messages(
        payload,
        character=character,
        peers=peers,
        excerpt_stage_guidance=build_excerpt_stage_guidance(excerpt_stages),
        dialogue_style_guidance=build_dialogue_style_guidance(request, character),
        priority_guidance=build_distill_priority_guidance(character),
        chunk_guidance=build_chunk_distill_guidance(
            chunk_label=chunk_label,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chunk_mode=chunk_mode,
        ),
    )


def compose_distill_merge_messages(
    payload: dict[str, Any],
    *,
    character: str,
    peer_characters: list[str] | None,
    chunk_drafts: list[dict[str, str]],
    fallback_reason: str,
    normalize_characters: Callable[[list[str]], list[str]],
    build_excerpt_stage_guidance: Callable[[dict[str, Any]], str],
    build_dialogue_style_guidance: Callable[[dict[str, Any], str], str],
    build_distill_priority_guidance: Callable[[str], str],
) -> list[dict[str, str]]:
    request = dict(payload.get("request", {}) or {})
    excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
    peers = [name for name in normalize_characters(peer_characters or []) if name != character]
    return build_distill_merge_messages(
        payload,
        character=character,
        peers=peers,
        chunk_drafts=chunk_drafts,
        fallback_reason=fallback_reason,
        excerpt_stage_guidance=build_excerpt_stage_guidance(excerpt_stages),
        dialogue_style_guidance=build_dialogue_style_guidance(request, character),
        priority_guidance=build_distill_priority_guidance(character),
    )


def compose_relation_llm_messages(
    payload: dict[str, Any],
    *,
    characters: list[str],
    normalize_characters: Callable[[list[str]], list[str]],
    build_relation_chunk_guidance: Callable[..., str],
    chunk_label: str = "",
    chunk_index: int = 0,
    chunk_total: int = 0,
    chunk_mode: str = "",
) -> list[dict[str, str]]:
    return build_relation_llm_messages(
        payload,
        characters=normalize_characters(characters),
        chunk_guidance=build_relation_chunk_guidance(
            chunk_label=chunk_label,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chunk_mode=chunk_mode,
        ),
    )


def compose_relation_merge_messages(
    payload: dict[str, Any],
    *,
    characters: list[str],
    chunk_drafts: list[dict[str, str]],
    fallback_reason: str,
    normalize_characters: Callable[[list[str]], list[str]],
) -> list[dict[str, str]]:
    return build_relation_merge_messages(
        payload,
        characters=normalize_characters(characters),
        chunk_drafts=chunk_drafts,
        fallback_reason=fallback_reason,
    )


def compose_distill_repair_messages(
    payload: dict[str, Any],
    *,
    character: str,
    peer_characters: list[str],
    profile: dict[str, Any],
    group_name: str,
    fields: tuple[str, ...],
    repair_targets: dict[str, str],
    dialogue_evidence: list[str] | None,
    build_distill_llm_messages_fn: Callable[..., list[dict[str, str]]],
    render_profile_md: Callable[[dict[str, Any]], str],
) -> list[dict[str, str]]:
    base_messages = build_distill_llm_messages_fn(payload, character=character, peer_characters=peer_characters)
    return build_distill_repair_messages(
        base_messages,
        payload=payload,
        profile_markdown=render_profile_md(profile),
        group_name=group_name,
        fields=fields,
        repair_targets=repair_targets,
        dialogue_evidence=list(dialogue_evidence or []),
    )


def compose_distill_completion_messages(
    payload: dict[str, Any],
    *,
    character: str,
    peer_characters: list[str],
    profile: dict[str, Any],
    group_name: str,
    fields: tuple[str, ...],
    dialogue_evidence: list[str] | None,
    build_distill_llm_messages_fn: Callable[..., list[dict[str, str]]],
    render_profile_md: Callable[[dict[str, Any]], str],
) -> list[dict[str, str]]:
    base_messages = build_distill_llm_messages_fn(payload, character=character, peer_characters=peer_characters)
    return build_distill_completion_messages(
        base_messages,
        payload=payload,
        profile_markdown=render_profile_md(profile),
        group_name=group_name,
        fields=fields,
        dialogue_evidence=list(dialogue_evidence or []),
    )


def compose_relation_repair_messages(
    payload: dict[str, Any],
    *,
    characters: list[str],
    relation_markdown: str,
    issues: list[str],
    build_relation_llm_messages_fn: Callable[..., list[dict[str, str]]],
) -> list[dict[str, str]]:
    base_messages = build_relation_llm_messages_fn(payload, characters=characters)
    return build_relation_repair_messages(
        base_messages,
        relation_markdown=relation_markdown,
        issues=issues,
    )
