from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from src.skill_support.novel_preparation import CHARACTER_VARIANT_MAP, MATCH_IGNORED_PATTERN
from src.utils.text_parser import load_novel_text, split_sentences

KEY_FIELDS = (
    "core_identity",
    "story_role",
    "identity_anchor",
    "temperament_type",
    "soul_goal",
    "core_traits",
    "key_bonds",
    "speech_style",
    "worldview",
    "belief_anchor",
    "moral_bottom_line",
    "restraint_threshold",
    "stress_response",
)

FIELD_LABELS = {
    "core_identity": "核心身份",
    "story_role": "故事位置",
    "identity_anchor": "身份锚点",
    "temperament_type": "气质底色",
    "soul_goal": "灵魂目标",
    "core_traits": "核心特质",
    "key_bonds": "重要牵系",
    "speech_style": "说话方式",
    "worldview": "世界观",
    "belief_anchor": "信念支点",
    "moral_bottom_line": "道德底线",
    "restraint_threshold": "失控阈值",
    "stress_response": "应激反应",
}

TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16", "utf-16-le", "utf-16-be")


def suggest_redistill_segments_payload(
    manifest: dict[str, Any],
    *,
    character: str,
    current_fields: dict[str, str] | None = None,
    max_segments: int = 3,
) -> dict[str, Any]:
    normalized_character = str(character or "").strip()
    if not normalized_character:
        raise ValueError("Character is required.")

    source_entry = _resolve_current_source_entry(manifest)
    source_path = Path(str(source_entry.get("source_path", "")).strip())
    if not source_path.exists():
        raise FileNotFoundError(str(source_path))

    text = _load_supported_source_text(source_path)
    sentences = [item.strip() for item in split_sentences(text) if item.strip()]
    weak_fields = _collect_weak_fields(current_fields or {})
    windows = _build_segment_windows(
        sentences,
        character=normalized_character,
        weak_fields=weak_fields,
        max_segments=max_segments,
    )

    return {
        "character": normalized_character,
        "source_name": str(source_entry.get("source_name", "")).strip() or source_path.name,
        "source_kind": str(source_entry.get("kind", "")).strip() or "initial",
        "source_path": str(source_path.resolve()),
        "weak_fields": weak_fields,
        "weak_field_labels": [FIELD_LABELS.get(name, name) for name in weak_fields],
        "segments": windows,
    }


def _resolve_current_source_entry(manifest: dict[str, Any]) -> dict[str, Any]:
    sources = list(manifest.get("novel_sources", []) or [])
    for item in reversed(sources):
        if isinstance(item, dict) and str(item.get("source_path", "")).strip():
            return item
    novel_path = Path(str(manifest.get("novel_path", "")).strip())
    if not novel_path.exists():
        raise FileNotFoundError(str(novel_path))
    return {
        "source_name": novel_path.name,
        "kind": "initial",
        "source_path": str(novel_path.resolve()),
    }


def _load_supported_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".epub"}:
        return load_novel_text(str(path))
    raw = path.read_bytes()
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _collect_weak_fields(fields: dict[str, str]) -> list[str]:
    weak = [field for field in KEY_FIELDS if _is_field_weak(field, str(fields.get(field, "")).strip())]
    return weak or list(KEY_FIELDS[:4])


