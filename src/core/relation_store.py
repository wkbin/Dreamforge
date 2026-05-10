#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from src.core.contracts import PathProviderLike, RelationStore
from src.utils.file_utils import load_markdown_data, save_markdown_data


class MarkdownRelationStore(RelationStore):
    """Markdown-backed storage for novel-scoped relation graphs."""

    def __init__(self, path_provider: PathProviderLike):
        self.path_provider = path_provider

    def load_relations(self, novel_id: str, default: Any = None) -> Any:
        return load_markdown_data(self.path_provider.relations_file(novel_id), default=default)

    def save_relations(
        self,
        novel_id: str,
        relations: Dict[str, Dict[str, Any]],
        output_path: Optional[str] = None,
    ) -> None:
        if output_path:
            output = Path(output_path)
            path = output if output.suffix.lower() == ".md" else output / f"{novel_id}_relations.md"
        else:
            path = self.path_provider.relations_file(novel_id)

        save_markdown_data(
            path,
            {"novel_id": novel_id, "relations": relations},
            title="RELATION_GRAPH",
            summary=[
                f"- novel_id: {novel_id}",
                f"- relation_count: {len(relations)}",
            ],
        )

    def apply_dialogue_update(
        self,
        novel_id: str,
        *,
        pair_key: str,
        message: str,
        speaker: str = "",
        target: str = "",
    ) -> Dict[str, Any]:
        payload = self.load_relations(novel_id, default={"novel_id": novel_id, "relations": {}}) or {}
        relations = dict(payload.get("relations", {}) or {})
        current = dict(relations.get(pair_key, {}) or {})

        metrics = self._coerce_metrics(current)
        msg = str(message or "")
        positive_tokens: Sequence[str] = ("谢谢", "抱歉", "理解", "关心", "在意", "帮你", "信你", "一起")
        negative_tokens: Sequence[str] = ("滚", "讨厌", "厌恶", "闭嘴", "烦", "背叛", "威胁", "恨")
        uncertain_tokens: Sequence[str] = ("也许", "或许", "未必", "以后再说", "再看", "不一定")

        if any(token in msg for token in positive_tokens):
            metrics["trust"] = min(10, metrics["trust"] + 1)
            metrics["affection"] = min(10, metrics["affection"] + 1)
            metrics["hostility"] = max(0, metrics["hostility"] - 1)
        if any(token in msg for token in negative_tokens):
            metrics["hostility"] = min(10, metrics["hostility"] + 2)
            metrics["trust"] = max(0, metrics["trust"] - 1)
            metrics["affection"] = max(0, metrics["affection"] - 2)
        if any(token in msg for token in uncertain_tokens):
            metrics["ambiguity"] = min(10, metrics["ambiguity"] + 1)

        current.update(metrics)
        current.setdefault("evidence_lines", [])
        evidence_lines = current.get("evidence_lines", [])
        if not isinstance(evidence_lines, list):
            evidence_lines = []
        evidence_line = f"{speaker}->{target}: {msg}".strip(": ").strip()
        if evidence_line:
            evidence_lines.append(evidence_line[:220])
        current["evidence_lines"] = evidence_lines[-10:]

        current["updated_at"] = int(time.time())
        relations[pair_key] = current
        payload["relations"] = relations
        payload["novel_id"] = novel_id
        payload["conflicts"] = self.detect_conflicts(relations)
        save_markdown_data(
            self.path_provider.relations_file(novel_id),
            payload,
            title="RELATION_GRAPH",
            summary=[
                f"- novel_id: {novel_id}",
                f"- relation_count: {len(relations)}",
                f"- conflict_count: {len(payload.get('conflicts', []))}",
            ],
        )
        return current

    def detect_conflicts(self, relations: Dict[str, Dict[str, Any]]) -> list[Dict[str, Any]]:
        conflicts: list[Dict[str, Any]] = []
        for pair_key, relation in relations.items():
            if not isinstance(relation, dict):
                continue
            metrics = self._coerce_metrics(relation)
            trust = metrics["trust"]
            affection = metrics["affection"]
            hostility = metrics["hostility"]
            ambiguity = metrics["ambiguity"]

            tags: list[str] = []
            if trust >= 8 and hostility >= 6:
                tags.append("high_trust_high_hostility")
            if affection >= 8 and hostility >= 6:
                tags.append("high_affection_high_hostility")
            if ambiguity >= 8 and max(trust, affection, hostility) >= 8:
                tags.append("high_ambiguity_with_extreme_signal")
            if not tags:
                continue
            conflicts.append(
                {
                    "pair_key": pair_key,
                    "tags": tags,
                    "trust": trust,
                    "affection": affection,
                    "hostility": hostility,
                    "ambiguity": ambiguity,
                }
            )
        return conflicts

    @staticmethod
    def _coerce_metrics(relation: Dict[str, Any]) -> Dict[str, int]:
        def to_int(key: str, default: int) -> int:
            try:
                value = int(relation.get(key, default))
            except (TypeError, ValueError):
                value = default
            return max(0, min(10, value))

        return {
            "trust": to_int("trust", 5),
            "affection": to_int("affection", 5),
            "hostility": to_int("hostility", 0),
            "ambiguity": to_int("ambiguity", 3),
        }
