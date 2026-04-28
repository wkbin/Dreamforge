#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import List


logger = logging.getLogger(__name__)


class TokenCounter:
    """Token counting and chunk splitting utility."""

    def __init__(self) -> None:
        self._encoder = None
        try:
            import tiktoken

            self._encoder = tiktoken.get_encoding("cl100k_base")
        except (ImportError, AttributeError, ValueError):
            logger.debug("tiktoken unavailable, falling back to heuristic token counting")
            self._encoder = None

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoder:
            return len(self._encoder.encode(text))
        # Fallback estimation for CJK-heavy text.
        return max(1, len(text) // 2)

    def split_by_tokens(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        if not text.strip():
            return []
        if chunk_size <= 0:
            return [text]
        overlap = max(0, min(overlap, chunk_size - 1))
        if self._encoder:
            token_ids = self._encoder.encode(text)
            chunks: List[str] = []
            step = chunk_size - overlap
            for start in range(0, len(token_ids), step):
                part = token_ids[start : start + chunk_size]
                if not part:
                    continue
                chunks.append(self._encoder.decode(part))
                if start + chunk_size >= len(token_ids):
                    break
            return chunks

        # Fallback: approximate chars by token ratio.
        char_chunk = chunk_size * 2
        char_overlap = overlap * 2
        step = max(1, char_chunk - char_overlap)
        chunks = []
        for start in range(0, len(text), step):
            piece = text[start : start + char_chunk]
            if not piece:
                continue
            chunks.append(piece)
            if start + char_chunk >= len(text):
                break
        return chunks
