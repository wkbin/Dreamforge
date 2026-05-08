#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from src.core.exceptions import OptionalDependencyError, TextDecodingError


TEXT_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "gb18030",
    "gbk",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
)


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
        raise TextDecodingError("无法识别小说文本编码，请转换为 UTF-8 或 GB18030 后重试") from last_error
    raise TextDecodingError("无法读取小说文本")


def load_novel_text(path: str) -> str:
    novel_path = Path(path)
    if not novel_path.exists():
        raise FileNotFoundError(f"小说文件不存在: {path}")

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
        raise OptionalDependencyError("读取 .epub 需要安装 ebooklib") from exc

    book = epub.read_epub(str(path))
    chunks: List[str] = []
    for item in book.get_items():
        if item.get_type() == 9:  # ebooklib.ITEM_DOCUMENT
            html = item.get_content().decode("utf-8", errors="ignore")
            text = _strip_html_tags(html)
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[。！？!?])\s*", text)
    return [p.strip() for p in parts if p.strip()]
