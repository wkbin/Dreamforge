from __future__ import annotations

from typing import Any, Callable


def should_use_chunking(
    text: str,
    *,
    trigger_chars: int,
    trigger_sentences: int,
    sentence_splitter: Callable[[str], list[str]],
) -> bool:
    excerpt = str(text or "").strip()
    if not excerpt:
        return False
    sentence_count = len(sentence_splitter(excerpt))
    return len(excerpt) > int(trigger_chars) or sentence_count > int(trigger_sentences)


def split_text_into_chunks(
    text: str,
    *,
    max_chars: int,
    max_sentences: int,
    sentence_splitter: Callable[[str], list[str]],
) -> list[str]:
    clean = str(text or "").strip()
    if not clean:
        return []
    sentences = [item.strip() for item in sentence_splitter(clean) if item.strip()]
    if not sentences:
        sentences = [item.strip() for item in clean.splitlines() if item.strip()] or [clean]
    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0
    for sentence in sentences:
        units = [sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars)] or [sentence]
        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            projected = current_chars + len(unit) + (1 if current else 0)
            if current and (len(current) >= max_sentences or projected > max_chars):
                chunks.append("\n".join(current).strip())
                current = []
                current_chars = 0
            current.append(unit)
            current_chars += len(unit) + (1 if len(current) > 1 else 0)
    if current:
        chunks.append("\n".join(current).strip())
    return [item for item in chunks if item]


def build_distill_chunk_payloads(
    payload: dict[str, Any],
    *,
    chunk_excerpt_text: Callable[[str], list[str]],
) -> list[dict[str, Any]]:
    request = dict(payload.get("request", {}) or {})
    excerpt = str(request.get("excerpt", "")).strip()
    excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
    chunk_entries: list[dict[str, Any]] = []
    for stage_key, stage_label in (("start", "前段"), ("mid", "中段"), ("end", "后段")):
        stage_text = str(excerpt_stages.get(stage_key, "")).strip()
        if not stage_text:
            continue
        stage_chunks = chunk_excerpt_text(stage_text)
        for index, chunk_text in enumerate(stage_chunks, start=1):
            chunk_request = dict(request)
            chunk_request["excerpt"] = chunk_text
            chunk_request["excerpt_stages"] = {"start": "", "mid": "", "end": ""}
            chunk_request["excerpt_stages"][stage_key] = chunk_text
            chunk_request["excerpt_focus"] = {
                **dict(request.get("excerpt_focus", {}) or {}),
                "strategy": "chunked_character_windows",
            }
            chunk_meta = dict(payload.get("meta", {}) or {})
            chunk_meta["chunk_stage"] = stage_key
            chunk_meta["chunk_index"] = index
            chunk_meta["chunk_total"] = len(stage_chunks)
            chunk_entries.append(
                {
                    "label": f"{stage_label}-{index}" if len(stage_chunks) > 1 else stage_label,
                    "payload": {
                        **payload,
                        "request": chunk_request,
                        "meta": chunk_meta,
                    },
                }
            )
    if chunk_entries:
        return chunk_entries
    excerpt_chunks = chunk_excerpt_text(excerpt)
    return [
        {
            "label": f"证据块-{index}",
            "payload": {
                **payload,
                "request": {
                    **request,
                    "excerpt": chunk_text,
                    "excerpt_stages": {"start": "", "mid": "", "end": ""},
                },
                "meta": {
                    **dict(payload.get("meta", {}) or {}),
                    "chunk_index": index,
                    "chunk_total": len(excerpt_chunks),
                },
            },
        }
        for index, chunk_text in enumerate(excerpt_chunks, start=1)
    ]


def build_relation_chunk_payloads(
    payload: dict[str, Any],
    *,
    chunk_relation_text: Callable[[str], list[str]],
) -> list[dict[str, Any]]:
    request = dict(payload.get("request", {}) or {})
    excerpt = str(request.get("excerpt", "")).strip()
    excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
    chunk_entries: list[dict[str, Any]] = []
    for stage_key, stage_label in (("start", "前段"), ("mid", "中段"), ("end", "后段")):
        stage_text = str(excerpt_stages.get(stage_key, "")).strip()
        if not stage_text:
            continue
        stage_chunks = chunk_relation_text(stage_text)
        for index, chunk_text in enumerate(stage_chunks, start=1):
            chunk_request = dict(request)
            chunk_request["excerpt"] = chunk_text
            chunk_request["excerpt_stages"] = {"start": "", "mid": "", "end": ""}
            chunk_request["excerpt_stages"][stage_key] = chunk_text
            chunk_request["excerpt_focus"] = {
                **dict(request.get("excerpt_focus", {}) or {}),
                "strategy": "chunked_relation_windows",
            }
            chunk_entries.append(
                {
                    "label": f"{stage_label}-{index}" if len(stage_chunks) > 1 else stage_label,
                    "payload": {
                        **payload,
                        "request": chunk_request,
                        "meta": {
                            **dict(payload.get("meta", {}) or {}),
                            "chunk_stage": stage_key,
                            "chunk_index": index,
                            "chunk_total": len(stage_chunks),
                        },
                    },
                }
            )
    if chunk_entries:
        return chunk_entries
    excerpt_chunks = chunk_relation_text(excerpt)
    return [
        {
            "label": f"关系块-{index}",
            "payload": {
                **payload,
                "request": {
                    **request,
                    "excerpt": chunk_text,
                    "excerpt_stages": {"start": "", "mid": "", "end": ""},
                },
                "meta": {
                    **dict(payload.get("meta", {}) or {}),
                    "chunk_index": index,
                    "chunk_total": len(excerpt_chunks),
                },
            },
        }
        for index, chunk_text in enumerate(excerpt_chunks, start=1)
    ]
