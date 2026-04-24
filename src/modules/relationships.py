#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import itertools
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.core.llm_client import LLMClient
from src.modules.distillation import NovelDistiller
from src.utils.file_utils import ensure_dir, novel_id_from_input, save_json
from src.utils.text_parser import load_novel_text, split_sentences
from src.utils.token_counter import TokenCounter


class RelationshipExtractor:
    """Extract pairwise relationship graph from chunked novel text."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm_client = LLMClient(self.config)
        self.token_counter = TokenCounter()
        self.distiller = NovelDistiller(self.config)
        self._last_chunk_count = 0

    def estimate_cost(self, novel_path: str) -> float:
        text = load_novel_text(novel_path)
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
        avg_chunk_tokens = self.token_counter.count(text) / max(1, len(chunks))
        total_prompt_tokens = int(len(chunks) * (avg_chunk_tokens + 200))
        synthetic_prompt = "x" * max(10, total_prompt_tokens // 2)
        return self.llm_client.estimate_cost(synthetic_prompt, expected_completion_ratio=0.25)

    def extract(self, novel_path: str, output_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        text = load_novel_text(novel_path)
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
        novel_id = novel_id_from_input(novel_path)

        characters = self.distiller._extract_top_characters(text)
        alias_map = self.distiller._build_alias_map(text, characters, allow_sparse_alias=False)
        relation_buckets: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "trust_samples": [],
                "affection_samples": [],
                "power_gap_samples": [],
                "conflict_points": [],
                "interactions": [],
            }
        )

        for chunk in chunks:
            present = [name for name in characters if self.distiller._text_mentions_any_alias(chunk, alias_map[name])]
            if len(present) < 2:
                continue
            present = sorted(set(present))
            pair_interactions = self._extract_pair_interactions(chunk, present, alias_map=alias_map)

            for a, b in itertools.combinations(present, 2):
                key = "_".join(sorted([a, b]))
                interactions = pair_interactions.get(key, [])
                if not interactions:
                    continue
                evidence_text = "\n".join(interactions)
                scores = self._score_relation(evidence_text, a, b)
                bucket = relation_buckets[key]
                bucket["trust_samples"].append(scores["trust"])
                bucket["affection_samples"].append(scores["affection"])
                bucket["power_gap_samples"].append(scores["power_gap"])
                if scores["conflict_point"]:
                    bucket["conflict_points"].append(scores["conflict_point"])
                bucket["interactions"].extend(interactions[:2])

        final_relations: Dict[str, Dict[str, Any]] = {}
        for key in sorted(relation_buckets.keys()):
            b = relation_buckets[key]
            final_relations[key] = {
                "trust": self._avg_int(b["trust_samples"], default=5),
                "affection": self._avg_int(b["affection_samples"], default=5),
                "power_gap": self._avg_int(b["power_gap_samples"], default=0),
                "conflict_point": self._mode_text(b["conflict_points"], default="价值观差异"),
                "typical_interaction": self._mode_text(
                    b["interactions"], default="对话-试探-回应-暂时平衡"
                ),
            }

        self._save_relations(final_relations, novel_path, output_path, novel_id)
        return final_relations

    def _chunk_text(self, text: str) -> List[str]:
        size = int(self.config.get("text_processing.chunk_size_tokens", 8000))
        overlap = int(self.config.get("text_processing.chunk_overlap_tokens", 200))
        return self.token_counter.split_by_tokens(text, size, overlap)

    @staticmethod
    def _avg_int(values: List[int], default: int) -> int:
        if not values:
            return default
        return int(round(sum(values) / len(values)))

    @staticmethod
    def _mode_text(values: List[str], default: str) -> str:
        if not values:
            return default
        counter = defaultdict(int)
        for v in values:
            counter[v] += 1
        return sorted(counter.items(), key=lambda x: x[1], reverse=True)[0][0]

    def _extract_pair_interactions(
        self,
        chunk: str,
        present: List[str],
        alias_map: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, List[str]]:
        sents = split_sentences(chunk)
        pairs: Dict[str, List[str]] = defaultdict(list)
        alias_map = alias_map or {name: [name] for name in present}
        for sent in sents:
            hit = sorted(
                set(name for name in present if self.distiller._text_mentions_any_alias(sent, alias_map.get(name, [name])))
            )
            if len(hit) < 2:
                continue
            cleaned = re.sub(r"\s+", " ", sent).strip()
            for a, b in itertools.combinations(hit, 2):
                pairs["_".join([a, b])].append(cleaned)
        return pairs

    @staticmethod
    def _score_relation(chunk: str, a: str, b: str) -> Dict[str, Any]:
        local = chunk
        trust = 5
        affection = 5
        power_gap = 0
        conflict_point = ""

        positive = ("相信", "信任", "依靠", "照顾", "保护", "安慰", "和好")
        negative = ("怀疑", "争执", "误会", "冲突", "冷战", "责备", "怨")
        power_high = (f"{a}命令{b}", f"{b}命令{a}", "压制", "服从", "主导")
        conflict_markers = ("家族", "婚约", "利益", "权力", "秘密", "背叛")

        if any(x in local for x in positive):
            trust += 2
            affection += 2
        if any(x in local for x in negative):
            trust -= 2
            affection -= 1
        if any(x in local for x in power_high):
            power_gap += 2
        for c in conflict_markers:
            if c in local:
                conflict_point = c
                break

        return {
            "trust": max(0, min(10, trust)),
            "affection": max(0, min(10, affection)),
            "power_gap": max(-5, min(5, power_gap)),
            "conflict_point": conflict_point,
        }

    def _save_relations(
        self,
        relations: Dict[str, Dict[str, Any]],
        novel_path: str,
        output_path: Optional[str],
        novel_id: str,
    ) -> None:
        if not output_path:
            out_dir = ensure_dir(Path(self.config.get_path("relations")) / novel_id)
            file = out_dir / f"{novel_id}_relations.json"
            save_json(file, relations)
            return

        out = Path(output_path)
        if out.suffix.lower() == ".json":
            save_json(out, relations)
        else:
            out_dir = ensure_dir(out)
            save_json(out_dir / (Path(novel_path).stem + "_relations.json"), relations)
