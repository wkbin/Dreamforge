#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

TEXT_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "gb18030",
    "gbk",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
)

MIXED_EXCERPT_MIN_CHARS = 3_000
MIXED_EXCERPT_MIN_SENTENCES = 40

CHARACTER_VARIANT_MAP = str.maketrans(
    {
        "寶": "宝",
        "釵": "钗",
        "賈": "贾",
        "夢": "梦",
        "樓": "楼",
        "藍": "蓝",
        "無": "无",
        "羨": "羡",
        "齊": "齐",
        "澤": "泽",
        "劉": "刘",
        "備": "备",
        "關": "关",
        "寧": "宁",
        "蘇": "苏",
        "葉": "叶",
        "鐘": "钟",
        "鍾": "钟",
        "餘": "余",
        "後": "后",
        "臺": "台",
        "蕭": "萧",
        "萬": "万",
        "陳": "陈",
        "吳": "吴",
        "鄭": "郑",
        "趙": "赵",
        "孫": "孙",
        "錢": "钱",
        "馬": "马",
        "許": "许",
        "顧": "顾",
        "謝": "谢",
        "韓": "韩",
        "歐": "欧",
    }
)

MATCH_IGNORED_PATTERN = re.compile(r"[\s\u3000\u00b7\u2027\u30fb'\"`~!@#$%^&*()_+\-=\[\]{}\\|;:,.<>/?，。！？：；、“”‘’《》【】（）]")


def _decode_score(text: str) -> tuple[int, int, int, int]:
    if not text:
        return (-10_000, 0, 0, 0)
    replacement_count = text.count("�")
    null_count = text.count("\x00")
    cjk_count = sum(1 for ch in text if "一" <= ch <= "鿿")
    readable_count = sum(1 for ch in text if ch.isprintable() or ch in "\r\n\t")
    return (
        cjk_count * 4 + readable_count - replacement_count * 50 - null_count * 100,
        cjk_count,
        -replacement_count,
        -null_count,
    )


def _strip_html_tags(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_text_bytes(raw: bytes) -> str:
    for preferred in ("utf-8-sig", "utf-8"):
        try:
            decoded = raw.decode(preferred)
        except UnicodeDecodeError:
            continue
        if "�" not in decoded and "\x00" not in decoded:
            return decoded

    last_error: UnicodeError | None = None
    best_text = ""
    best_score: tuple[int, int, int, int] | None = None
    for encoding in TEXT_ENCODINGS:
        try:
            decoded = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        score = _decode_score(decoded)
        if best_score is None or score > best_score:
            best_text = decoded
            best_score = score
    if best_score is not None and best_score[0] > 0:
        return best_text
    if best_text:
        return best_text
    if last_error:
        raise UnicodeError("无法识别小说文本编码，请转换为 UTF-8 或 GB18030 后重试") from last_error
    raise UnicodeError("无法读取小说文本")


def load_novel_text(path: str | Path) -> str:
    novel_path = Path(path)
    if not novel_path.exists():
        raise FileNotFoundError(f"小说文件不存在: {novel_path}")

    suffix = novel_path.suffix.lower()
    if suffix == ".txt":
        return _decode_text_bytes(novel_path.read_bytes())
    if suffix == ".epub":
        return _load_epub(novel_path)
    raise ValueError(f"不支持的文件类型: {suffix}，仅支持 .txt / .epub")


def _load_epub(path: Path) -> str:
    try:
        from ebooklib import epub
    except ImportError as exc:
        raise ImportError("读取 .epub 需要安装 ebooklib") from exc

    book = epub.read_epub(str(path))
    chunks: list[str] = []
    for item in book.get_items():
        if item.get_type() == 9:
            html = item.get_content().decode("utf-8", errors="ignore")
            text = _strip_html_tags(html)
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[。！？!?])\s*", text)
    return [p.strip() for p in parts if p.strip()]


