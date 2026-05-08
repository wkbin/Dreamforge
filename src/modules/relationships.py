#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import itertools
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.core.config import Config
from src.core.contracts import (
    CostEstimator,
    PathProviderLike,
    RelationStore,
    RelationVisualizationExporter,
    RuleProvider,
    RuntimePartsLike,
)
from src.core.relation_store import MarkdownRelationStore
from src.core.relation_visualization_exporter import MermaidRelationVisualizationExporter
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
        relation_store: Optional[RelationStore] = None,
        relation_visualization_exporter: Optional[RelationVisualizationExporter] = None,
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
        self.relation_store = relation_store or MarkdownRelationStore(path_provider)
        self.relation_visualization_exporter = relation_visualization_exporter or MermaidRelationVisualizationExporter(self)
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

    @classmethod
    def from_runtime_parts(cls, parts: RuntimePartsLike) -> "RelationshipExtractor":
        return cls(
            parts.config,
            llm_client=parts.llm,
            token_counter=parts.token_counter,
            distiller=parts.distiller,
            rulebook=parts.rulebook,
            path_provider=parts.path_provider,
            relation_store=parts.relation_store,
            relation_visualization_exporter=parts.relation_visualization_exporter,
        )

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
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        text = self.distiller.prepare_novel_text(load_novel_text(novel_path))
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
        novel_id = novel_id_from_input(novel_path)
        self._emit_progress(progress_callback, "text_loaded", novel_id=novel_id, chunk_count=len(chunks))

        scoped_characters = [item.strip() for item in characters or [] if item.strip()] or self._load_existing_character_names(novel_id)
        if not scoped_characters:
            scoped_characters = self.distiller.extract_top_characters(text)
        self._emit_progress(
            progress_callback,
            "characters_ready",
            novel_id=novel_id,
            characters=list(scoped_characters),
            total=len(scoped_characters),
        )
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

        for idx, chunk in enumerate(chunks):
            self._emit_progress(
                progress_callback,
                "scanning_chunk",
                novel_id=novel_id,
                index=idx + 1,
                total=len(chunks),
            )
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
                "evidence_lines": self._dedupe_texts(bucket["interactions"], 3),
                "relation_change": self._infer_relation_change(trust, affection, conflict_penalty, interaction_bonus),
                "hidden_attitude": self._infer_hidden_attitude(
                    trust,
                    affection,
                    min(10, max(0, 5 - affection) + conflict_penalty),
                    self._mode_text(bucket["conflict_points"], default=""),
                ),
                "appellations": {
                    direction: self._mode_text(terms, default="")
                    for direction, terms in bucket["appellations"].items()
                    if self._mode_text(terms, default="")
                },
            }

        self._save_relations(final_relations, novel_id, output_path)
        self._export_relation_bundle(final_relations, novel_id)
        self._emit_progress(
            progress_callback,
            "rendering_graph",
            novel_id=novel_id,
            relation_count=len(final_relations),
        )
        self._export_relation_visualizations(final_relations, novel_id)
        self._emit_progress(
            progress_callback,
            "graph_done",
            novel_id=novel_id,
            relation_count=len(final_relations),
            html_path=str(self.path_provider.visualization_file(novel_id, ".html")),
            mermaid_path=str(self.path_provider.visualization_file(novel_id, ".mermaid.md")),
        )
        return final_relations

    @staticmethod
    def _emit_progress(
        callback: Optional[Callable[[str, Dict[str, Any]], None]],
        stage: str,
        **payload: Any,
    ) -> None:
        if callback is None:
            return
        callback(stage, payload)

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
        alias_map: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, List[str]]:
        alias_map = alias_map or {name: [name] for name in present}
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
        self.relation_store.save_relations(novel_id, relations, output_path=output_path)

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

    def _export_relation_visualizations(self, relations: Dict[str, Dict[str, Any]], novel_id: str) -> None:
        self.relation_visualization_exporter.export_visualizations(relations, novel_id)

    def _render_mermaid_graph(
        self,
        relations: Dict[str, Dict[str, Any]],
        *,
        node_styles: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        lines = ["graph LR"]
        node_styles = node_styles or {}
        node_classes: Dict[str, Dict[str, str]] = {}
        link_styles: List[str] = []

        for pair_key, payload in sorted(relations.items()):
            names = pair_key.split("_")
            if len(names) != 2:
                continue
            left, right = names
            trust = int(payload.get("trust", 5))
            affection = int(payload.get("affection", 5))
            hostility = int(payload.get("hostility", max(0, 5 - affection)))
            closeness = self._closeness_score(trust, affection)
            label = f"T{trust} A{affection} H{hostility}"
            lines.append(f"    {self._graph_id(left)}[{left}] ---|{label}| {self._graph_id(right)}[{right}]")
            node_classes[left] = node_styles.get(left, self._default_node_style())
            node_classes[right] = node_styles.get(right, self._default_node_style())
            link_styles.append(self._edge_style(trust, hostility, closeness))

        if len(lines) == 1:
            placeholder = self._default_node_style()
            lines.append("    empty[暂无关系数据]")
            node_classes["empty"] = {**placeholder, "class_name": "group_empty"}

        class_definitions: Dict[str, Dict[str, str]] = {}
        for name, style in sorted(node_classes.items()):
            class_name = style.get("class_name", "group_unknown")
            node_id = name if name == "empty" else self._graph_id(name)
            lines.append(f"    class {node_id} {class_name}")
            class_definitions[class_name] = style
        for class_name, style in sorted(class_definitions.items()):
            lines.append(
                "    classDef "
                f"{class_name} "
                f"fill:{style.get('fill', '#f3f4f6')},"
                f"stroke:{style.get('stroke', '#6b7280')},"
                f"color:{style.get('text', '#111827')},"
                "stroke-width:2px"
            )
        for index, style in enumerate(link_styles):
            lines.append(f"    linkStyle {index} {style}")
        return "\n".join(lines)

    def _render_relation_html(
        self,
        novel_id: str,
        relations: Dict[str, Dict[str, Any]],
        *,
        node_styles: Optional[Dict[str, Dict[str, str]]] = None,
        mermaid_graph: Optional[str] = None,
        mermaid_runtime_filename: str = "",
    ) -> str:
        node_styles = node_styles or {}
        rows: List[str] = []
        for pair_key, payload in sorted(relations.items()):
            trust = int(payload.get("trust", 5))
            affection = int(payload.get("affection", 5))
            hostility = int(payload.get("hostility", 0))
            power_gap = int(payload.get("power_gap", 0))
            closeness = self._closeness_score(trust, affection)
            conflict = html.escape(str(payload.get("conflict_point", "")))
            interaction = html.escape(str(payload.get("typical_interaction", "")))
            rows.append(
                "<tr>"
                f"<td><span class=\"pair-key\">{html.escape(pair_key)}</span></td>"
                f"<td>{self._metric_badge(trust, 'trust')}</td>"
                f"<td>{self._metric_badge(affection, 'affection')}</td>"
                f"<td>{self._metric_badge(hostility, 'hostility')}</td>"
                f"<td>{self._metric_badge(closeness, 'closeness')}</td>"
                f"<td>{power_gap}</td>"
                f"<td>{conflict or '<span class=\"muted\">-</span>'}</td>"
                f"<td>{interaction or '<span class=\"muted\">-</span>'}</td>"
                "</tr>"
            )
        if not rows:
            rows.append("<tr><td colspan=\"8\"><span class=\"muted\">暂无关系数据，生成后这里会显示图谱和明细。</span></td></tr>")

        mermaid = mermaid_graph or self._render_mermaid_graph(relations, node_styles=node_styles)
        escaped_mermaid = html.escape(mermaid)
        relation_count = len(relations)
        unique_categories: List[tuple[str, Dict[str, str]]] = []
        seen_categories = set()
        for style in node_styles.values():
            class_name = style.get("class_name", "group_unknown")
            if class_name in seen_categories:
                continue
            seen_categories.add(class_name)
            unique_categories.append((class_name, style))
        node_cards: List[str] = []
        for name, style in sorted(node_styles.items()):
            details = []
            faction = str(style.get("faction_position", "")).strip()
            role = str(style.get("story_role", "")).strip()
            if faction:
                details.append(f"阵营：{html.escape(faction)}")
            if role:
                details.append(f"角色：{html.escape(role)}")
            if not details:
                details.append("未标注阵营/角色")
            node_cards.append(
                "<li class=\"node-item\">"
                f"<span class=\"swatch\" style=\"background:{style.get('fill', '#f3f4f6')}; border-color:{style.get('stroke', '#6b7280')};\"></span>"
                "<div>"
                f"<strong>{html.escape(name)}</strong>"
                f"<span>{' / '.join(details)}</span>"
                "</div>"
                "</li>"
            )
        if not node_cards:
            node_cards.append("<li class=\"node-item muted\">暂无节点元数据</li>")
        category_legend = "".join(
            (
                "<span class=\"legend-item\">"
                f"<span class=\"swatch\" style=\"background:{style.get('fill', '#f3f4f6')}; border-color:{style.get('stroke', '#6b7280')};\"></span>"
                f"{html.escape(style.get('legend', '未标注阵营/角色'))}"
                "</span>"
            )
            for _, style in unique_categories
        )
        conflict_count = sum(1 for payload in relations.values() if int(payload.get("hostility", 0)) >= 6)
        runtime_script_tag = (
            f"  <script src=\"{html.escape(mermaid_runtime_filename)}\"></script>\n"
            "  <script>\n"
            "    mermaid.initialize({ startOnLoad: true, theme: 'base', securityLevel: 'loose', themeVariables: { primaryTextColor: '#1f2937', lineColor: '#7b5b34', primaryBorderColor: '#8a5a2b', clusterBorder: '#d6c7a7', fontFamily: 'Noto Serif SC, Source Han Serif SC, serif' } });\n"
            "  </script>\n"
            if mermaid_runtime_filename
            else ""
        )
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"zh-CN\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\" />\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
            f"  <title>{html.escape(novel_id)} relation graph</title>\n"
            "  <style>\n"
            "    :root { --bg:#f6efe2; --ink:#1f2937; --muted:#6b7280; --line:#d6c7a7; --card:#fffaf0; --warm:#8a5a2b; --trust:#156f55; --affection:#b4583a; --hostility:#b42318; }\n"
            "    * { box-sizing:border-box; }\n"
            "    body { font-family: 'Noto Serif SC', 'Source Han Serif SC', serif; margin: 0; background: radial-gradient(circle at top, #fff9ef, var(--bg)); color: var(--ink); }\n"
            "    .page { max-width: 1280px; margin: 0 auto; padding: 28px 20px 36px; }\n"
            "    h1 { margin: 0 0 8px; font-size: 32px; }\n"
            "    .subtitle { color: var(--muted); margin-bottom: 20px; }\n"
            "    .summary { display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }\n"
            "    .stat { background: linear-gradient(180deg, #fffdf8, #f7edd8); border:1px solid var(--line); border-radius: 14px; padding: 14px 16px; }\n"
            "    .stat-label { display:block; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }\n"
            "    .stat-value { font-size: 26px; color: var(--warm); }\n"
            "    .grid { display:grid; grid-template-columns: minmax(0, 1.35fr) minmax(340px, .95fr); gap: 18px; align-items:start; }\n"
            "    .card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 18px; box-shadow: 0 10px 35px rgba(90, 60, 20, .06); }\n"
            "    .card h2 { margin: 0 0 12px; font-size: 19px; }\n"
            "    .legend { display:flex; flex-wrap:wrap; gap:10px; margin: 4px 0 12px; }\n"
            "    .legend-item { display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; background:#fff; border:1px solid var(--line); font-size:13px; }\n"
            "    .swatch { width:12px; height:12px; border-radius:999px; display:inline-block; border:2px solid transparent; flex:0 0 auto; }\n"
            "    .edge-rule { display:grid; gap:10px; margin-top: 14px; }\n"
            "    .edge-rule strong { display:block; margin-bottom: 4px; }\n"
            "    .graph-shell { min-height: 480px; background: linear-gradient(180deg, #fffef9, #fcf5e8); border:1px dashed #dbc8a4; border-radius: 14px; padding: 12px; }\n"
            "    .mermaid { text-align:center; }\n"
            "    pre { white-space: pre-wrap; overflow-x: auto; background: #fffdf8; padding: 16px; border-radius: 12px; border:1px solid var(--line); }\n"
            "    details { margin-top: 16px; }\n"
            "    details summary { cursor: pointer; color: var(--warm); font-weight: 600; }\n"
            "    .node-list { list-style:none; margin:0; padding:0; display:grid; gap:10px; }\n"
            "    .node-item { display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:12px; background:#fffdf8; border:1px solid var(--line); }\n"
            "    .node-item strong { display:block; margin-bottom:4px; }\n"
            "    .node-item span { color: var(--muted); font-size: 13px; }\n"
            "    table { width: 100%; border-collapse: collapse; background: white; }\n"
            "    th, td { border: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }\n"
            "    th { background: #efe3c5; }\n"
            "    .pair-key { font-weight: 600; color: #4b3a28; }\n"
            "    .metric { display:inline-flex; min-width:40px; justify-content:center; padding:4px 10px; border-radius:999px; font-weight:700; color:#fff; }\n"
            "    .metric.trust { background: var(--trust); }\n"
            "    .metric.affection { background: var(--affection); }\n"
            "    .metric.hostility { background: var(--hostility); }\n"
            "    .metric.closeness { background: #6b7280; }\n"
            "    .muted { color: var(--muted); }\n"
            "    .note { color: var(--muted); font-size: 13px; margin-top: 10px; }\n"
            "    @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } .page { padding: 20px 14px 28px; } h1 { font-size: 26px; } }\n"
            "  </style>\n"
            f"{runtime_script_tag}"
            "</head>\n"
            "<body>\n"
            "  <div class=\"page\">\n"
            f"    <h1>{html.escape(novel_id)} 人物关系图谱</h1>\n"
            f"    <div class=\"subtitle\">共 {relation_count} 条关系。节点颜色优先按阵营，其次按角色类型；绿色边偏信任，红色边偏冲突，线越粗表示关系越亲密。</div>\n"
            "    <div class=\"summary\">\n"
            f"      <div class=\"stat\"><span class=\"stat-label\">Relations</span><span class=\"stat-value\">{relation_count}</span></div>\n"
            f"      <div class=\"stat\"><span class=\"stat-label\">High Trust</span><span class=\"stat-value\">{sum(1 for payload in relations.values() if int(payload.get('trust', 5)) >= 7)}</span></div>\n"
            f"      <div class=\"stat\"><span class=\"stat-label\">High Conflict</span><span class=\"stat-value\">{conflict_count}</span></div>\n"
            f"      <div class=\"stat\"><span class=\"stat-label\">Node Groups</span><span class=\"stat-value\">{max(1, len(unique_categories))}</span></div>\n"
            "    </div>\n"
            "    <div class=\"grid\">\n"
            "      <div class=\"card\">\n"
            "        <h2>关系网络</h2>\n"
            f"        <div class=\"legend\">{category_legend or '<span class=\"legend-item\">暂无阵营/角色元数据</span>'}</div>\n"
            "        <div class=\"graph-shell\">\n"
            f"          <div class=\"mermaid\">{html.escape(mermaid)}</div>\n"
            "        </div>\n"
            "        <div class=\"edge-rule\">\n"
            "          <div><strong>边的含义</strong><span class=\"muted\">绿色表示信任占优，红色表示冲突占优，棕色表示关系仍在拉扯或偏中性。</span></div>\n"
            "          <div><strong>线宽映射</strong><span class=\"muted\">线宽按亲密度计算，亲密度由 trust 与 affection 的均值近似映射到 1 到 5 级。</span></div>\n"
            "        </div>\n"
            "        <details>\n"
            "          <summary>查看 Mermaid 源码</summary>\n"
            f"          <pre>{escaped_mermaid}</pre>\n"
            "        </details>\n"
            "      </div>\n"
            "      <div class=\"card\">\n"
            "        <h2>节点说明</h2>\n"
            "        <ul class=\"node-list\">\n"
            f"          {''.join(node_cards)}\n"
            "        </ul>\n"
            "        <div class=\"note\">颜色来自人物画像中的 `faction_position` 或 `story_role`。如果两者都缺失，会回退为中性色。</div>\n"
            "      </div>\n"
            "    </div>\n"
            "    <div class=\"card\" style=\"margin-top:18px;\">\n"
            "      <h2>关系明细</h2>\n"
            "      <table>\n"
            "        <thead><tr><th>关系对</th><th>Trust</th><th>Affection</th><th>Hostility</th><th>Closeness</th><th>Power Gap</th><th>Conflict</th><th>Interaction</th></tr></thead>\n"
            f"        <tbody>{''.join(rows)}</tbody>\n"
            "      </table>\n"
            "    </div>\n"
            "  </div>\n"
            "</body>\n"
            "</html>\n"
        )

    @staticmethod
    def _default_node_style() -> Dict[str, str]:
        return {
            "class_name": "group_unknown",
            "legend": "未标注阵营/角色",
            "fill": "#f3f4f6",
            "stroke": "#6b7280",
            "text": "#111827",
            "faction_position": "",
            "story_role": "",
        }

    def _build_visual_node_styles(
        self,
        novel_id: str,
        relations: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, str]]:
        profile_metadata = self._load_profile_visual_metadata(novel_id)
        node_names = self._relation_node_names(relations)
        categories: List[str] = []
        node_styles: Dict[str, Dict[str, str]] = {}

        for name in node_names:
            profile = profile_metadata.get(name, {})
            category_key, legend = self._node_category(profile)
            if category_key not in categories:
                categories.append(category_key)
            node_styles[name] = {
                "category_key": category_key,
                "legend": legend,
                "faction_position": str(profile.get("faction_position", "")).strip(),
                "story_role": str(profile.get("story_role", "")).strip(),
            }

        palette_map: Dict[str, Dict[str, str]] = {}
        for index, category_key in enumerate(categories):
            palette = self._category_palette(index)
            palette_map[category_key] = {
                "class_name": f"group_{index}",
                "fill": palette["fill"],
                "stroke": palette["stroke"],
                "text": palette["text"],
            }

        fallback = self._default_node_style()
        for name, style in node_styles.items():
            style.update(palette_map.get(style.get("category_key", ""), fallback))

        return node_styles

    def _load_profile_visual_metadata(self, novel_id: str) -> Dict[str, Dict[str, str]]:
        root = self.path_provider.characters_root(novel_id)
        if not root.exists():
            return {}
        metadata: Dict[str, Dict[str, str]] = {}
        for persona_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            merged: Dict[str, str] = {}
            for filename in ("PROFILE.generated.md", "PROFILE.md"):
                profile_path = persona_dir / filename
                if not profile_path.exists():
                    continue
                merged.update(self._parse_profile_visual_metadata(profile_path))
            if merged:
                metadata[persona_dir.name] = merged
        return metadata

    @staticmethod
    def _parse_profile_visual_metadata(path: Path) -> Dict[str, str]:
        parsed: Dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in {"faction_position", "story_role"} and value:
                parsed[key] = value
        return parsed

    @staticmethod
    def _relation_node_names(relations: Dict[str, Dict[str, Any]]) -> List[str]:
        names = set()
        for pair_key in relations:
            parts = pair_key.split("_")
            if len(parts) != 2:
                continue
            names.update(parts)
        return sorted(names)

    @staticmethod
    def _node_category(profile: Dict[str, str]) -> tuple[str, str]:
        faction = str(profile.get("faction_position", "")).strip()
        if faction:
            return f"faction::{faction}", f"阵营: {faction}"
        role = str(profile.get("story_role", "")).strip()
        if role:
            return f"role::{role}", f"角色: {role}"
        return "unknown", "未标注阵营/角色"

    @staticmethod
    def _category_palette(index: int) -> Dict[str, str]:
        palette = [
            {"fill": "#dbeafe", "stroke": "#1d4ed8", "text": "#172554"},
            {"fill": "#dcfce7", "stroke": "#15803d", "text": "#14532d"},
            {"fill": "#fef3c7", "stroke": "#b45309", "text": "#78350f"},
            {"fill": "#fee2e2", "stroke": "#dc2626", "text": "#7f1d1d"},
            {"fill": "#e0f2fe", "stroke": "#0891b2", "text": "#164e63"},
            {"fill": "#ede9fe", "stroke": "#6d28d9", "text": "#4c1d95"},
        ]
        return palette[index % len(palette)]

    @staticmethod
    def _closeness_score(trust: int, affection: int) -> int:
        return max(1, min(5, int(round((trust + affection) / 4))))

    @staticmethod
    def _edge_style(trust: int, hostility: int, closeness: int) -> str:
        if hostility >= max(6, trust):
            color = "#b42318"
        elif trust >= 7:
            color = "#15803d"
        else:
            color = "#8a5a2b"
        width = 1 + closeness
        return f"stroke:{color},stroke-width:{width}px"

    @staticmethod
    def _metric_badge(value: int, kind: str) -> str:
        return f"<span class=\"metric {kind}\">{value}</span>"

    @staticmethod
    def _graph_id(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff]", "_", str(name))

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
                    f"- hidden_attitude: {payload.get('hidden_attitude', '')}",
                    f"- relation_change: {payload.get('relation_change', '')}",
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
    def _dedupe_texts(values: List[str], limit: int = 3) -> List[str]:
        deduped: List[str] = []
        seen = set()
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            deduped.append(text)
            if len(deduped) >= limit:
                break
        return deduped

    @staticmethod
    def _infer_relation_change(trust: int, affection: int, conflict_penalty: int, interaction_bonus: int) -> str:
        if conflict_penalty >= 2 and affection <= 4:
            return "恶化"
        if affection >= 7 and trust >= 7 and interaction_bonus >= 1:
            return "升温"
        if conflict_penalty >= 1 and affection >= 6:
            return "反复波动"
        return "固化"

    @staticmethod
    def _infer_hidden_attitude(trust: int, affection: int, hostility: int, conflict_point: str) -> str:
        if affection >= 7 and trust >= 6 and conflict_point:
            return "表面未必挑明，私下仍明显在意对方态度"
        if hostility >= 6:
            return "表面可以周旋，私下戒备和疏离感更重"
        if trust >= 7:
            return "嘴上未必多说，实际更愿意向对方让步或靠近"
        return ""

    @staticmethod
    def _pair_key(a: str, b: str) -> str:
        return "_".join(sorted([a, b]))
