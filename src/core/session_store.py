#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.core.contracts import PathProviderLike, SessionStore
from src.utils.file_utils import load_markdown_data, save_markdown_data


def _now_ts() -> int:
    return int(time.time())


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def _extract_tokens(text: str) -> list[str]:
    lowered = text.lower()
    return re.findall(r"[0-9a-z\u4e00-\u9fff]{2,}", lowered)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


@dataclass
class MemorySearchHit:
    text: str
    score: float
    metadata: Dict[str, Any]

    def to_payload(self) -> Dict[str, Any]:
        payload = {"text": self.text, "score": round(float(self.score), 6)}
        payload.update(dict(self.metadata or {}))
        return payload


class MarkdownSessionStore(SessionStore):
    """Markdown-backed session persistence for chat runtime state."""

    def __init__(self, path_provider: PathProviderLike):
        self.path_provider = path_provider
        self._local_vector_dimensions = 256

    def load_session(self, session_id: str, default: Any = None) -> Any:
        return load_markdown_data(self._session_path(session_id), default=default)

    def save_session(self, session: Dict[str, Any]) -> None:
        session_id = self._session_identity(session)
        if not session_id:
            raise ValueError("Session payload is missing id/session_id.")
        save_markdown_data(
            self._session_path(session_id),
            session,
            title="SESSION",
            summary=[
                f"- id: {session_id}",
                f"- novel_id: {session.get('novel_id', '')}",
                f"- mode: {session.get('mode', '')}",
            ],
        )

    def compress_context(
        self,
        session: Dict[str, Any],
        *,
        max_recent_turns: Optional[int] = None,
        summary_char_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        history = list(session.get("history", []) or [])
        if not history:
            return session

        cfg = self._memory_config()
        recent_turns = _clamp(max_recent_turns or cfg["recent_turns"], 4, 200)
        summary_limit = _clamp(summary_char_limit or cfg["summary_char_limit"], 80, 2000)
        if len(history) <= recent_turns:
            return session

        to_archive = history[:-recent_turns]
        keep = history[-recent_turns:]
        state = session.setdefault("state", {})
        memory_summary = dict(dict(state.get("memory", {}) or {}).get("summary", {}) or {})
        previous_summary = _normalize_text(memory_summary.get("summary", ""))
        compressed = self._build_memory_summary(previous_summary, to_archive, summary_limit)
        key_points = self._extract_key_points(to_archive, limit=8)

        state.setdefault("memory", {})["summary"] = {
            "summary": compressed,
            "key_points": key_points,
            "compressed_turns": len(to_archive),
            "recent_turns_kept": len(keep),
            "updated_at": _now_ts(),
        }
        session["history"] = keep

        session_id = self._session_identity(session)
        if session_id:
            for entry in to_archive:
                if bool(entry.get("memory_archived")):
                    continue
                text = self._entry_to_memory_text(entry)
                if not text:
                    continue
                metadata = {
                    "speaker": str(entry.get("speaker", "")).strip(),
                    "target": str(entry.get("target", "")).strip(),
                    "ts": int(entry.get("ts", 0) or 0),
                }
                self.append_long_term_memory(session_id, text, metadata=metadata)
                entry["memory_archived"] = True
        return session

    def append_long_term_memory(
        self,
        session_id: str,
        text: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        normalized = _normalize_text(text)
        if not session_id or not normalized:
            return
        memory_payload = self._load_long_term_payload(session_id)
        entries = list(memory_payload.get("entries", []) or [])
        if self._memory_entry_exists(entries, normalized, metadata):
            return
        item = {
            "id": f"mem-{_now_ts()}-{len(entries) + 1}",
            "text": normalized,
            "metadata": dict(metadata or {}),
            "vector": self._embed_local(normalized),
        }
        entries.append(item)
        max_entries = _clamp(int(self._memory_config().get("long_term_max_entries", 400) or 400), 20, 5000)
        if len(entries) > max_entries:
            entries = entries[-max_entries:]
        memory_payload["entries"] = entries
        memory_payload["session_id"] = session_id
        memory_payload["updated_at"] = _now_ts()
        save_markdown_data(
            self._long_term_memory_path(session_id),
            memory_payload,
            title="SESSION_LONG_TERM_MEMORY",
            summary=[
                f"- session_id: {session_id}",
                f"- entry_count: {len(entries)}",
            ],
        )
        self._upsert_pinecone_vector(session_id, item)

    def search_long_term_memory(self, session_id: str, query: str, *, top_k: int = 5) -> List[Dict[str, Any]]:
        normalized = _normalize_text(query)
        if not session_id or not normalized:
            return []
        limit = _clamp(top_k, 1, 50)
        pinecone_hits = self._search_pinecone(session_id, normalized, top_k=limit)
        if pinecone_hits:
            return [hit.to_payload() for hit in pinecone_hits]

        payload = self._load_long_term_payload(session_id)
        entries = list(payload.get("entries", []) or [])
        if not entries:
            return []
        query_vec = self._embed_local(normalized)
        scored: list[MemorySearchHit] = []
        for item in entries:
            text = _normalize_text(item.get("text", ""))
            if not text:
                continue
            item_vec = self._embed_local(text)
            score = self._cosine_similarity(query_vec, item_vec)
            scored.append(
                MemorySearchHit(
                    text=text,
                    score=score,
                    metadata=dict(item.get("metadata", {}) or {}),
                )
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return [hit.to_payload() for hit in scored[:limit]]

    def save_relation_snapshot(self, session: Dict[str, Any]) -> None:
        session_id = self._session_identity(session)
        if not session_id:
            raise ValueError("Session payload is missing id/session_id.")
        payload = {
            "session_id": session_id,
            "novel_id": session.get("novel_id"),
            "updated_at": session.get("updated_at"),
            "relation_matrix": dict(dict(session.get("state", {}).get("relations", {}) or {}).get("matrix", {}) or {}),
            "relation_delta": dict(dict(session.get("state", {}).get("relations", {}) or {}).get("delta", {}) or {}),
        }
        save_markdown_data(
            self._relation_snapshot_path(session_id),
            payload,
            title="SESSION_RELATIONS",
            summary=[
                f"- session_id: {session_id}",
                f"- novel_id: {session.get('novel_id', '')}",
            ],
        )

    def _session_path(self, session_id: str):
        return self.path_provider.sessions_dir() / f"{session_id}.md"

    def _relation_snapshot_path(self, session_id: str):
        return self.path_provider.sessions_dir() / f"{session_id}_relations.md"

    def _long_term_memory_path(self, session_id: str):
        return self.path_provider.sessions_dir() / f"{session_id}_memory.md"

    def _load_long_term_payload(self, session_id: str) -> Dict[str, Any]:
        return load_markdown_data(
            self._long_term_memory_path(session_id),
            default={"session_id": session_id, "entries": [], "updated_at": 0},
        ) or {"session_id": session_id, "entries": [], "updated_at": 0}

    def _memory_config(self) -> Dict[str, Any]:
        config = getattr(self.path_provider, "config", None)
        get = getattr(config, "get", None)
        if not callable(get):
            return {
                "recent_turns": 24,
                "summary_char_limit": 360,
                "long_term_max_entries": 400,
                "vector_provider": "local",
                "pinecone_api_key": "",
                "pinecone_index": "",
                "pinecone_namespace": "zaomeng",
            }
        return {
            "recent_turns": int(get("memory.recent_turns", 24) or 24),
            "summary_char_limit": int(get("memory.summary_char_limit", 360) or 360),
            "long_term_max_entries": int(get("memory.long_term_max_entries", 400) or 400),
            "vector_provider": str(get("memory.vector_provider", "local") or "local").strip().lower(),
            "pinecone_api_key": str(get("memory.pinecone_api_key", "") or "").strip(),
            "pinecone_index": str(get("memory.pinecone_index", "") or "").strip(),
            "pinecone_namespace": str(get("memory.pinecone_namespace", "zaomeng") or "zaomeng").strip() or "zaomeng",
        }

    def _entry_to_memory_text(self, entry: Dict[str, Any]) -> str:
        speaker = str(entry.get("speaker", "")).strip()
        message = _normalize_text(entry.get("message", ""))
        target = str(entry.get("target", "")).strip()
        if not message:
            return ""
        if speaker and target:
            return f"{speaker} -> {target}: {message}"
        if speaker:
            return f"{speaker}: {message}"
        return message

    @staticmethod
    def _session_identity(session: Dict[str, Any]) -> str:
        return str(session.get("id") or session.get("session_id") or "").strip()

    @staticmethod
    def _memory_entry_exists(entries: Sequence[Dict[str, Any]], text: str, metadata: Optional[Dict[str, Any]]) -> bool:
        incoming = dict(metadata or {})
        incoming_speaker = str(incoming.get("speaker", "")).strip()
        incoming_target = str(incoming.get("target", "")).strip()
        incoming_kind = str(incoming.get("kind", "")).strip()
        incoming_run_id = str(incoming.get("run_id", "")).strip()
        for entry in entries:
            if _normalize_text(entry.get("text", "")) != text:
                continue
            current_metadata = dict(entry.get("metadata", {}) or {})
            current_speaker = str(current_metadata.get("speaker", "")).strip()
            current_target = str(current_metadata.get("target", "")).strip()
            current_kind = str(current_metadata.get("kind", "")).strip()
            current_run_id = str(current_metadata.get("run_id", "")).strip()
            if current_speaker != incoming_speaker:
                continue
            if current_target != incoming_target:
                continue
            if incoming_kind and current_kind and current_kind != incoming_kind:
                continue
            if incoming_run_id and current_run_id and current_run_id != incoming_run_id:
                continue
            return True
        return False

    def _build_memory_summary(
        self,
        previous_summary: str,
        archived_entries: Sequence[Dict[str, Any]],
        summary_char_limit: int,
    ) -> str:
        snippets = [self._entry_to_memory_text(entry) for entry in archived_entries]
        snippets = [item for item in snippets if item]
        head = "；".join(snippets[:4])
        tail = "；".join(snippets[-4:])
        candidate = f"{previous_summary}；{head}；{tail}" if previous_summary else f"{head}；{tail}"
        condensed = re.sub(r"(；){2,}", "；", candidate).strip("； ")
        if len(condensed) <= summary_char_limit:
            return condensed
        return f"{condensed[:summary_char_limit].rstrip()}..."

    def _extract_key_points(self, archived_entries: Sequence[Dict[str, Any]], *, limit: int) -> List[str]:
        points: list[str] = []
        for entry in archived_entries:
            text = self._entry_to_memory_text(entry)
            if not text:
                continue
            normalized = text.strip()
            if normalized and normalized not in points:
                points.append(normalized)
            if len(points) >= limit:
                break
        return points[:limit]

    def _embed_local(self, text: str) -> List[float]:
        vec = [0.0] * self._local_vector_dimensions
        counts = Counter(_extract_tokens(text))
        if not counts:
            return vec
        for token, weight in counts.items():
            slot = self._stable_slot(token)
            vec[slot] += float(weight)
        norm = math.sqrt(sum(value * value for value in vec))
        if norm <= 0:
            return vec
        return [value / norm for value in vec]

    def _stable_slot(self, token: str) -> int:
        digest = hashlib.blake2b(str(token or "").encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self._local_vector_dimensions

    @staticmethod
    def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
        if not left or not right:
            return 0.0
        size = min(len(left), len(right))
        dot = 0.0
        left_norm = 0.0
        right_norm = 0.0
        for idx in range(size):
            lv = float(left[idx])
            rv = float(right[idx])
            dot += lv * rv
            left_norm += lv * lv
            right_norm += rv * rv
        if left_norm <= 0 or right_norm <= 0:
            return 0.0
        return dot / math.sqrt(left_norm * right_norm)

    def _pinecone_client(self) -> Tuple[Any, str, str] | None:
        cfg = self._memory_config()
        provider = cfg["vector_provider"]
        if provider not in {"pinecone", "pinecone-local-first"}:
            return None
        api_key = cfg["pinecone_api_key"]
        index_name = cfg["pinecone_index"]
        namespace = cfg["pinecone_namespace"]
        if not api_key or not index_name:
            return None
        try:
            pinecone_module = import_module("pinecone")
        except Exception:
            return None

        client = None
        index = None
        try:
            pinecone_cls = getattr(pinecone_module, "Pinecone", None)
            if pinecone_cls is not None:
                client = pinecone_cls(api_key=api_key)
                index = client.Index(index_name)
            else:
                init = getattr(pinecone_module, "init", None)
                index_factory = getattr(pinecone_module, "Index", None)
                if callable(init) and callable(index_factory):
                    init(api_key=api_key)
                    index = index_factory(index_name)
        except Exception:
            return None
        if index is None:
            return None
        return index, namespace, index_name

    def _upsert_pinecone_vector(self, session_id: str, item: Dict[str, Any]) -> None:
        pinecone = self._pinecone_client()
        if pinecone is None:
            return
        index, namespace, _ = pinecone
        vector = item.get("vector")
        if not isinstance(vector, list) or not vector:
            return
        metadata = dict(item.get("metadata", {}) or {})
        metadata["text"] = str(item.get("text", ""))[:2000]
        metadata["session_id"] = session_id
        try:
            index.upsert(
                vectors=[
                    {
                        "id": str(item.get("id", "")),
                        "values": [float(value) for value in vector],
                        "metadata": metadata,
                    }
                ],
                namespace=namespace,
            )
        except Exception:
            return

    def _search_pinecone(self, session_id: str, query: str, *, top_k: int) -> List[MemorySearchHit]:
        pinecone = self._pinecone_client()
        if pinecone is None:
            return []
        index, namespace, _ = pinecone
        try:
            response = index.query(
                vector=self._embed_local(query),
                top_k=top_k,
                include_metadata=True,
                namespace=namespace,
                filter={"session_id": {"$eq": session_id}},
            )
        except Exception:
            return []

        matches = getattr(response, "matches", None)
        if matches is None and isinstance(response, dict):
            matches = response.get("matches", [])
        results: list[MemorySearchHit] = []
        for item in matches or []:
            metadata = getattr(item, "metadata", None)
            score = getattr(item, "score", None)
            if isinstance(item, dict):
                metadata = item.get("metadata", metadata)
                score = item.get("score", score)
            metadata_payload = dict(metadata or {})
            text = _normalize_text(metadata_payload.pop("text", ""))
            if not text:
                continue
            results.append(
                MemorySearchHit(
                    text=text,
                    score=float(score or 0.0),
                    metadata=metadata_payload,
                )
            )
        return results