def prepare_novel_excerpt(
    text: str,
    *,
    max_sentences: int = 80,
    max_chars: int = 12_000,
    characters: list[str] | None = None,
) -> str:
    return build_excerpt_payload_from_text(
        text,
        max_sentences=max_sentences,
        max_chars=max_chars,
        characters=characters,
    )["excerpt"]


def build_excerpt_payload_from_text(
    text: str,
    *,
    max_sentences: int = 80,
    max_chars: int = 12_000,
    characters: list[str] | None = None,
) -> dict[str, Any]:
    clean = str(text or "").strip()
    if not clean:
        return {
            "excerpt": "",
            "requested_characters": _normalize_characters(characters),
            "matched_characters": [],
            "missing_characters": _normalize_characters(characters),
            "excerpt_strategy": "empty",
            "excerpt_stages": _empty_stage_blocks(),
        }

    sentences = split_sentences(clean)
    requested = _normalize_characters(characters)
    if requested:
        payload = _character_focused_excerpt(
            sentences,
            requested,
            max_sentences=max_sentences,
            max_chars=max_chars,
        )
        if payload["excerpt"]:
            return payload

    selected_indices = _select_leading_indices(sentences, max_sentences=max_sentences, max_chars=max_chars)
    return _build_excerpt_result(
        sentences,
        selected_indices,
        requested_characters=requested,
        matched_characters=[],
        missing_characters=requested,
        excerpt_strategy="leading_sentences",
        max_chars=max_chars,
    )


def load_prepared_novel_excerpt(
    novel_path: str | Path,
    *,
    max_sentences: int = 80,
    max_chars: int = 12_000,
    characters: list[str] | None = None,
) -> str:
    return prepare_novel_excerpt(
        load_novel_text(novel_path),
        max_sentences=max_sentences,
        max_chars=max_chars,
        characters=characters,
    )


def build_excerpt_payload(
    novel_path: str | Path,
    *,
    max_sentences: int = 80,
    max_chars: int = 12_000,
    characters: list[str] | None = None,
) -> dict[str, object]:
    path = Path(novel_path)
    excerpt_payload = build_excerpt_payload_from_text(
        load_novel_text(path),
        max_sentences=max_sentences,
        max_chars=max_chars,
        characters=characters,
    )
    return {
        "source_path": str(path),
        "source_name": path.name,
        "max_sentences": max_sentences,
        "max_chars": max_chars,
        "requested_characters": list(excerpt_payload["requested_characters"]),
        "matched_characters": list(excerpt_payload["matched_characters"]),
        "missing_characters": list(excerpt_payload["missing_characters"]),
        "excerpt_strategy": str(excerpt_payload["excerpt_strategy"]),
        "excerpt": str(excerpt_payload["excerpt"]),
        "excerpt_stages": dict(excerpt_payload["excerpt_stages"]),
    }


