#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import Config
from src.core.llm_client import LLMClient
from src.utils.file_utils import ensure_dir, novel_id_from_input, safe_filename, save_json
from src.utils.text_parser import load_novel_text, split_sentences
from src.utils.token_counter import TokenCounter


class NovelDistiller:
    """Novel character distillation with chunked processing."""

    STOP_NAMES = {
        "我们",
        "你们",
        "他们",
        "她们",
        "自己",
        "那里",
        "这里",
        "这个",
        "那个",
        "一种",
        "一个",
    }
    COMMON_SURNAMES = (
        "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
        "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费"
        "廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和"
        "穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜"
        "阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞"
        "万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程"
        "嵇邢滑裴陆荣翁荀羊惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山"
        "谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎"
    )

    TRAIT_KEYWORDS = {
        "勇敢": ["勇", "冲", "无畏", "果断"],
        "温柔": ["轻声", "温柔", "安慰", "体贴"],
        "聪慧": ["思索", "推断", "聪明", "机敏"],
        "敏感": ["委屈", "难过", "心酸", "叹息"],
        "傲气": ["冷笑", "不屑", "高傲", "轻蔑"],
        "忠诚": ["守护", "忠", "誓言", "不离"],
        "善良": ["帮助", "善意", "宽容", "谅解"],
        "执拗": ["坚持", "非要", "绝不", "固执"],
    }

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm_client = LLMClient(self.config)
        self.token_counter = TokenCounter()
        self._last_chunk_count = 0

    def estimate_cost(self, novel_path: str) -> float:
        text = load_novel_text(novel_path)
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
        # Add brief instruction overhead for each chunk.
        avg_chunk_tokens = self.token_counter.count(text) / max(1, len(chunks))
        total_prompt_tokens = int(len(chunks) * (avg_chunk_tokens + 250))
        synthetic_prompt = "x" * max(10, total_prompt_tokens // 2)
        return self.llm_client.estimate_cost(synthetic_prompt, expected_completion_ratio=0.35)

    def get_last_chunk_count(self) -> int:
        return self._last_chunk_count

    def distill(
        self,
        novel_path: str,
        characters: Optional[List[str]] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        text = load_novel_text(novel_path)
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
        novel_id = novel_id_from_input(novel_path)

        target_characters = [c.strip() for c in characters if c.strip()] if characters else None
        allow_sparse_alias = bool(target_characters)
        if not target_characters:
            target_characters = self._extract_top_characters(text)
            allow_sparse_alias = False
        if not target_characters:
            raise ValueError("No character candidates were extracted from the novel text")
        alias_map = self._build_alias_map(text, target_characters, allow_sparse_alias=allow_sparse_alias)

        aggregated = {name: self._empty_bucket() for name in target_characters}
        arc_points: Dict[str, List[Tuple[int, Dict[str, int]]]] = defaultdict(list)

        for idx, chunk in enumerate(chunks):
            chunk_evidence, chunk_values = self._extract_from_chunk(chunk, alias_map)
            for name in target_characters:
                bucket = aggregated[name]
                evidence = chunk_evidence.get(name)
                if not evidence:
                    continue
                bucket["descriptions"].extend(evidence["descriptions"])
                bucket["dialogues"].extend(evidence["dialogues"])
                bucket["thoughts"].extend(evidence["thoughts"])
                arc_points[name].append((idx, chunk_values.get(name, {})))

        profiles: Dict[str, Dict[str, Any]] = {}
        base_dir = Path(output_dir) if output_dir else Path(self.config.get_path("characters")) / novel_id
        out_dir = ensure_dir(base_dir)

        for name in target_characters:
            profile = self._build_profile(name, aggregated[name], arc_points.get(name, []))
            profile["novel_id"] = novel_id
            profile["source_path"] = novel_path
            profile["evidence"] = {
                "description_count": len(aggregated[name]["descriptions"]),
                "dialogue_count": len(aggregated[name]["dialogues"]),
                "thought_count": len(aggregated[name]["thoughts"]),
                "chunk_count": len(arc_points.get(name, [])),
            }
            profiles[name] = profile
            save_json(out_dir / f"{safe_filename(name)}.json", profile)

        return profiles

    def _chunk_text(self, text: str) -> List[str]:
        size = int(self.config.get("text_processing.chunk_size_tokens", 8000))
        overlap = int(self.config.get("text_processing.chunk_overlap_tokens", 200))
        return self.token_counter.split_by_tokens(text, size, overlap)

    def _extract_top_characters(self, text: str) -> List[str]:
        # Prefer surname-based 2-3 character full names.
        name_pattern = re.compile(rf"([{self.COMMON_SURNAMES}][\u4e00-\u9fff]{{1,2}})")
        raw = []
        for m in name_pattern.finditer(text):
            start = m.start()
            if start > 0 and "\u4e00" <= text[start - 1] <= "\u9fff":
                continue
            raw.append(m.group(1))
        disallowed_in_given = set("你我他她它们的了得地着过吗呀啊呢就在和并与把被让向对将又很都并且")
        candidates = []
        for n in raw:
            if n in self.STOP_NAMES:
                continue
            if len(n) < 2 or len(n) > 3:
                continue
            if any(ch in disallowed_in_given for ch in n[1:]):
                continue
            candidates.append(n)
        counts = Counter(candidates)

        filtered = []
        min_appearances = int(self.config.get("distillation.min_appearances", 3))
        for name, count in counts.most_common(60):
            if count < min_appearances:
                continue
            if self._looks_like_name(name):
                filtered.append(name)

        if not filtered:
            for name, count in counts.most_common(30):
                if count < 2:
                    continue
                if self._looks_like_name(name):
                    filtered.append(name)

        if not filtered:
            for name, count in counts.most_common(10):
                if count < 1:
                    continue
                if self._looks_like_name(name):
                    filtered.append(name)

        if len(filtered) < 2:
            for name, count in counts.most_common(20):
                if count < 1:
                    continue
                if not self._looks_like_name(name):
                    continue
                if name not in filtered:
                    filtered.append(name)
                if len(filtered) >= 5:
                    break

        # Alias supplementation (e.g. 宝玉/黛玉) when full-name data is sparse.
        if len(filtered) < 3:
            alias_candidates = re.findall(r"[\u4e00-\u9fff]{2}(?:儿|爷|姐|妹|兄|玉|钗)", text)
            alias_counts = Counter(alias_candidates)
            for alias, count in alias_counts.most_common(10):
                if count < 2:
                    continue
                if alias not in filtered and alias not in self.STOP_NAMES:
                    filtered.append(alias)

        max_characters = int(self.config.get("distillation.max_characters", 10))
        return filtered[:max_characters]

    def _build_alias_map(
        self,
        text: str,
        character_names: List[str],
        allow_sparse_alias: bool = False,
    ) -> Dict[str, List[str]]:
        alias_owners: Dict[str, List[str]] = defaultdict(list)
        for name in character_names:
            for alias in self._candidate_aliases(name):
                alias_owners[alias].append(name)

        alias_map: Dict[str, List[str]] = {}
        for name in character_names:
            aliases = [name]
            for alias in self._candidate_aliases(name):
                if alias_owners.get(alias) != [name]:
                    continue
                if not self._alias_is_reliable(text, alias, allow_sparse_alias=allow_sparse_alias):
                    continue
                aliases.append(alias)
            alias_map[name] = aliases
        return alias_map

    @staticmethod
    def _candidate_aliases(name: str) -> List[str]:
        if len(name) < 3:
            return []
        alias = name[-2:]
        if len(alias) < 2 or alias == name:
            return []
        return [alias]

    def _alias_is_reliable(self, text: str, alias: str, allow_sparse_alias: bool = False) -> bool:
        if len(alias) < 2 or alias in self.STOP_NAMES:
            return False
        min_mentions = 1 if allow_sparse_alias else 2
        return self._count_token_mentions(text, alias) >= min_mentions

    def _text_mentions_any_alias(self, text: str, aliases: List[str]) -> bool:
        return any(self._contains_token(text, alias) for alias in aliases)

    @staticmethod
    def _contains_token(text: str, token: str) -> bool:
        if not token:
            return False
        return token in text

    def _count_token_mentions(self, text: str, token: str) -> int:
        if not token:
            return 0
        return text.count(token)

    @staticmethod
    def _looks_like_name(name: str) -> bool:
        if len(name) < 2 or len(name) > 4:
            return False
        # Avoid common function words.
        bad = {"但是", "于是", "因为", "如果", "然后", "突然", "还是", "已经", "不能", "不会"}
        return name not in bad

    @staticmethod
    def _empty_bucket() -> Dict[str, List[str]]:
        return {"descriptions": [], "dialogues": [], "thoughts": []}

    def _extract_from_chunk(
        self, chunk: str, alias_map: Dict[str, List[str]]
    ) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, Dict[str, int]]]:
        sentences = split_sentences(chunk)
        evidence_map: Dict[str, Dict[str, List[str]]] = {}
        value_map: Dict[str, Dict[str, int]] = {}
        dims = self.config.get("distillation.values_dimensions", [])

        for name, aliases in alias_map.items():
            evidence = self._empty_bucket()
            values_acc: List[Dict[str, int]] = []

            for i, sent in enumerate(sentences):
                prev_sent = sentences[i - 1] if i > 0 else ""
                next_sent = sentences[i + 1] if i + 1 < len(sentences) else ""
                contains_name = self._text_mentions_any_alias(sent, aliases)
                pronoun_hit = any(p in sent for p in ("他", "她")) and (
                    self._text_mentions_any_alias(prev_sent, aliases)
                    or self._text_mentions_any_alias(next_sent, aliases)
                )
                if not (contains_name or pronoun_hit):
                    continue

                if "“" in sent or "\"" in sent:
                    evidence["dialogues"].append(sent)
                elif any(k in sent for k in ("心想", "想着", "觉得", "暗道", "心里")):
                    evidence["thoughts"].append(sent)
                else:
                    evidence["descriptions"].append(sent)
                values_acc.append(self._score_values(sent, dims))

            if any(evidence.values()):
                evidence_map[name] = evidence
                value_map[name] = self._average_values(values_acc, dims)

        return evidence_map, value_map

    @staticmethod
    def _score_values(sentence: str, dims: List[str]) -> Dict[str, int]:
        score = {d: 5 for d in dims}
        positive_markers = ("帮助", "保护", "坦诚", "承担", "勇敢", "坚持")
        negative_markers = ("欺骗", "逃避", "犹豫", "怯懦", "背叛", "冷酷")
        delta = 0
        if any(x in sentence for x in positive_markers):
            delta += 1
        if any(x in sentence for x in negative_markers):
            delta -= 1
        for d in dims:
            score[d] = max(0, min(10, score[d] + delta))
        return score

    @staticmethod
    def _average_values(values_list: List[Dict[str, int]], dims: List[str]) -> Dict[str, int]:
        if not values_list:
            return {d: 5 for d in dims}
        out: Dict[str, int] = {}
        for d in dims:
            avg = sum(v.get(d, 5) for v in values_list) / len(values_list)
            out[d] = int(round(avg))
        return out

    def _build_profile(
        self,
        name: str,
        bucket: Dict[str, List[str]],
        arc_values: List[Tuple[int, Dict[str, int]]],
    ) -> Dict[str, Any]:
        descriptions = self._dedupe(bucket["descriptions"], 24)
        dialogues = self._dedupe(bucket["dialogues"], 8)
        thoughts = self._dedupe(bucket["thoughts"], 12)

        core_traits = self._infer_traits(descriptions + thoughts)
        speech_style = self._infer_speech_style(dialogues)
        decision_rules = self._infer_decision_rules(thoughts, descriptions)
        values = self._merge_arc_values(arc_values)
        arc = self._build_arc(arc_values, values)

        return {
            "name": name,
            "core_traits": core_traits[:10],
            "values": values,
            "speech_style": speech_style,
            "typical_lines": dialogues[:8],
            "decision_rules": decision_rules[:8],
            "arc": arc,
        }

    def _infer_traits(self, lines: List[str]) -> List[str]:
        if not lines:
            return ["复杂", "克制"]
        text = " ".join(lines)
        hits = []
        for trait, keys in self.TRAIT_KEYWORDS.items():
            score = sum(text.count(k) for k in keys)
            if score > 0:
                hits.append((trait, score))
        if not hits:
            return ["谨慎", "多思"]
        hits.sort(key=lambda x: x[1], reverse=True)
        return [h[0] for h in hits[:10]]

    @staticmethod
    def _infer_speech_style(lines: List[str]) -> str:
        if not lines:
            return "叙述偏内敛，发言较少。"
        avg_len = sum(len(x) for x in lines) / len(lines)
        tone = "直白" if avg_len < 18 else "铺陈"
        emotional = "情绪外露" if any("！" in x or "?" in x or "？" in x for x in lines) else "克制"
        return f"语言{tone}，整体{emotional}。"

    @staticmethod
    def _infer_decision_rules(thoughts: List[str], descriptions: List[str]) -> List[str]:
        corpus = thoughts + descriptions
        rules: List[str] = []
        for line in corpus[:20]:
            if "如果" in line and "就" in line:
                rules.append("如果触发关键冲突→优先维护核心立场")
            elif any(k in line for k in ("保护", "守", "帮")):
                rules.append("同伴受压→倾向主动介入")
            elif any(k in line for k in ("退", "避", "沉默")):
                rules.append("局势失控→先压抑表达再观察")
        if not rules:
            rules = ["高压情境→先判断关系再行动"]
        return NovelDistiller._dedupe(rules, 8)

    def _merge_arc_values(self, arc_values: List[Tuple[int, Dict[str, int]]]) -> Dict[str, int]:
        dims = self.config.get("distillation.values_dimensions", [])
        if not arc_values:
            return {d: 5 for d in dims}
        merged = defaultdict(list)
        for _, values in arc_values:
            for d in dims:
                merged[d].append(values.get(d, 5))
        return {d: int(round(sum(vals) / len(vals))) for d, vals in merged.items()}

    def _build_arc(
        self, arc_values: List[Tuple[int, Dict[str, int]]], fallback_values: Dict[str, int]
    ) -> Dict[str, Any]:
        if not arc_values:
            return {
                "start": fallback_values,
                "mid": {**fallback_values, "trigger_event": "信息不足"},
                "end": {**fallback_values, "final_state": "信息不足"},
            }

        arc_values.sort(key=lambda x: x[0])
        start = arc_values[0][1] or fallback_values
        mid_idx = len(arc_values) // 2
        mid = arc_values[mid_idx][1] or fallback_values
        end = arc_values[-1][1] or fallback_values
        return {
            "start": start,
            "mid": {**mid, "trigger_event": "关键冲突推进"},
            "end": {**end, "final_state": "阶段性收束"},
        }

    @staticmethod
    def _dedupe(items: List[str], max_items: int) -> List[str]:
        seen = set()
        out = []
        for item in items:
            clean = re.sub(r"\s+", " ", item).strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            out.append(clean)
            if len(out) >= max_items:
                break
        return out
