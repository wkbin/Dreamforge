from __future__ import annotations

import concurrent.futures
import logging
from pathlib import Path
from typing import Any, Callable

from src.core.config import Config

logger = logging.getLogger(__name__)


def chunk_parallel_workers(*, config: Config, chunk_total: int) -> int:
    if chunk_total <= 1:
        return 1
    provider = str(config.get("llm.provider", "") or "").strip().lower()
    configured = int(config.get("llm.parallel_chunk_workers", 6) or 6)
    configured = max(1, configured)
    if provider == "ollama":
        return 1
    return min(configured, 6, chunk_total)


def run_distill_chunk_drafts(
    *,
    parts: Any,
    config: Config,
    manifest_path: Path,
    chunk_entries: list[dict[str, Any]],
    character: str,
    peer_characters: list[str],
    progress_hook: Any | None,
    workers: int,
    assert_not_stopped: Callable[..., None],
    build_distill_llm_messages: Callable[..., list[dict[str, str]]],
    chat_completion: Callable[[list[dict[str, str]], float, int], dict[str, Any]],
    sanitize_markdown_output: Callable[[str], str],
    llm_cap: Callable[[Config, str, int], int],
    chunk_max_tokens: int,
    stopped_error_type: type[BaseException],
) -> list[dict[str, str]]:
    def run_one(index: int, chunk_entry: dict[str, Any]) -> dict[str, str]:
        assert_not_stopped(manifest_path, current_character=character)
        if callable(progress_hook):
            progress_hook(
                "chunking_character",
                {
                    "character": character,
                    "chunk_index": index,
                    "chunk_total": len(chunk_entries),
                    "chunk_label": chunk_entry["label"],
                    "parallel_workers": workers,
                },
            )
        assert_not_stopped(manifest_path, current_character=character)
        llm_result = chat_completion(
            build_distill_llm_messages(
                chunk_entry["payload"],
                character=character,
                peer_characters=peer_characters,
                chunk_label=str(chunk_entry["label"]),
                chunk_index=index,
                chunk_total=len(chunk_entries),
                chunk_mode="partial",
            ),
            float(config.get("llm.temperature", 0.18) or 0.18),
            llm_cap(config, "llm.max_tokens", chunk_max_tokens),
        )
        content = sanitize_markdown_output(str(llm_result.get("content", ""))).strip()
        return {"label": str(chunk_entry["label"]), "content": content, "index": index}

    return _run_chunk_drafts(
        run_one=run_one,
        chunk_entries=chunk_entries,
        workers=workers,
        thread_name_prefix="zaomeng-distill",
        stopped_error_type=stopped_error_type,
        fallback_warning=lambda exc: logger.warning(
            "Parallel distill chunk execution failed for %s, falling back to sequential mode: %s",
            character,
            exc,
        ),
        before_each=lambda index, _: assert_not_stopped(manifest_path, current_character=character),
    )


def run_relation_chunk_drafts(
    *,
    parts: Any,
    config: Config,
    manifest_path: Path,
    chunk_entries: list[dict[str, Any]],
    characters: list[str],
    progress_hook: Any | None,
    workers: int,
    assert_not_stopped: Callable[..., None],
    build_relation_llm_messages: Callable[..., list[dict[str, str]]],
    chat_completion: Callable[[list[dict[str, str]], float, int], dict[str, Any]],
    sanitize_markdown_output: Callable[[str], str],
    llm_cap: Callable[[Config, str, int], int],
    chunk_max_tokens: int,
    stopped_error_type: type[BaseException],
) -> list[dict[str, str]]:
    stopped_message = "这次蒸馏已停止，关系图未继续生成。"

    def run_one(index: int, chunk_entry: dict[str, Any]) -> dict[str, str]:
        assert_not_stopped(manifest_path, message=stopped_message)
        if callable(progress_hook):
            progress_hook(
                "chunking_graph",
                {
                    "chunk_index": index,
                    "chunk_total": len(chunk_entries),
                    "chunk_label": chunk_entry["label"],
                    "parallel_workers": workers,
                },
            )
        assert_not_stopped(manifest_path, message=stopped_message)
        relation_result = chat_completion(
            build_relation_llm_messages(
                chunk_entry["payload"],
                characters=characters,
                chunk_label=str(chunk_entry["label"]),
                chunk_index=index,
                chunk_total=len(chunk_entries),
                chunk_mode="partial",
            ),
            float(config.get("llm.temperature", 0.18) or 0.18),
            llm_cap(config, "llm.max_tokens", chunk_max_tokens),
        )
        content = sanitize_markdown_output(str(relation_result.get("content", ""))).strip()
        return {"label": str(chunk_entry["label"]), "content": content, "index": index}

    return _run_chunk_drafts(
        run_one=run_one,
        chunk_entries=chunk_entries,
        workers=workers,
        thread_name_prefix="zaomeng-relation",
        stopped_error_type=stopped_error_type,
        fallback_warning=lambda exc: logger.warning(
            "Parallel relation chunk execution failed, falling back to sequential mode: %s",
            exc,
        ),
        before_each=lambda index, _: assert_not_stopped(manifest_path, message=stopped_message),
    )


def _run_chunk_drafts(
    *,
    run_one: Callable[[int, dict[str, Any]], dict[str, str]],
    chunk_entries: list[dict[str, Any]],
    workers: int,
    thread_name_prefix: str,
    stopped_error_type: type[BaseException],
    fallback_warning: Callable[[Exception], None],
    before_each: Callable[[int, dict[str, Any]], None],
) -> list[dict[str, str]]:
    if workers <= 1:
        return _run_chunk_drafts_sequential(
            run_one=run_one,
            chunk_entries=chunk_entries,
            before_each=before_each,
        )

    try:
        futures: dict[concurrent.futures.Future[dict[str, str]], int] = {}
        drafts: list[dict[str, str]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix=thread_name_prefix) as executor:
            for index, chunk_entry in enumerate(chunk_entries, start=1):
                futures[executor.submit(run_one, index, chunk_entry)] = index
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result["content"]:
                    drafts.append(result)
        return sorted(drafts, key=lambda item: int(item["index"]))
    except Exception as exc:
        if isinstance(exc, stopped_error_type):
            raise
        fallback_warning(exc)
        return _run_chunk_drafts_sequential(
            run_one=run_one,
            chunk_entries=chunk_entries,
            before_each=before_each,
        )


def _run_chunk_drafts_sequential(
    *,
    run_one: Callable[[int, dict[str, Any]], dict[str, str]],
    chunk_entries: list[dict[str, Any]],
    before_each: Callable[[int, dict[str, Any]], None],
) -> list[dict[str, str]]:
    drafts: list[dict[str, str]] = []
    for index, chunk_entry in enumerate(chunk_entries, start=1):
        before_each(index, chunk_entry)
        result = run_one(index, chunk_entry)
        if result["content"]:
            drafts.append(result)
    return sorted(drafts, key=lambda item: int(item["index"]))
