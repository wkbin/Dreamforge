from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from src.core.config import Config
from src.core.exceptions import LLMRequestError

logger = logging.getLogger(__name__)


def generate_character_profile_markdown(
    *,
    parts: Any,
    config: Config,
    manifest_path: Path,
    payload: dict[str, Any],
    character: str,
    peer_characters: list[str],
    progress_hook: Any | None,
    assert_run_not_stopped: Callable[..., None],
    should_use_chunked_distill: Callable[[dict[str, Any]], bool],
    generate_character_profile_markdown_chunked: Callable[..., tuple[str, dict[str, Any]]],
    build_distill_llm_messages: Callable[..., list[dict[str, str]]],
    sanitize_markdown_output: Callable[[str], str],
    llm_cap: Callable[[Config, str, int], int],
    distill_single_max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    assert_run_not_stopped(manifest_path, current_character=character)
    if should_use_chunked_distill(payload):
        return generate_character_profile_markdown_chunked(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            payload=payload,
            character=character,
            peer_characters=peer_characters,
            progress_hook=progress_hook,
        )
    try:
        assert_run_not_stopped(manifest_path, current_character=character)
        llm_result = parts.llm.chat_completion(
            build_distill_llm_messages(
                payload,
                character=character,
                peer_characters=peer_characters,
            ),
            temperature=float(config.get("llm.temperature", 0.2) or 0.2),
            max_tokens=llm_cap(config, "llm.max_tokens", distill_single_max_tokens),
        )
        content = sanitize_markdown_output(str(llm_result.get("content", "")))
        return content, {"chunked": False, "chunk_count": 1}
    except LLMRequestError as exc:
        logger.warning("Single-pass distill failed for %s, retrying with chunked distill: %s", character, exc)
        return generate_character_profile_markdown_chunked(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            payload=payload,
            character=character,
            peer_characters=peer_characters,
            progress_hook=progress_hook,
            fallback_reason=str(exc),
        )


def generate_character_profile_markdown_chunked(
    *,
    parts: Any,
    config: Config,
    manifest_path: Path,
    payload: dict[str, Any],
    character: str,
    peer_characters: list[str],
    progress_hook: Any | None,
    fallback_reason: str,
    build_distill_chunk_payloads: Callable[[dict[str, Any]], list[dict[str, Any]]],
    assert_run_not_stopped: Callable[..., None],
    build_distill_llm_messages: Callable[..., list[dict[str, str]]],
    sanitize_markdown_output: Callable[[str], str],
    llm_cap: Callable[[Config, str, int], int],
    distill_single_max_tokens: int,
    chunk_parallel_workers: Callable[..., int],
    run_distill_chunk_drafts: Callable[..., list[dict[str, str]]],
    build_distill_merge_messages: Callable[..., list[dict[str, str]]],
    distill_merge_max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    chunk_entries = build_distill_chunk_payloads(payload)
    if len(chunk_entries) <= 1:
        assert_run_not_stopped(manifest_path, current_character=character)
        llm_result = parts.llm.chat_completion(
            build_distill_llm_messages(
                payload,
                character=character,
                peer_characters=peer_characters,
            ),
            temperature=float(config.get("llm.temperature", 0.2) or 0.2),
            max_tokens=llm_cap(config, "llm.max_tokens", distill_single_max_tokens),
        )
        content = sanitize_markdown_output(str(llm_result.get("content", "")))
        return content, {"chunked": False, "chunk_count": 1}

    workers = chunk_parallel_workers(config=config, chunk_total=len(chunk_entries))
    drafts = run_distill_chunk_drafts(
        parts=parts,
        config=config,
        manifest_path=manifest_path,
        chunk_entries=chunk_entries,
        character=character,
        peer_characters=peer_characters,
        progress_hook=progress_hook,
        workers=workers,
    )

    if not drafts:
        raise ValueError(f"{character} 的分批蒸馏结果为空。")
    if len(drafts) == 1:
        return drafts[0]["content"], {
            "chunked": True,
            "chunk_count": len(chunk_entries),
            "fallback_reason": fallback_reason,
            "parallel_workers": workers,
        }

    if callable(progress_hook):
        progress_hook("merging_character", {"character": character, "chunk_total": len(drafts), "parallel_workers": workers})
    assert_run_not_stopped(manifest_path, current_character=character)
    merge_result = parts.llm.chat_completion(
        build_distill_merge_messages(
            payload,
            character=character,
            peer_characters=peer_characters,
            chunk_drafts=drafts,
            fallback_reason=fallback_reason,
        ),
        temperature=float(config.get("llm.temperature", 0.2) or 0.2),
        max_tokens=llm_cap(config, "llm.max_tokens", distill_merge_max_tokens),
    )
    merged_content = sanitize_markdown_output(str(merge_result.get("content", "")))
    return merged_content, {
        "chunked": True,
        "chunk_count": len(chunk_entries),
        "fallback_reason": fallback_reason,
        "parallel_workers": workers,
    }


def generate_relation_markdown(
    *,
    parts: Any,
    config: Config,
    manifest_path: Path,
    payload: dict[str, Any],
    characters: list[str],
    progress_hook: Any | None,
    assert_run_not_stopped: Callable[..., None],
    should_use_chunked_relation: Callable[[dict[str, Any]], bool],
    generate_relation_markdown_chunked: Callable[..., tuple[str, dict[str, Any]]],
    build_relation_llm_messages: Callable[..., list[dict[str, str]]],
    sanitize_markdown_output: Callable[[str], str],
    llm_cap: Callable[[Config, str, int], int],
    relation_single_max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    stop_message = "这次蒸馏已停止，关系图未继续生成。"
    assert_run_not_stopped(manifest_path, message=stop_message)
    if should_use_chunked_relation(payload):
        return generate_relation_markdown_chunked(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            payload=payload,
            characters=characters,
            progress_hook=progress_hook,
        )
    try:
        assert_run_not_stopped(manifest_path, message=stop_message)
        relation_result = parts.llm.chat_completion(
            build_relation_llm_messages(payload, characters=characters),
            temperature=float(config.get("llm.temperature", 0.2) or 0.2),
            max_tokens=llm_cap(config, "llm.max_tokens", relation_single_max_tokens),
        )
        relation_markdown = sanitize_markdown_output(str(relation_result.get("content", "")))
        return relation_markdown, {"chunked": False, "chunk_count": 1}
    except LLMRequestError as exc:
        logger.warning("Single-pass relation graph failed, retrying with chunked relation distill: %s", exc)
        return generate_relation_markdown_chunked(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            payload=payload,
            characters=characters,
            progress_hook=progress_hook,
            fallback_reason=str(exc),
        )


def generate_relation_markdown_chunked(
    *,
    parts: Any,
    config: Config,
    manifest_path: Path,
    payload: dict[str, Any],
    characters: list[str],
    progress_hook: Any | None,
    fallback_reason: str,
    build_relation_chunk_payloads: Callable[[dict[str, Any]], list[dict[str, Any]]],
    assert_run_not_stopped: Callable[..., None],
    build_relation_llm_messages: Callable[..., list[dict[str, str]]],
    sanitize_markdown_output: Callable[[str], str],
    llm_cap: Callable[[Config, str, int], int],
    relation_single_max_tokens: int,
    chunk_parallel_workers: Callable[..., int],
    run_relation_chunk_drafts: Callable[..., list[dict[str, str]]],
    build_relation_merge_messages: Callable[..., list[dict[str, str]]],
    relation_merge_max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    stop_message = "这次蒸馏已停止，关系图未继续生成。"
    chunk_entries = build_relation_chunk_payloads(payload)
    if len(chunk_entries) <= 1:
        assert_run_not_stopped(manifest_path, message=stop_message)
        relation_result = parts.llm.chat_completion(
            build_relation_llm_messages(payload, characters=characters),
            temperature=float(config.get("llm.temperature", 0.2) or 0.2),
            max_tokens=llm_cap(config, "llm.max_tokens", relation_single_max_tokens),
        )
        relation_markdown = sanitize_markdown_output(str(relation_result.get("content", "")))
        return relation_markdown, {"chunked": False, "chunk_count": 1}

    workers = chunk_parallel_workers(config=config, chunk_total=len(chunk_entries))
    drafts = run_relation_chunk_drafts(
        parts=parts,
        config=config,
        manifest_path=manifest_path,
        chunk_entries=chunk_entries,
        characters=characters,
        progress_hook=progress_hook,
        workers=workers,
    )

    if not drafts:
        raise ValueError("分批关系图谱结果为空。")
    if len(drafts) == 1:
        return drafts[0]["content"], {
            "chunked": True,
            "chunk_count": len(chunk_entries),
            "fallback_reason": fallback_reason,
            "parallel_workers": workers,
        }

    if callable(progress_hook):
        progress_hook("merging_graph", {"chunk_total": len(drafts), "parallel_workers": workers})
    assert_run_not_stopped(manifest_path, message=stop_message)
    merge_result = parts.llm.chat_completion(
        build_relation_merge_messages(
            payload,
            characters=characters,
            chunk_drafts=drafts,
            fallback_reason=fallback_reason,
        ),
        temperature=float(config.get("llm.temperature", 0.2) or 0.2),
        max_tokens=llm_cap(config, "llm.max_tokens", relation_merge_max_tokens),
    )
    merged_markdown = sanitize_markdown_output(str(merge_result.get("content", "")))
    return merged_markdown, {
        "chunked": True,
        "chunk_count": len(chunk_entries),
        "fallback_reason": fallback_reason,
        "parallel_workers": workers,
    }
