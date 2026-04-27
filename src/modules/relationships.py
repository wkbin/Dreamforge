#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import itertools
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.core.contracts import CostEstimator, PathProviderLike, RuleProvider
from src.modules.distillation import NovelDistiller
from src.utils.file_utils import novel_id_from_input, save_markdown_data
from src.utils.text_parser import load_novel_text, split_sentences
from src.utils.token_counter import TokenCounter


class RelationshipExtractor:
    """Extract pairwise relationship signals from a novel with rule-driven heuristics."""

    DEFAULT_APPELLATION_PATTERN = (
        r"(大哥|二哥|三哥|四哥|大姐|二姐|三姐|大弟|二弟|三弟|贤弟|兄长|哥哥|姐姐|妹妹|弟弟|"
        r"主公|将军|军师|丞相|先生|夫人|姑娘|公子)"
    )
    DEFAULT_SPEECH_VERBS = ("道", "说", "问", "答", "笑", "喝", "叹", "叫")

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        llm_client: Optional[CostEstimator] = None,
        token_counter: Optional[TokenCounter] = None,
        distiller: Optional[NovelDistiller] = None,
        rulebook: Optional[RuleProvider] = None,
        path_provider: Optional[PathProviderLike] = None,
    ):
        self.config = config or Config()
        if (
            llm_client is None
            or token_counter is None
            or distiller is None
            or rulebook is None
            or path_provider is None
        ):
            raise ValueError(
                "RelationshipExtractor requires injected llm_client, token_counter, distiller, rulebook, and path_provider"
            )
        self.path_provider = path_provider
        self.rulebook = rulebook
        self.llm_client = llm_client
        self.token_counter = token_counter
        self.distiller = distiller
        self._last_chunk_count = 0

        rules = self.rulebook.section("relationships")
        self.appellation_pattern = str(rules.get("appellation_pattern", self.DEFAULT_APPELLATION_PATTERN))
        self.speech_verbs = tuple(rules.get("speech_verbs", list(self.DEFAULT_SPEECH_VERBS)))
        self.positive_markers = tuple(rules.get("positive_markers", []))
        self.negative_markers = tuple(rules.get("negative_markers", []))
        self.power_markers = tuple(rules.get("power_markers", []))
        self.conflict_markers = tuple(rules.get("conflict_markers", []))
        self.ambiguous_appellations = set(rules.get("ambiguous_appellations", []))
        self.appellation_target_window = int(rules.get("appellation_target_window", 8))

    def estimate_cost(self, novel_path: str) -> float:
        text = self.distiller.prepare_novel_text(load_novel_text(novel_path))
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
        avg_chunk_tokens = self.token_counter.count(text) / max(1, len(chunks))
        total_prompt_tokens = int(len(chunks) * (avg_chunk_tokens + 200))
        synthetic_prompt = "x" * max(10, total_prompt_tokens // 2)
        return self.llm_client.estimate_cost(synthetic_prompt, expected_completion_ratio=0.25)

    def extract(
        self,
        novel_path: str,
        output_path: Optional[str] = None,
        characters: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        text = self.distiller.prepare_novel_text(load_novel_text(novel_path))
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
        novel_id = novel_id_from_input(novel_path)

        scoped_characters = [item.strip() for item in characters or [] if item.strip()] or self._load_existing_character_names(novel_id)
        if not scoped_characters:
            scoped_characters = self.distiller.extract_top_characters(text)
        alias_map = self.distiller.build_alias_map(text, scoped_characters, allow_sparse_alias=False)

        buckets: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "trust_samples": [],
                "affection_samples": [],
                "power_gap_samples": [],
                "conflict_points": [],
                "interactions": [],
                "appellations": defaultdict(list),
            }
        )

        for chunk in chunks:
            present = [
                name
                for name in scoped_characters
                if self.distiller.text_mentions_any_alias(chunk, alias_map.get(name, [name]))
            ]
            if len(present) < 2:
                continue

            pair_interactions = self._extract_pair_interactions(chunk, sorted(set(present)), alias_map)
            for a, b in itertools.combinations(sorted(set(present)), 2):
                key = self._pair_key(a, b)
                interactions = pair_interactions.get(key, [])
                if not interactions:
                    continue
                scores = self._score_relation("\n".join(interactions), a, b)
                bucket = buckets[key]
                bucket["trust_samples"].append(scores["trust"])
                bucket["affection_samples"].append(scores["affection"])
                bucket["power_gap_samples"].append(scores["power_gap"])
                if scores["conflict_point"]:
                    bucket["conflict_points"].append(scores["conflict_point"])
                bucket["interactions"].extend(interactions[:2])
                for direction, term in scores.get("appellations", {}).items():
                    if term:
                        bucket["appellations"][direction].append(term)

        final_relations: Dict[str, Dict[str, Any]] = {}
        for key in sorted(buckets.keys()):
            bucket = buckets[key]
            interaction_bonus = min(2, len(bucket["interactions"]) // 8)
            appellation_count = sum(len(terms) for terms in bucket["appellations"].values())
            appellation_bonus = 1 if appellation_count else 0
            conflict_penalty = min(3, (len(bucket["conflict_points"]) // 2) + (1 if bucket["conflict_points"] else 0))
            trust = max(
                0,
                min(
                    10,
                    self._avg_int(bucket["trust_samples"], default=5)
                    + min(1, interaction_bonus)
                    + appellation_bonus
                    - min(1, conflict_penalty),
                ),
            )
            affection = max(
                0,
                min(
                    10,
                    self._avg_int(bucket["affection_samples"], default=5)
                    + interaction_bonus
                    + appellation_bonus
                    - conflict_penalty,
                ),
            )
            final_relations[key] = {
                "trust": trust,
                "affection": affection,
                "power_gap": self._avg_int(bucket["power_gap_samples"], default=0),
                "hostility": min(10, max(0, 5 - affection) + conflict_penalty),
                "ambiguity": max(0, 7 - abs(affection - trust) - min(2, interaction_bonus)),
                "conflict_point": self._mode_text(bucket["conflict_points"], default="立场差异"),
                "typical_interaction": self._mode_text(bucket["interactions"], default="试探 -> 回应 -> 暂时收束"),
                "appellations": {
                    direction: self._mode_text(terms, default="")
                    for direction, terms in bucket["appellations"].items()
                    if self._mode_text(terms, default="")
                },
            }

        self._save_relations(final_relations, novel_id, output_path)
        self._export_relation_bundle(final_relations, novel_id)
        return final_relations

    def _chunk_text(self, text: str) -> List[str]:
        size = int(self.config.get("text_processing.chunk_size_tokens", 8000))
        overlap = int(self.config.get("text_processing.chunk_overlap_tokens", 200))
        return self.token_counter.split_by_tokens(text, size, overlap)

    def _load_existing_character_names(self, novel_id: str) -> List[str]:
        root = self.path_provider.characters_root(novel_id)
        if not root.exists():
            return []
        names: List[str] = []
        for path in sorted(root.iterdir()):
            if not path.is_dir():
                continue
            if (path / "PROFILE.md").exists() or (path / "PROFILE.generated.md").exists():
                names.append(path.name)
        return names

    def _extract_pair_interactions(
        self,
        chunk: str,
        present: List[str],
        alias_map: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
        sentences = split_sentences(chunk)
        pairs: Dict[str, List[str]] = defaultdict(list)
        for sentence in sentences:
            hit = [
                name
                for name in present
                if self.distiller.text_mentions_any_alias(sentence, alias_map.get(name, [name]))
            ]
            if len(hit) < 2:
                continue
            cleaned = re.sub(r"\s+", " ", sentence).strip()
            for a, b in itertools.combinations(sorted(set(hit)), 2):
                pairs[self._pair_key(a, b)].append(cleaned)
        return pairs

    def _score_relation(self, chunk: str, a: str, b: str) -> Dict[str, Any]:
        text = str(chunk or "")
        positive_hits = sum(text.count(token) for token in self.positive_markers)
        negative_hits = sum(text.count(token) for token in self.negative_markers)
        power_hits = sum(text.count(token) for token in self.power_markers)
        conflict_hits = [token for token in self.conflict_markers if token in text]
        trust = 5 + min(2, positive_hits) - min(3, negative_hits) - min(1, len(conflict_hits))
        affection = 5 + min(2, positive_hits) - min(2, negative_hits) - min(2, len(conflict_hits))
        power_gap = min(5, power_hits)
        conflict_point = conflict_hits[0] if conflict_hits else ""

        return {
            "trust": max(0, min(10, trust)),
            "affection": max(0, min(10, affection)),
            "power_gap": max(-5, min(5, power_gap)),
            "conflict_point": conflict_point,
            "appellations": self._extract_appellations(text, a, b),
        }

    def _extract_appellations(self, chunk: str, a: str, b: str) -> Dict[str, str]:
        results: Dict[str, str] = {}
        speech_pattern = "|".join(re.escape(item) for item in self.speech_verbs)
        for speaker, target in ((a, b), (b, a)):
            target_aliases = self._candidate_target_aliases(target)
            pattern = re.compile(
                rf"{re.escape(speaker)}[^“”\"']{{0,12}}(?:{speech_pattern})[^“”\"']{{0,4}}[“\"](?P<quote>[^”\"]+)"
            )
            for match in pattern.finditer(chunk):
                quote = match.group("quote").strip()
                alias_hit = next((alias for alias in target_aliases if quote.startswith(alias)), "")
                if alias_hit:
                    results[f"{speaker}->{target}"] = alias_hit
                    break

                title_match = re.match(rf"^(?P<title>{self.appellation_pattern})(?:[，,:：])?", quote)
                if not title_match:
                    continue

                title = title_match.group("title")
                if title in self.ambiguous_appellations:
                    window = quote[: self.appellation_target_window]
                    if any(alias in window for alias in target_aliases):
                        results[f"{speaker}->{target}"] = title
                        break
                    continue

                results[f"{speaker}->{target}"] = title
                break
        return results

    def _candidate_target_aliases(self, target: str) -> List[str]:
        aliases = [target]
        aliases.extend(self.distiller.candidate_aliases(target))
        return [item for item in self._unique_texts(aliases) if item]

    @staticmethod
    def _unique_texts(items: List[str]) -> List[str]:
        seen = set()
        results: List[str] = []
        for item in items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            results.append(text)
            seen.add(text)
        return results

    def _save_relations(
        self,
        relations: Dict[str, Dict[str, Any]],
        novel_id: str,
        output_path: Optional[str],
    ) -> None:
        if output_path:
            output = Path(output_path)
            if output.suffix.lower() == ".md":
                path = output
            else:
                path = output / f"{novel_id}_relations.md"
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

    def _export_relation_bundle(self, relations: Dict[str, Dict[str, Any]], novel_id: str) -> None:
        by_character: Dict[str, List[tuple[str, Dict[str, Any]]]] = defaultdict(list)
        for pair_key, payload in relations.items():
            names = pair_key.split("_")
            if len(names) != 2:
                continue
            left, right = names
            by_character[left].append((right, payload))
            by_character[right].append((left, payload))

        for character_name, items in by_character.items():
            persona_dir = self.path_provider.character_dir(novel_id, character_name)
            if not ((persona_dir / "PROFILE.md").exists() or (persona_dir / "PROFILE.generated.md").exists()):
                continue

            generated = persona_dir / "RELATIONS.generated.md"
            generated.write_text(self._render_relations_markdown(character_name, items), encoding="utf-8")
            editable = persona_dir / "RELATIONS.md"
            if not editable.exists():
                editable.write_text(self._render_relations_override_stub(character_name), encoding="utf-8")
            self.distiller.refresh_navigation(persona_dir, character_name)

    @staticmethod
    def _render_relations_markdown(character_name: str, items: List[tuple[str, Dict[str, Any]]]) -> str:
        lines = [
            "# RELATIONS",
            f"<!-- Generated target-specific relation overlays for {character_name}. -->",
            "",
        ]
        for target_name, payload in sorted(items, key=lambda item: item[0]):
            appellations = payload.get("appellations", {}) if isinstance(payload.get("appellations", {}), dict) else {}
            appellation_to_target = appellations.get(f"{character_name}->{target_name}", "")
            lines.extend(
                [
                    f"## {target_name}",
                    f"- trust: {payload.get('trust', 5)}",
                    f"- affection: {payload.get('affection', 5)}",
                    f"- power_gap: {payload.get('power_gap', 0)}",
                    f"- conflict_point: {payload.get('conflict_point', '')}",
                    f"- typical_interaction: {payload.get('typical_interaction', '')}",
                    f"- appellation_to_target: {appellation_to_target}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _render_relations_override_stub(character_name: str) -> str:
        return (
            "# RELATIONS\n"
            f"<!-- Manual relation overrides for {character_name}.\n"
            "Use sections like:\n"
            "## 某角色\n"
            "- trust: 8\n"
            "- affection: 6\n"
            "- power_gap: 1\n"
            "- conflict_point: 立场差异\n"
            "- typical_interaction: ...\n"
            "- appellation_to_target: ...\n"
            "-->\n"
        )

    @staticmethod
    def _avg_int(values: List[int], default: int) -> int:
        return int(round(sum(values) / len(values))) if values else default

    @staticmethod
    def _mode_text(values: List[str], default: str) -> str:
        if not values:
            return default
        counter = defaultdict(int)
        for value in values:
            if value:
                counter[value] += 1
        if not counter:
            return default
        return sorted(counter.items(), key=lambda item: item[1], reverse=True)[0][0]

    @staticmethod
    def _pair_key(a: str, b: str) -> str:
        return "_".join(sorted([a, b]))