def _is_field_weak(field: str, value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if field in {"worldview", "belief_anchor", "moral_bottom_line", "restraint_threshold", "stress_response", "speech_style", "identity_anchor", "soul_goal"}:
        return len(text) < 10
    if field in {"core_traits", "key_bonds"}:
        return len(text) < 6
    return len(text) < 4


def _normalize_match_text(text: str) -> str:
    sample = unicodedata.normalize("NFKC", str(text or "")).translate(CHARACTER_VARIANT_MAP)
    return MATCH_IGNORED_PATTERN.sub("", sample).lower()


def _count_character_mentions(text: str, character: str) -> int:
    normalized_text = _normalize_match_text(text)
    normalized_character = _normalize_match_text(character)
    if not normalized_text or not normalized_character:
        return 0
    return normalized_text.count(normalized_character)


def _looks_like_dialogue(sentence: str) -> bool:
    text = str(sentence or "")
    return any(token in text for token in ("“", "”", "\"", "「", "」", "『", "』", "道", "说", "问", "答", "笑道"))


def _looks_like_thought(sentence: str) -> bool:
    text = str(sentence or "")
    return any(token in text for token in ("心想", "想道", "想着", "觉得", "只觉", "暗想", "心里", "思忖"))


def _estimate_fields(*, weak_fields: list[str], dialogue_hits: int, thought_hits: int, cast_hits: int) -> list[str]:
    suggestions: list[str] = []

    def add(field: str) -> None:
        if field in weak_fields and field not in suggestions:
            suggestions.append(field)

    if dialogue_hits > 0:
        add("speech_style")
    if thought_hits > 0:
        add("soul_goal")
        add("worldview")
        add("identity_anchor")
    if cast_hits >= 2:
        add("key_bonds")
        add("core_traits")
    if dialogue_hits + thought_hits >= 2:
        add("temperament_type")
        add("stress_response")
    if cast_hits > 0:
        add("core_identity")
        add("story_role")

    for field in weak_fields:
        if len(suggestions) >= 4:
            break
        if field not in suggestions:
            suggestions.append(field)
    return suggestions[:4]


def _estimate_reason(*, dialogue_hits: int, thought_hits: int, cast_hits: int) -> str:
    reasons: list[str] = []
    if dialogue_hits > 0:
        reasons.append("对白密度较高")
    if thought_hits > 0:
        reasons.append("含人物内心或判断")
    if cast_hits >= 2:
        reasons.append("角色命中集中")
    if not reasons:
        reasons.append("这一段和目标角色有直接命中")
    return "，".join(reasons)


def _build_segment_windows(
    sentences: list[str],
    *,
    character: str,
    weak_fields: list[str],
    max_segments: int,
) -> list[dict[str, Any]]:
    if not sentences:
        return []

    candidates: list[dict[str, Any]] = []
    window_size = 8
    stride = 4
    for start in range(0, len(sentences), stride):
        chunk = sentences[start : start + window_size]
        if not chunk:
            break
        excerpt = "".join(chunk).strip()
        if not excerpt:
            continue
        cast_hits = _count_character_mentions(excerpt, character)
        if cast_hits <= 0:
            continue
        dialogue_hits = sum(1 for item in chunk if _looks_like_dialogue(item))
        thought_hits = sum(1 for item in chunk if _looks_like_thought(item))
        score = cast_hits * 30 + dialogue_hits * 12 + thought_hits * 10 - max(0, len(excerpt) - 420) // 30
        estimated_fields = _estimate_fields(
            weak_fields=weak_fields,
            dialogue_hits=dialogue_hits,
            thought_hits=thought_hits,
            cast_hits=cast_hits,
        )
        candidates.append(
            {
                "segment_id": f"seg-{start + 1}",
                "preview": _preview_text(excerpt),
                "full_text": excerpt,
                "start_sentence": start + 1,
                "end_sentence": start + len(chunk),
                "character_hits": cast_hits,
                "dialogue_hits": dialogue_hits,
                "thought_hits": thought_hits,
                "score": max(score, 1),
                "estimated_fields": estimated_fields,
                "estimated_field_labels": [FIELD_LABELS.get(name, name) for name in estimated_fields],
                "reason": _estimate_reason(dialogue_hits=dialogue_hits, thought_hits=thought_hits, cast_hits=cast_hits),
            }
        )

    candidates.sort(
        key=lambda item: (
            -int(item["score"]),
            -int(item["character_hits"]),
            -int(item["dialogue_hits"]),
            int(item["start_sentence"]),
        )
    )

    unique: list[dict[str, Any]] = []
    seen_ranges: set[tuple[int, int]] = set()
    for item in candidates:
        key = (int(item["start_sentence"]), int(item["end_sentence"]))
        if key in seen_ranges:
            continue
        seen_ranges.add(key)
        unique.append(item)
        if len(unique) >= max_segments:
            break
    return unique


def _preview_text(text: str, limit: int = 120) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"