def _normalize_characters(characters: list[str] | None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in list(characters or []):
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def _normalize_match_text(text: str) -> str:
    sample = unicodedata.normalize("NFKC", str(text or "")).translate(CHARACTER_VARIANT_MAP)
    return MATCH_IGNORED_PATTERN.sub("", sample).lower()


def _sentence_mentions_character(sentence: str, character: str) -> bool:
    normalized_character = _normalize_match_text(character)
    if not normalized_character:
        return False
    return normalized_character in _normalize_match_text(sentence)


def _leading_excerpt(sentences: list[str], *, max_sentences: int, max_chars: int) -> str:
    selected_indices = _select_leading_indices(sentences, max_sentences=max_sentences, max_chars=max_chars)
    return _render_excerpt_from_indices(sentences, selected_indices, max_chars=max_chars)


def _select_leading_indices(sentences: list[str], *, max_sentences: int, max_chars: int) -> list[int]:
    selected: list[str] = []
    selected_indices: list[int] = []
    total_chars = 0
    for idx, sentence in enumerate(sentences):
        if len(selected) >= max_sentences:
            break
        projected = total_chars + len(sentence) + (1 if selected else 0)
        if selected and projected > max_chars:
            break
        if not selected and len(sentence) > max_chars:
            return [idx]
        selected.append(sentence)
        selected_indices.append(idx)
        total_chars = projected

    if selected_indices:
        return selected_indices
    return [0] if sentences else []


def _character_focused_excerpt(
    sentences: list[str],
    characters: list[str],
    *,
    max_sentences: int,
    max_chars: int,
) -> dict[str, Any]:
    character_hits: dict[str, list[int]] = {name: [] for name in characters}
    all_hit_indices: list[int] = []
    seen_hits: set[int] = set()

    for idx, sentence in enumerate(sentences):
        for name in characters:
            if _sentence_mentions_character(sentence, name):
                character_hits[name].append(idx)
                if idx not in seen_hits:
                    seen_hits.add(idx)
                    all_hit_indices.append(idx)

    matched = [name for name, hits in character_hits.items() if hits]
    missing = [name for name in characters if not character_hits[name]]
    if not matched:
        return {
            "excerpt": "",
            "requested_characters": characters,
            "matched_characters": [],
            "missing_characters": missing,
            "excerpt_strategy": "leading_sentences",
            "excerpt_stages": _empty_stage_blocks(),
        }

    center_budget = max(1, min(max_sentences, max_chars // 48))
    representative_hits = _build_representative_hit_plan(character_hits, matched, center_budget=center_budget)
    candidate_indices = _candidate_indices_from_centers(representative_hits, total_sentences=len(sentences))

    selected_indices: list[int] = []
    used_indices: set[int] = set()
    total_chars = 0
    for idx in candidate_indices:
        if len(selected_indices) >= max_sentences or idx in used_indices:
            continue
        sentence = sentences[idx]
        projected = total_chars + len(sentence) + (1 if selected_indices else 0)
        if selected_indices and projected > max_chars:
            continue
        if not selected_indices and len(sentence) > max_chars:
            selected_indices.append(idx)
            used_indices.add(idx)
            total_chars = max_chars
            break
        selected_indices.append(idx)
        used_indices.add(idx)
        total_chars = projected

    selected_indices.sort()
    augmented = False
    if _needs_character_excerpt_augmentation(
        sentences,
        selected_indices,
        max_sentences=max_sentences,
        max_chars=max_chars,
    ):
        selected_indices = _augment_character_excerpt_indices(
            sentences,
            selected_indices,
            character_hits=character_hits,
            matched_characters=matched,
            max_sentences=max_sentences,
            max_chars=max_chars,
        )
        augmented = True
    return _build_excerpt_result(
        sentences,
        selected_indices,
        requested_characters=characters,
        matched_characters=matched,
        missing_characters=missing,
        excerpt_strategy="character_windows_mixed" if augmented else "character_windows",
        max_chars=max_chars,
    )


def _needs_character_excerpt_augmentation(
    sentences: list[str],
    selected_indices: list[int],
    *,
    max_sentences: int,
    max_chars: int,
) -> bool:
    if not selected_indices:
        return False
    target_chars = min(max_chars, MIXED_EXCERPT_MIN_CHARS)
    target_sentences = min(max_sentences, MIXED_EXCERPT_MIN_SENTENCES)
    excerpt = _render_excerpt_from_indices(sentences, selected_indices, max_chars=max_chars)
    current_sentences = len([item for item in split_sentences(excerpt) if item.strip()])
    return len(excerpt) < target_chars or current_sentences < target_sentences


def _augment_character_excerpt_indices(
    sentences: list[str],
    selected_indices: list[int],
    *,
    character_hits: dict[str, list[int]],
    matched_characters: list[str],
    max_sentences: int,
    max_chars: int,
) -> list[int]:
    used_indices = {idx for idx in selected_indices if 0 <= idx < len(sentences)}
    ordered = sorted(used_indices)

    def current_chars() -> int:
        return len(_render_excerpt_from_indices(sentences, ordered, max_chars=max_chars))

    def enough() -> bool:
        target_chars = min(max_chars, MIXED_EXCERPT_MIN_CHARS)
        target_sentences = min(max_sentences, MIXED_EXCERPT_MIN_SENTENCES)
        return len(ordered) >= target_sentences and current_chars() >= target_chars

    def try_add(index: int) -> None:
        nonlocal ordered
        if index in used_indices or not (0 <= index < len(sentences)):
            return
        if len(ordered) >= max_sentences:
            return
        sentence = sentences[index].strip()
        if not sentence:
            return
        projected_chars = current_chars() + len(sentence) + (1 if ordered else 0)
        if ordered and projected_chars > max_chars:
            return
        used_indices.add(index)
        ordered = sorted(used_indices)

    def add_candidates(indices: list[int], *, radius: int = 0) -> None:
        for center in indices:
            for idx in _window_indices(center, len(sentences), radius=radius):
                try_add(idx)
                if enough():
                    return

    add_candidates(_build_dense_hit_plan(character_hits, matched_characters, sample_cap=8), radius=1)
    if enough():
        return ordered

    add_candidates(_representative_timeline_indices(sentences), radius=1)
    if enough():
        return ordered

    add_candidates(_dialogue_candidate_indices(sentences, matched_characters), radius=0)
    if enough():
        return ordered

    add_candidates(_thought_or_evaluation_indices(sentences, matched_characters), radius=0)
    return ordered


def _build_dense_hit_plan(
    character_hits: dict[str, list[int]],
    matched_characters: list[str],
    *,
    sample_cap: int,
) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    for name in matched_characters:
        for idx in _spread_sample_indices(character_hits.get(name, []), sample_cap=sample_cap):
            if idx in seen:
                continue
            seen.add(idx)
            ordered.append(idx)
    return ordered


def _representative_timeline_indices(sentences: list[str]) -> list[int]:
    if not sentences:
        return []
    total = len(sentences)
    points = [0, total // 2, total - 1]
    ordered: list[int] = []
    seen: set[int] = set()
    for idx in points:
        if idx in seen:
            continue
        seen.add(idx)
        ordered.append(idx)
    return ordered


def _dialogue_candidate_indices(sentences: list[str], characters: list[str]) -> list[int]:
    primary: list[int] = []
    secondary: list[int] = []
    for idx, sentence in enumerate(sentences):
        text = str(sentence or "").strip()
        if not text or not _looks_like_dialogue_sentence(text):
            continue
        if any(_sentence_mentions_character(text, name) for name in characters):
            primary.append(idx)
        else:
            secondary.append(idx)
    return primary + secondary


def _thought_or_evaluation_indices(sentences: list[str], characters: list[str]) -> list[int]:
    primary: list[int] = []
    secondary: list[int] = []
    for idx, sentence in enumerate(sentences):
        text = str(sentence or "").strip()
        if not text or not _looks_like_thought_or_evaluation_sentence(text):
            continue
        if any(_sentence_mentions_character(text, name) for name in characters):
            primary.append(idx)
        else:
            secondary.append(idx)
    return primary + secondary


def _looks_like_dialogue_sentence(text: str) -> bool:
    sample = str(text or "").strip()
    if not sample:
        return False
    if any(token in sample for token in ('"', "“", "”", "「", "」")):
        return True
    return bool(re.search(r"(说道|笑道|问道|答道|道：|道:|喊道|喝道|骂道|低声道|轻声道)", sample))


def _looks_like_thought_or_evaluation_sentence(text: str) -> bool:
    sample = str(text or "").strip()
    if not sample:
        return False
    return bool(
        re.search(
            r"(心想|心道|心里|想着|只觉|觉得|不禁|暗想|思忖|寻思|素来|向来|一向|生性|性子|为人|看似|其实|原是|本就)",
            sample,
        )
    )


def _build_excerpt_result(
    sentences: list[str],
    selected_indices: list[int],
    *,
    requested_characters: list[str],
    matched_characters: list[str],
    missing_characters: list[str],
    excerpt_strategy: str,
    max_chars: int | None = None,
) -> dict[str, Any]:
    excerpt = _render_excerpt_from_indices(sentences, selected_indices, max_chars=max_chars)
    return {
        "excerpt": excerpt,
        "requested_characters": requested_characters,
        "matched_characters": matched_characters,
        "missing_characters": missing_characters,
        "excerpt_strategy": excerpt_strategy,
        "excerpt_stages": _build_excerpt_stages(sentences, selected_indices),
    }


def _render_excerpt_from_indices(sentences: list[str], selected_indices: list[int], *, max_chars: int | None = None) -> str:
    selected_sentences = [
        sentences[idx][:max_chars].strip() if i == 0 and max_chars and len(sentences[idx]) > max_chars else sentences[idx]
        for i, idx in enumerate(selected_indices)
        if 0 <= idx < len(sentences)
    ]
    return "\n".join(item for item in selected_sentences if item.strip()).strip()


def _build_excerpt_stages(sentences: list[str], selected_indices: list[int]) -> dict[str, str]:
    if not selected_indices:
        return _empty_stage_blocks()
    ordered = sorted(idx for idx in selected_indices if 0 <= idx < len(sentences))
    minimum = ordered[0]
    maximum = ordered[-1]
    span = max(1, maximum - minimum)
    buckets: dict[str, list[str]] = {"start": [], "mid": [], "end": []}
    for idx in ordered:
        ratio = (idx - minimum) / span
        if ratio <= 0.34:
            stage = "start"
        elif ratio >= 0.67:
            stage = "end"
        else:
            stage = "mid"
        sentence = sentences[idx].strip()
        if sentence and sentence not in buckets[stage]:
            buckets[stage].append(sentence)
    return {
        "start": "\n".join(buckets["start"]).strip(),
        "mid": "\n".join(buckets["mid"]).strip(),
        "end": "\n".join(buckets["end"]).strip(),
    }


def _empty_stage_blocks() -> dict[str, str]:
    return {"start": "", "mid": "", "end": ""}


def _build_representative_hit_plan(
    character_hits: dict[str, list[int]],
    matched_characters: list[str],
    *,
    center_budget: int,
) -> list[int]:
    per_character = {
        name: _spread_sample_indices(
            character_hits.get(name, []),
            sample_cap=max(1, min(len(sorted(set(character_hits.get(name, [])))), center_budget)),
        )
        for name in matched_characters
    }
    ordered_centers: list[int] = []
    seen: set[int] = set()

    max_slots = max((len(indices) for indices in per_character.values()), default=0)
    for slot in range(max_slots):
        for name in matched_characters:
            indices = per_character.get(name, [])
            if slot >= len(indices):
                continue
            idx = indices[slot]
            if idx in seen:
                continue
            seen.add(idx)
            ordered_centers.append(idx)
            if len(ordered_centers) >= center_budget:
                return ordered_centers

    return ordered_centers


def _spread_sample_indices(indices: list[int], *, sample_cap: int) -> list[int]:
    unique = sorted(set(indices))
    if len(unique) <= sample_cap:
        return unique
    if sample_cap <= 1:
        return [unique[0]]

    samples: list[int] = []
    total = len(unique) - 1
    for slot in range(sample_cap):
        position = round((total * slot) / (sample_cap - 1))
        candidate = unique[position]
        if candidate not in samples:
            samples.append(candidate)
    return samples


def _candidate_indices_from_centers(centers: list[int], *, total_sentences: int) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    max_radius = _context_radius_for_centers(centers, total_sentences=total_sentences)
    for radius in range(0, max_radius + 1):
        for center in centers:
            for idx in _window_indices(center, total_sentences, radius=radius):
                if idx in seen:
                    continue
                seen.add(idx)
                ordered.append(idx)
    return ordered


def _context_radius_for_centers(centers: list[int], *, total_sentences: int) -> int:
    if not centers or total_sentences <= 0:
        return 1
    if len(centers) == 1:
        return 3
    if len(centers) <= 3:
        return 2
    return 1


def _window_indices(center: int, total: int, radius: int = 1) -> list[int]:
    start = max(0, center - radius)
    end = min(total, center + radius + 1)
    return list(range(start, end))
