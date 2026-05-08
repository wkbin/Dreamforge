from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from src.utils.text_parser import split_sentences


def finalize_generated_profile_source(
    source_path: Path,
    *,
    payload: dict[str, Any],
    chunk_count: int,
    load_profile_source: Callable[[Path], dict[str, Any]],
    render_profile_md: Callable[[dict[str, Any]], str],
) -> None:
    try:
        profile = load_profile_source(source_path)
    except Exception:
        return
    evidence = profile_evidence_from_payload(payload, chunk_count=chunk_count)
    profile["description_count"] = int(evidence["description_count"])
    profile["dialogue_count"] = int(evidence["dialogue_count"])
    profile["thought_count"] = int(evidence["thought_count"])
    profile["chunk_count"] = int(evidence["chunk_count"])
    profile["evidence"] = {
        "description_count": int(evidence["description_count"]),
        "dialogue_count": int(evidence["dialogue_count"]),
        "thought_count": int(evidence["thought_count"]),
        "chunk_count": int(evidence["chunk_count"]),
    }
    if not str(profile.get("evidence_source", "")).strip():
        profile["evidence_source"] = str(evidence["evidence_source"]).strip()
    rendered = render_profile_md(profile).strip()
    if rendered:
        source_path.write_text(rendered + "\n", encoding="utf-8")


def profile_evidence_from_payload(payload: dict[str, Any], *, chunk_count: int) -> dict[str, Any]:
    request = dict(payload.get("request", {}) or {})
    excerpt = str(request.get("excerpt", "")).strip()
    sentences = [item.strip() for item in split_sentences(excerpt) if item.strip()]
    if not sentences and excerpt:
        sentences = [item.strip() for item in excerpt.splitlines() if item.strip()]

    description_count = 0
    dialogue_count = 0
    thought_count = 0
    for sentence in sentences:
        if looks_like_thought_or_evaluation_sentence(sentence):
            thought_count += 1
        elif looks_like_dialogue_sentence(sentence):
            dialogue_count += 1
        else:
            description_count += 1

    excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
    stage_refs: list[str] = []
    for stage_key in ("start", "mid", "end"):
        if str(excerpt_stages.get(stage_key, "")).strip():
            stage_refs.append(f"excerpt:{stage_key}")
    strategy = str((request.get("excerpt_focus", {}) or {}).get("strategy", "")).strip()
    if strategy:
        stage_refs.append(f"strategy:{strategy}")

    return {
        "description_count": description_count,
        "dialogue_count": dialogue_count,
        "thought_count": thought_count,
        "chunk_count": max(1, int(chunk_count or 1)),
        "evidence_source": "；".join(stage_refs),
    }


def looks_like_dialogue_sentence(text: str) -> bool:
    sample = str(text or "").strip()
    if not sample:
        return False
    if any(token in sample for token in ('"', "“", "”", "「", "」")):
        return True
    return bool(re.search(r"(说道|笑道|问道|答道|道：|道:|喊道|喝道|骂道|低声道|轻声道)", sample))


def looks_like_thought_or_evaluation_sentence(text: str) -> bool:
    sample = str(text or "").strip()
    if not sample:
        return False
    return bool(
        re.search(
            r"(心想|心道|心里|想着|只觉|觉得|不禁|暗想|思忖|寻思|素来|向来|一向|生性|性子|为人|看似|其实|原是|本就)",
            sample,
        )
    )
