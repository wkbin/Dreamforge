#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.core.config import Config
from src.core.contracts import CostEstimator, PathProviderLike, RuleProvider
from src.core.exceptions import ZaomengError
from src.utils.file_utils import canonical_aliases, ensure_dir, novel_id_from_input, safe_filename
from src.utils.text_parser import load_novel_text, split_sentences
from src.utils.token_counter import TokenCounter


class NovelDistiller:
    """Generic novel character distillation driven by editable markdown rules."""

    logger = logging.getLogger(__name__)

    CHAPTER_HEADING_PATTERNS = (
        re.compile(r"^第[0-9零一二三四五六七八九十百千两]+章"),
        re.compile(r"^第[0-9零一二三四五六七八九十百千两]+回"),
        re.compile(r"^卷[0-9零一二三四五六七八九十百千两]"),
        re.compile(r"^chapter\s+\d+", flags=re.IGNORECASE),
    )
    DEFAULT_NAV_LOAD_ORDER = (
        "SOUL",
        "GOALS",
        "STYLE",
        "TRAUMA",
        "IDENTITY",
        "BACKGROUND",
        "CAPABILITY",
        "BONDS",
        "CONFLICTS",
        "ROLE",
        "AGENTS",
        "RELATIONS",
        "MEMORY",
    )
    PERSONA_FILE_CATALOG = {
        "SOUL": {
            "optional": False,
            "role": "core values, worldview, boundaries",
            "behaviors": "stance, taboo, refusal, value judgment",
            "write_policy": "manual_edit",
        },
        "GOALS": {
            "optional": True,
            "role": "long-term drive, unresolved desire, strategic priority",
            "behaviors": "decision preference, long arc pressure, ambition",
            "write_policy": "manual_edit",
        },
        "STYLE": {
            "optional": True,
            "role": "signature phrasing, cadence, surface emotion, sample lines",
            "behaviors": "word choice, sentence length, tone, recurring fragments",
            "write_policy": "manual_edit",
        },
        "TRAUMA": {
            "optional": True,
            "role": "pain points, scars, triggers, never-do rules",
            "behaviors": "trigger reactions, avoidance, hard boundaries",
            "write_policy": "manual_edit",
        },
        "IDENTITY": {
            "optional": False,
            "role": "background, lived experience, habits, emotion profile",
            "behaviors": "self-reference, memory framing, habit-driven reactions",
            "write_policy": "manual_edit",
        },
        "BACKGROUND": {
            "optional": True,
            "role": "world identity, faction position, environment imprint, survival context",
            "behaviors": "camp alignment, social rank, environmental pressure, worldview fit",
            "write_policy": "manual_edit",
        },
        "CAPABILITY": {
            "optional": True,
            "role": "strengths, weaknesses, blind spots, action tendency",
            "behaviors": "what the character is good at, where they fail, how they overreach",
            "write_policy": "manual_edit",
        },
        "BONDS": {
            "optional": True,
            "role": "relationship habits, trust boundary, reward-and-resentment logic",
            "behaviors": "how the character treats allies, strangers, enemies, and debts",
            "write_policy": "manual_edit",
        },
        "CONFLICTS": {
            "optional": True,
            "role": "hidden desire, inner contradiction, fear triggers, private self",
            "behaviors": "internal pull, weakness exposure, private vs public self",
            "write_policy": "manual_edit",
        },
        "ROLE": {
            "optional": True,
            "role": "story function, stance stability, world-rule compatibility",
            "behaviors": "plot pressure, pivot role, alignment stability",
            "write_policy": "manual_edit",
        },
        "AGENTS": {
            "optional": False,
            "role": "runtime behavior rules, silence policy, group chat routing",
            "behaviors": "when to speak, when to hold back, how to engage others",
            "write_policy": "manual_edit",
        },
        "RELATIONS": {
            "optional": True,
            "role": "target-specific trust, affection, appellations, friction points",
            "behaviors": "tone toward each character, appellations, conflict framing",
            "write_policy": "manual_edit",
        },
        "MEMORY": {
            "optional": False,
            "role": "stable notes plus runtime write-back from user guidance and corrections",
            "behaviors": "persistent user constraints, correction carry-over, mutable notes",
            "write_policy": "runtime_append",
        },
    }

    DEFAULT_ADDRESS_SUFFIXES = ("哥哥", "姐姐", "妹妹", "弟弟", "姑娘", "公子", "爷")
    DEFAULT_SPEECH_VERBS = ("道", "说道", "笑道", "问道", "答道", "喝道", "叫道", "叹道", "呼道")
    DEFAULT_OBJECT_LEADERS = (
        "叫",
        "唤",
        "问",
        "对",
        "向",
        "同",
        "与",
        "跟",
        "把",
        "将",
        "扯住",
        "拉住",
        "搀起",
        "扶起",
        "扶着",
        "呼",
        "忙呼",
        "喝住",
        "捉住",
        "拿住",
        "推着",
        "拖着",
        "请",
        "教",
    )
    DEFAULT_STOP_NAMES = {
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
    DEFAULT_COMMON_SURNAMES = (
        "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚"
        "范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元"
        "卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强"
        "贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁"
        "单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山"
        "谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎"
    )
    DEFAULT_TRAIT_KEYWORDS = {
        "勇敢": ["勇", "冲", "无畏", "果断"],
        "温柔": ["轻声", "温和", "安慰", "体贴"],
        "聪慧": ["思索", "推断", "聪明", "机敏"],
        "敏感": ["委屈", "难过", "心酸", "叹息"],
        "傲气": ["冷笑", "不屑", "高傲", "轻蔑"],
        "忠诚": ["守护", "忠", "誓言", "不离"],
        "善良": ["帮助", "善意", "宽容", "谅解"],
        "执拗": ["坚持", "非要", "绝不", "固执"],
        "机变": ["变化", "试探", "识破", "周旋"],
        "诙谐": ["笑道", "打趣", "顽皮", "戏弄"],
        "虔诚": ["佛", "祈祷", "经文", "戒律"],
        "沉稳": ["稳住", "接应", "收拾", "不慌"],
        "圆滑": ["不如", "且慢", "何必", "先看看"],
        "克制": ["沉住气", "先忍", "不动声色", "收着"],
    }

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        llm_client: Optional[CostEstimator] = None,
        token_counter: Optional[TokenCounter] = None,
        rulebook: Optional[RuleProvider] = None,
        path_provider: Optional[PathProviderLike] = None,
    ):
        self.config = config or Config()
        if llm_client is None or token_counter is None or rulebook is None or path_provider is None:
            raise ValueError("NovelDistiller requires injected llm_client, token_counter, rulebook, and path_provider")
        self.path_provider = path_provider
        self.rulebook = rulebook
        self.llm_client = llm_client
        self.token_counter = token_counter
        self._last_chunk_count = 0

        self.address_suffixes = tuple(
            self.rulebook.get("distillation", "address_suffixes", list(self.DEFAULT_ADDRESS_SUFFIXES))
        )
        self.speech_verbs = tuple(
            self.rulebook.get("distillation", "speech_verbs", list(self.DEFAULT_SPEECH_VERBS))
        )
        self.object_leaders = tuple(
            self.rulebook.get("distillation", "object_leaders", list(self.DEFAULT_OBJECT_LEADERS))
        )
        self.stop_names = set(self.rulebook.get("distillation", "stop_names", list(self.DEFAULT_STOP_NAMES)))
        self.common_surnames = str(
            self.rulebook.get("distillation", "common_surnames", self.DEFAULT_COMMON_SURNAMES)
        )
        self.trait_keywords = dict(
            self.rulebook.get("distillation", "trait_keywords", self.DEFAULT_TRAIT_KEYWORDS)
        )
        self.archetypes = dict(self.rulebook.get("distillation", "archetypes", {}))
        self.value_markers = dict(self.rulebook.get("distillation", "value_markers", {}))
        speaker_rules = self.rulebook.section("speaker")
        self.generic_fillers = tuple(speaker_rules.get("generic_fillers", []))
        self.signature_fragments = tuple(speaker_rules.get("signature_fragments", []))
        self.opener_patterns = tuple(speaker_rules.get("opener_patterns", []))
        self.connective_patterns = tuple(speaker_rules.get("connective_patterns", []))
        self.ending_patterns = tuple(speaker_rules.get("ending_patterns", []))
        self.fragment_stopwords = {
            str(item).strip() for item in speaker_rules.get("fragment_stopwords", []) if str(item).strip()
        }
        self.preferred_leading_chars = tuple(speaker_rules.get("preferred_leading_chars", []))
        self.preferred_trailing_chars = tuple(speaker_rules.get("preferred_trailing_chars", []))
        self.style_templates = dict(self.rulebook.get("distillation", "style_templates", {}))
        self.decision_rule_signals = dict(self.rulebook.get("distillation", "decision_rule_signals", {}))
        self.taboo_topics_by_value = dict(self.rulebook.get("distillation", "taboo_topics_by_value", {}))
        self.forbidden_behaviors_by_value = dict(
            self.rulebook.get("distillation", "forbidden_behaviors_by_value", {})
        )
        self.second_pass_mode = str(self.config.get("distillation.second_pass_mode", "auto")).strip().lower()
        self.stage_window_size = int(self.config.get("distillation.stage_window_size", 6))
        self.llm_evidence_lines_per_stage = int(self.config.get("distillation.llm_evidence_lines_per_stage", 6))

    def estimate_cost(self, novel_path: str) -> float:
        text = self.prepare_novel_text(load_novel_text(novel_path))
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
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
        text = self.prepare_novel_text(load_novel_text(novel_path))
        chunks = self._chunk_text(text)
        self._last_chunk_count = len(chunks)
        novel_id = novel_id_from_input(novel_path)

        target_characters = [item.strip() for item in characters or [] if item.strip()] or self.extract_top_characters(text)
        if not target_characters:
            raise ValueError("No character candidates were extracted from the novel text")

        alias_map = self.build_alias_map(text, target_characters, allow_sparse_alias=bool(characters))
        aggregated = {name: self._empty_bucket() for name in target_characters}
        arc_points: Dict[str, List[Tuple[int, Dict[str, int]]]] = defaultdict(list)

        for idx, chunk in enumerate(chunks):
            chunk_evidence, chunk_values = self._extract_from_chunk(chunk, alias_map)
            for name in target_characters:
                evidence = chunk_evidence.get(name)
                if not evidence:
                    continue
                bucket = aggregated[name]
                bucket["descriptions"].extend(evidence["descriptions"])
                bucket["dialogues"].extend(evidence["dialogues"])
                bucket["thoughts"].extend(evidence["thoughts"])
                bucket["timeline"].append(
                    {
                        "index": idx,
                        "descriptions": list(evidence["descriptions"]),
                        "dialogues": list(evidence["dialogues"]),
                        "thoughts": list(evidence["thoughts"]),
                    }
                )
                arc_points[name].append((idx, chunk_values.get(name, {})))

        out_dir = ensure_dir(Path(output_dir) if output_dir else self.path_provider.characters_root(novel_id))
        profiles: Dict[str, Dict[str, Any]] = {}
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
            profile = self._refine_profile_with_llm(
                profile,
                bucket=aggregated[name],
                arc_values=arc_points.get(name, []),
            )
            profile["novel_id"] = novel_id
            profile["source_path"] = novel_path
            profiles[name] = profile
            self._export_persona_bundle(out_dir, profile)
        return profiles

    def extract_top_characters(self, text: str) -> List[str]:
        return self._extract_top_characters(self.prepare_novel_text(text))

    def build_alias_map(
        self,
        text: str,
        character_names: List[str],
        allow_sparse_alias: bool = False,
    ) -> Dict[str, List[str]]:
        return self._build_alias_map(self.prepare_novel_text(text), character_names, allow_sparse_alias=allow_sparse_alias)

    def text_mentions_any_alias(self, text: str, aliases: List[str]) -> bool:
        return self._text_mentions_any_alias(text, aliases)

    def refresh_navigation(self, persona_dir: Path, character_name: str) -> None:
        self.refresh_persona_navigation(persona_dir, character_name)

    def candidate_aliases(self, name: str) -> List[str]:
        clean = str(name or "").strip()
        aliases: List[str] = []
        aliases.extend(canonical_aliases(clean))
        if len(clean) >= 3:
            given = clean[-2:]
            if given != clean:
                aliases.append(given)
                for suffix in self.address_suffixes:
                    aliases.append(f"{given[0]}{suffix}")
                    aliases.append(f"{clean[0]}{suffix}")
        elif len(clean) == 2:
            for suffix in self.address_suffixes:
                aliases.append(f"{clean[0]}{suffix}")
        return self._unique_texts(item for item in aliases if item and item != clean)

    def prepare_novel_text(self, text: str) -> str:
        return self._prepare_novel_text(text)

    def _chunk_text(self, text: str) -> List[str]:
        size = int(self.config.get("text_processing.chunk_size_tokens", 8000))
        overlap = int(self.config.get("text_processing.chunk_overlap_tokens", 200))
        return self.token_counter.split_by_tokens(text, size, overlap)

    def _extract_top_characters(self, text: str) -> List[str]:
        name_pattern = re.compile(rf"([{self.common_surnames}][\u4e00-\u9fff]{{1,2}})")
        raw_names: List[str] = []
        for match in name_pattern.finditer(text):
            start = match.start()
            if start > 0 and "\u4e00" <= text[start - 1] <= "\u9fff":
                continue
            raw_names.append(match.group(1))

        disallowed = set("你我他她它们的了得地着过吗呀啊呢就在和并与把被让向对将又很都并且")
        candidates = []
        for name in raw_names:
            if name in self.stop_names or len(name) < 2 or len(name) > 3:
                continue
            if any(ch in disallowed for ch in name[1:]):
                continue
            candidates.append(name)

        counts = Counter(candidates)
        filtered = self._pick_frequent_names(counts, min_count=int(self.config.get("distillation.min_appearances", 3)))
        if not filtered:
            filtered = self._pick_frequent_names(counts, min_count=2)
        if not filtered:
            filtered = self._pick_frequent_names(counts, min_count=1)

        if len(filtered) < 3:
            alias_candidates = re.findall(r"[\u4e00-\u9fff]{2}(?:儿|爷|姐|妹|兄|玉|钗)", text)
            for alias, count in Counter(alias_candidates).most_common(10):
                if count < 2 or alias in self.stop_names or alias in filtered:
                    continue
                filtered.append(alias)

        return filtered[: int(self.config.get("distillation.max_characters", 10))]

    def _pick_frequent_names(self, counts: Counter[str], min_count: int) -> List[str]:
        filtered: List[str] = []
        for name, count in counts.most_common(60):
            if count < min_count:
                continue
            if self._looks_like_name(name):
                filtered.append(name)
        return filtered

    def _build_alias_map(
        self,
        text: str,
        character_names: List[str],
        allow_sparse_alias: bool = False,
    ) -> Dict[str, List[str]]:
        alias_owners: Dict[str, List[str]] = defaultdict(list)
        for name in character_names:
            for alias in self.candidate_aliases(name):
                alias_owners[alias].append(name)

        alias_map: Dict[str, List[str]] = {}
        for name in character_names:
            aliases = [name]
            for alias in self.candidate_aliases(name):
                if alias_owners.get(alias) != [name]:
                    continue
                if not self._alias_is_reliable(text, alias, allow_sparse_alias=allow_sparse_alias):
                    continue
                aliases.append(alias)
            alias_map[name] = self._unique_texts(aliases)
        return alias_map

    def _alias_is_reliable(self, text: str, alias: str, allow_sparse_alias: bool = False) -> bool:
        if len(alias) < 2 or alias in self.stop_names:
            return False
        min_mentions = 1 if allow_sparse_alias else 2
        return self._count_token_mentions(text, alias) >= min_mentions

    def _extract_from_chunk(
        self,
        chunk: str,
        alias_map: Dict[str, List[str]],
    ) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, Dict[str, int]]]:
        sentences = split_sentences(chunk)
        evidence_map: Dict[str, Dict[str, List[str]]] = {}
        value_map: Dict[str, Dict[str, int]] = {}
        dims = self._value_dimensions()

        for name, aliases in alias_map.items():
            evidence = self._empty_bucket()
            values_acc: List[Dict[str, int]] = []

            for idx, sentence in enumerate(sentences):
                if self._looks_like_metadata_sentence(sentence):
                    continue
                prev_sent = sentences[idx - 1] if idx > 0 else ""
                next_sent = sentences[idx + 1] if idx + 1 < len(sentences) else ""
                contains_name = self._text_mentions_any_alias(sentence, aliases)
                pronoun_hit = any(token in sentence for token in ("他", "她")) and (
                    self._text_mentions_any_alias(prev_sent, aliases) or self._text_mentions_any_alias(next_sent, aliases)
                )
                has_quote = "“" in sentence or "\"" in sentence
                speaker_hit = has_quote and self._is_likely_spoken_by(sentence, aliases, prev_sent, next_sent)

                if not (contains_name or pronoun_hit or speaker_hit):
                    continue

                if has_quote and speaker_hit:
                    spoken = self._extract_spoken_content(sentence, aliases, prev_sent, next_sent)
                    if spoken:
                        evidence["dialogues"].append(spoken)
                        values_acc.append(self._score_values(spoken, dims))
                    continue

                if any(token in sentence for token in ("心想", "想着", "觉得", "暗道", "心里")):
                    evidence["thoughts"].append(sentence)
                else:
                    evidence["descriptions"].append(sentence)
                values_acc.append(self._score_values(sentence, dims))

            if any(evidence.values()):
                evidence_map[name] = {
                    key: self._dedupe_texts(items, limit=24 if key == "descriptions" else 12)
                    for key, items in evidence.items()
                }
                value_map[name] = self._average_values(values_acc, dims)

        return evidence_map, value_map

    def _score_values(self, sentence: str, dims: List[str]) -> Dict[str, int]:
        score = {dim: 5 for dim in dims}
        for dim in dims:
            config = self.value_markers.get(dim, {})
            positive = sum(sentence.count(token) for token in config.get("positive", []))
            negative = sum(sentence.count(token) for token in config.get("negative", []))
            delta = min(3, positive) - min(3, negative)
            score[dim] = max(1, min(10, score[dim] + delta))
        return score

    @staticmethod
    def _average_values(values_list: List[Dict[str, int]], dims: List[str]) -> Dict[str, int]:
        if not values_list:
            return {dim: 5 for dim in dims}
        averaged: Dict[str, int] = {}
        for dim in dims:
            averaged[dim] = int(round(sum(item.get(dim, 5) for item in values_list) / len(values_list)))
        return averaged

    def _build_profile(
        self,
        name: str,
        bucket: Dict[str, List[str]],
        arc_values: List[Tuple[int, Dict[str, int]]],
    ) -> Dict[str, Any]:
        descriptions = self._dedupe_texts(bucket["descriptions"], 24)
        dialogues = self._dedupe_texts(bucket["dialogues"], 8)
        thoughts = self._dedupe_texts(bucket["thoughts"], 12)
        timeline = list(bucket.get("timeline", []))
        archetype = self._infer_archetype(name, descriptions, dialogues, thoughts)
        values = self._infer_values_from_corpus(self._merge_arc_values(arc_values), descriptions, dialogues, thoughts, archetype)
        core_traits = self._infer_traits(descriptions + dialogues + thoughts, archetype)
        speech_style = self._infer_speech_style(dialogues, archetype)
        decision_rules = self._infer_decision_rules(thoughts, descriptions, dialogues, archetype)
        arc = self._build_arc(arc_values, values, timeline)
        identity_anchor = self._infer_identity_anchor(core_traits, values, decision_rules, archetype)
        soul_goal = self._infer_soul_goal(values, core_traits, archetype)
        life_experience = self._infer_life_experience(descriptions, dialogues, thoughts, decision_rules, values, archetype)
        worldview = self._infer_worldview(values, core_traits, archetype)
        thinking_style = self._infer_thinking_style(values, core_traits, speech_style, archetype)
        speech_habits = self._infer_speech_habits(dialogues, speech_style)
        emotion_profile = self._infer_emotion_profile(dialogues, thoughts, speech_style, core_traits)
        taboo_topics = self._infer_taboo_topics(values, core_traits, decision_rules)
        forbidden_behaviors = self._infer_forbidden_behaviors(values, core_traits, speech_style)
        core_identity = self._infer_core_identity(identity_anchor, core_traits, descriptions, dialogues)
        faction_position = self._infer_faction_position(name, descriptions, dialogues, thoughts, values)
        background_imprint = self._infer_background_imprint(life_experience, values, descriptions)
        world_rule_fit = self._infer_world_rule_fit(values, decision_rules, speech_style)
        strengths = self._infer_strengths(core_traits, decision_rules, speech_style)
        weaknesses = self._infer_weaknesses(core_traits, emotion_profile, speech_style)
        cognitive_limits = self._infer_cognitive_limits(values, core_traits)
        action_style = self._infer_action_style(values, decision_rules, speech_style)
        social_mode = self._infer_social_mode(values, core_traits, speech_style)
        key_bonds = self._infer_key_bonds(values, decision_rules, taboo_topics)
        reward_logic = self._infer_reward_logic(values, core_traits)
        hidden_desire = self._infer_hidden_desire(values, soul_goal)
        inner_conflict = self._infer_inner_conflict(values, core_traits, decision_rules)
        fear_triggers = self._infer_fear_triggers(values, taboo_topics, forbidden_behaviors)
        private_self = self._infer_private_self(speech_style, emotion_profile, social_mode)
        story_role = self._infer_story_role(descriptions, dialogues, thoughts, decision_rules)
        belief_anchor = self._infer_belief_anchor(values, worldview)
        stance_stability = self._infer_stance_stability(values, decision_rules)

        return {
            "name": name,
            "core_traits": core_traits[: int(self.config.get("distillation.traits_max_count", 10))],
            "values": values,
            "speech_style": speech_style,
            "typical_lines": dialogues[:8],
            "decision_rules": decision_rules[:8],
            "identity_anchor": identity_anchor,
            "soul_goal": soul_goal,
            "life_experience": life_experience[:4],
            "worldview": worldview,
            "thinking_style": thinking_style,
            "speech_habits": speech_habits,
            "emotion_profile": emotion_profile,
            "taboo_topics": taboo_topics[:6],
            "forbidden_behaviors": forbidden_behaviors[:6],
            "core_identity": core_identity,
            "faction_position": faction_position,
            "background_imprint": background_imprint,
            "world_rule_fit": world_rule_fit,
            "strengths": strengths[:5],
            "weaknesses": weaknesses[:5],
            "cognitive_limits": cognitive_limits[:4],
            "action_style": action_style,
            "social_mode": social_mode,
            "key_bonds": key_bonds[:4],
            "reward_logic": reward_logic,
            "hidden_desire": hidden_desire,
            "inner_conflict": inner_conflict,
            "fear_triggers": fear_triggers[:5],
            "private_self": private_self,
            "story_role": story_role,
            "belief_anchor": belief_anchor,
            "stance_stability": stance_stability,
            "arc": arc,
            "arc_summary": self._infer_arc_summary(arc),
            "arc_confidence": self._infer_arc_confidence(arc, timeline),
            "archetype": archetype,
        }

    def _refine_profile_with_llm(
        self,
        profile: Dict[str, Any],
        *,
        bucket: Dict[str, List[str]],
        arc_values: List[Tuple[int, Dict[str, int]]],
    ) -> Dict[str, Any]:
        if not self._should_use_llm_second_pass():
            return profile

        try:
            messages = self._build_second_pass_messages(profile, bucket, arc_values)
            response = self.llm_client.chat_completion(
                messages,
                temperature=0.2,
                max_tokens=1600,
            )
            content = str(response.get("content", "")).strip()
            if not content:
                return profile
            parsed = self._parse_markdown_kv(content)
            if not parsed:
                return profile
            refined = self._apply_profile_refinement(profile, parsed)
            refined["arc_summary"] = self._infer_arc_summary(refined.get("arc", {}))
            refined["arc_confidence"] = self._safe_int(parsed.get("arc_confidence", refined.get("arc_confidence", 0)))
            return refined
        except ZaomengError as exc:
            self.logger.warning("Skipping LLM second pass for %s: %s", profile.get("name", "unknown"), exc)
            return profile

    def _should_use_llm_second_pass(self) -> bool:
        if self.second_pass_mode == "rule-only":
            return False
        if self.second_pass_mode == "llm-only":
            return True
        return bool(getattr(self.llm_client, "is_generation_enabled", lambda: False)())

    def _build_second_pass_messages(
        self,
        profile: Dict[str, Any],
        bucket: Dict[str, List[str]],
        arc_values: List[Tuple[int, Dict[str, int]]],
    ) -> List[Dict[str, str]]:
        prompt_text = self._load_auxiliary_markdown(
            "prompt_file",
            "distill_prompt.md",
            fallback=(
                "# 人物档案蒸馏\n"
                "你需要在现有规则草稿基础上做第二次提炼，强化深层人格、阶段弧光与差异化表达。"
            ),
        )
        schema_text = self._load_auxiliary_markdown("reference_file", "output_schema.md", fallback="# 输出规范")
        style_text = self._load_auxiliary_markdown("reference_file", "style_differ.md", fallback="# 风格差异化")
        logic_text = self._load_auxiliary_markdown("reference_file", "logic_constraint.md", fallback="# 逻辑约束")
        draft_markdown = self._render_profile_md(profile)
        evidence_markdown = self._render_second_pass_evidence(profile["name"], bucket, arc_values)

        system_prompt = "\n\n".join(
            [
                prompt_text,
                schema_text,
                style_text,
                logic_text,
                (
                    "第二次蒸馏任务：\n"
                    "- 你会收到一个规则草稿版 PROFILE 和对应证据。\n"
                    "- 你的职责是把深层人格字段、阶段弧光字段、表达特征字段提炼得更具体、更去同质化。\n"
                    "- 只能基于给定证据修订，不得脑补剧情外设定。\n"
                    "- 输出必须仍然是可解析的 Markdown，每行使用 `- key: value`。\n"
                    "- 请输出完整 `# PROFILE` 文档，而不是解释。"
                ),
            ]
        )
        user_prompt = "\n\n".join(
            [
                "以下是规则草稿：",
                draft_markdown,
                "以下是证据摘要：",
                evidence_markdown,
            ]
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _render_second_pass_evidence(
        self,
        name: str,
        bucket: Dict[str, List[str]],
        arc_values: List[Tuple[int, Dict[str, int]]],
    ) -> str:
        timeline = list(bucket.get("timeline", []))
        stage_windows = self._build_stage_windows(timeline)
        lines = [
            f"# EVIDENCE FOR {name}",
            "",
            "## Early Stage",
        ]
        lines.extend(f"- {line}" for line in stage_windows.get("start", [])[: self.llm_evidence_lines_per_stage])
        lines.extend(["", "## Mid Stage"])
        lines.extend(f"- {line}" for line in stage_windows.get("mid", [])[: self.llm_evidence_lines_per_stage])
        lines.extend(["", "## Late Stage"])
        lines.extend(f"- {line}" for line in stage_windows.get("end", [])[: self.llm_evidence_lines_per_stage])
        lines.extend(["", "## Dialogue Samples"])
        lines.extend(f"- {line}" for line in self._dedupe_texts(bucket.get("dialogues", []), 8)[:8])
        lines.extend(["", "## Thought Samples"])
        lines.extend(f"- {line}" for line in self._dedupe_texts(bucket.get("thoughts", []), 6)[:6])
        lines.extend(["", "## Description Samples"])
        lines.extend(f"- {line}" for line in self._dedupe_texts(bucket.get("descriptions", []), 6)[:6])
        lines.extend(["", "## Arc Metrics"])
        for idx, values in arc_values[:12]:
            lines.append(f"- chunk_{idx}: {self._join_metric_map(values)}")
        return "\n".join(lines).rstrip() + "\n"

    def _load_auxiliary_markdown(self, method_name: str, filename: str, fallback: str) -> str:
        resolver = getattr(self.path_provider, method_name, None)
        if resolver is None:
            return fallback
        path = resolver(filename)
        if not path or not Path(path).exists():
            return fallback
        return Path(path).read_text(encoding="utf-8")

    @staticmethod
    def _parse_markdown_kv(text: str) -> Dict[str, str]:
        parsed: Dict[str, str] = {}
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key_text = key.strip()
            value_text = value.strip()
            if not key_text or not value_text:
                continue
            if key_text in parsed and parsed[key_text]:
                parsed[key_text] = f"{parsed[key_text]}；{value_text}"
            else:
                parsed[key_text] = value_text
        return parsed

    def _apply_profile_refinement(self, profile: Dict[str, Any], parsed: Dict[str, str]) -> Dict[str, Any]:
        refined = dict(profile)
        list_fields = {
            "core_traits",
            "typical_lines",
            "decision_rules",
            "life_experience",
            "taboo_topics",
            "forbidden_behaviors",
            "strengths",
            "weaknesses",
            "cognitive_limits",
            "fear_triggers",
            "key_bonds",
            "signature_phrases",
            "sentence_openers",
            "connective_tokens",
            "sentence_endings",
            "forbidden_fillers",
        }
        dict_targets = {
            "cadence": ("speech_habits", "cadence"),
            "signature_phrases": ("speech_habits", "signature_phrases"),
            "sentence_openers": ("speech_habits", "sentence_openers"),
            "connective_tokens": ("speech_habits", "connective_tokens"),
            "sentence_endings": ("speech_habits", "sentence_endings"),
            "forbidden_fillers": ("speech_habits", "forbidden_fillers"),
            "anger_style": ("emotion_profile", "anger_style"),
            "joy_style": ("emotion_profile", "joy_style"),
            "grievance_style": ("emotion_profile", "grievance_style"),
        }
        direct_fields = {
            "speech_style",
            "identity_anchor",
            "soul_goal",
            "worldview",
            "thinking_style",
            "core_identity",
            "faction_position",
            "background_imprint",
            "world_rule_fit",
            "social_mode",
            "hidden_desire",
            "inner_conflict",
            "story_role",
            "belief_anchor",
            "private_self",
            "stance_stability",
            "reward_logic",
            "action_style",
            "arc_summary",
        }

        for key, value in parsed.items():
            if key in {"arc_start", "arc_mid", "arc_end"}:
                bucket_name = key.split("_", 1)[1]
                arc_bucket = dict(refined.get("arc", {}).get(bucket_name, {}))
                arc_bucket.update(self._split_metric_map(value))
                refined.setdefault("arc", {})[bucket_name] = arc_bucket
                continue
            if key == "values":
                value_map = self._split_metric_map(value)
                if value_map:
                    refined["values"] = {
                        metric: max(0, min(10, self._safe_int(metric_value)))
                        for metric, metric_value in value_map.items()
                    }
                continue
            if key in dict_targets:
                parent, child = dict_targets[key]
                parent_bucket = dict(refined.get(parent, {})) if isinstance(refined.get(parent, {}), dict) else {}
                parent_bucket[child] = self._split_persona_scalar(value) if key in list_fields else value
                refined[parent] = parent_bucket
                continue
            if key in direct_fields:
                refined[key] = value
                continue
            if key in list_fields:
                refined[key] = self._split_persona_scalar(value)
        return refined

    @staticmethod
    def _split_persona_scalar(value: str) -> List[str]:
        return [item.strip() for item in re.split(r"[；;]\s*", str(value or "").strip()) if item.strip()]

    @staticmethod
    def _split_metric_map(value: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for item in re.split(r"[；;]\s*", str(value or "").strip()):
            if not item or "=" not in item:
                continue
            key, raw = item.split("=", 1)
            key_text = key.strip()
            raw_text = raw.strip()
            if not key_text:
                continue
            if re.fullmatch(r"-?\d+", raw_text):
                result[key_text] = int(raw_text)
            else:
                result[key_text] = raw_text
        return result

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _infer_traits(self, lines: List[str], archetype: str) -> List[str]:
        if not lines:
            return self._apply_archetype_traits(["克制", "复杂"], archetype)
        corpus = " ".join(lines)
        hits: List[Tuple[str, int]] = []
        for trait, markers in self.trait_keywords.items():
            score = sum(corpus.count(token) for token in markers)
            if score > 0:
                hits.append((trait, score))
        hits.sort(key=lambda item: item[1], reverse=True)
        base_traits = [trait for trait, _ in hits[:8]] or ["谨慎", "多思"]
        return self._apply_archetype_traits(base_traits, archetype)

    def _infer_archetype(
        self,
        name: str,
        descriptions: List[str],
        dialogues: List[str],
        thoughts: List[str],
    ) -> str:
        corpus = " ".join([name] + descriptions[:10] + dialogues[:10] + thoughts[:10])
        best_name = "default"
        best_score = 0
        second_score = 0
        for archetype_name, config in self.archetypes.items():
            markers = [str(item).strip() for item in config.get("markers", []) if str(item).strip()]
            score = sum(corpus.count(marker) for marker in markers)
            if score > best_score:
                second_score = best_score
                best_name = archetype_name
                best_score = score
            elif score > second_score:
                second_score = score
        return best_name if best_score >= 5 and best_score >= second_score + 2 else "default"

    def _apply_archetype_traits(self, traits: List[str], archetype: str) -> List[str]:
        configured = self.archetypes.get(archetype, {}).get("traits", [])
        return self._unique_texts(list(traits) + [str(item).strip() for item in configured if str(item).strip()])[:10]

    def _infer_values_from_corpus(
        self,
        values: Dict[str, int],
        descriptions: List[str],
        dialogues: List[str],
        thoughts: List[str],
        archetype: str,
    ) -> Dict[str, int]:
        dims = self._value_dimensions()
        corpus = " ".join(descriptions + dialogues + thoughts)
        merged = {dim: int(values.get(dim, 5)) for dim in dims}
        for dim in dims:
            config = self.value_markers.get(dim, {})
            positive = sum(corpus.count(token) for token in config.get("positive", []))
            negative = sum(corpus.count(token) for token in config.get("negative", []))
            delta = min(3, positive) - min(3, negative)
            merged[dim] = max(1, min(10, merged.get(dim, 5) + delta))
        for dim, bias in self.archetypes.get(archetype, {}).get("value_bias", {}).items():
            if dim not in merged:
                merged[dim] = 5
            merged[dim] = max(1, min(10, merged[dim] + max(-1, min(1, int(bias)))))
        return merged

    def _merge_arc_values(self, arc_values: List[Tuple[int, Dict[str, int]]]) -> Dict[str, int]:
        dims = self._value_dimensions()
        if not arc_values:
            return {dim: 5 for dim in dims}
        merged = defaultdict(list)
        for _, values in arc_values:
            for dim in dims:
                merged[dim].append(int(values.get(dim, 5)))
        return {dim: int(round(sum(items) / len(items))) for dim, items in merged.items()}

    def _build_arc(
        self,
        arc_values: List[Tuple[int, Dict[str, int]]],
        fallback_values: Dict[str, int],
        timeline: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        stages = self._build_stage_windows(timeline)
        if not arc_values:
            return {
                "start": {"phase_summary": self._summarize_stage_window(stages.get("start", []))},
                "mid": {
                    "phase_summary": self._summarize_stage_window(stages.get("mid", [])),
                    "trigger_event": "未识别到稳定弧光证据",
                },
                "end": {
                    "phase_summary": self._summarize_stage_window(stages.get("end", [])),
                    "final_state": "未判定（证据不足）",
                },
            }

        ordered = sorted(arc_values, key=lambda item: item[0])
        start = dict(ordered[0][1] or {})
        mid = dict(ordered[len(ordered) // 2][1] or {})
        end = dict(ordered[-1][1] or {})
        start["phase_summary"] = self._summarize_stage_window(stages.get("start", []))
        mid["phase_summary"] = self._summarize_stage_window(stages.get("mid", []))
        end["phase_summary"] = self._summarize_stage_window(stages.get("end", []))

        if len(ordered) < 2:
            return {
                "start": start,
                "mid": {**mid, "trigger_event": "样本跨度不足，未识别到稳定变化事件"},
                "end": {**end, "final_state": "未判定（片段跨度不足）"},
            }

        spread = 0
        for dim in self._value_dimensions():
            series = [int(values.get(dim, fallback_values.get(dim, 5))) for _, values in ordered]
            spread = max(spread, max(series) - min(series))
        if spread < 1:
            return {
                "start": start,
                "mid": {**mid, "trigger_event": "未识别到明确变化事件"},
                "end": {**end, "final_state": "静态人物或当前片段未呈现稳定弧光"},
            }

        return {
            "start": start,
            "mid": {**mid, "trigger_event": "关键关系或冲突推动"},
            "end": {**end, "final_state": "阶段性收束"},
        }

    def _build_stage_windows(self, timeline: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        if not timeline:
            return {"start": [], "mid": [], "end": []}
        ordered = sorted(timeline, key=lambda item: int(item.get("index", 0)))
        window = max(1, self.stage_window_size)
        start_entries = ordered[:window]
        end_entries = ordered[-window:]
        mid_start = max(0, (len(ordered) // 2) - (window // 2))
        mid_entries = ordered[mid_start : mid_start + window]
        return {
            "start": self._flatten_stage_entries(start_entries),
            "mid": self._flatten_stage_entries(mid_entries),
            "end": self._flatten_stage_entries(end_entries),
        }

    @staticmethod
    def _flatten_stage_entries(entries: List[Dict[str, Any]]) -> List[str]:
        lines: List[str] = []
        for item in entries:
            for key in ("descriptions", "thoughts", "dialogues"):
                for line in item.get(key, []):
                    text = str(line).strip()
                    if text:
                        lines.append(text)
        return NovelDistiller._dedupe_texts(lines, 12)

    @staticmethod
    def _summarize_stage_window(lines: List[str]) -> str:
        if not lines:
            return "该阶段证据不足"
        first = str(lines[0]).strip()
        if len(first) > 40:
            first = f"{first[:40]}..."
        return first

    @staticmethod
    def _infer_arc_summary(arc: Dict[str, Any]) -> str:
        start = arc.get("start", {}) if isinstance(arc.get("start", {}), dict) else {}
        mid = arc.get("mid", {}) if isinstance(arc.get("mid", {}), dict) else {}
        end = arc.get("end", {}) if isinstance(arc.get("end", {}), dict) else {}
        trigger = str(mid.get("trigger_event", "")).strip()
        final_state = str(end.get("final_state", "")).strip()
        if trigger and final_state:
            return f"{trigger} -> {final_state}"
        return final_state or trigger or str(start.get("phase_summary", "")).strip()

    @staticmethod
    def _infer_arc_confidence(arc: Dict[str, Any], timeline: List[Dict[str, Any]]) -> int:
        points = max(0, min(10, len(timeline)))
        trigger = str((arc.get("mid", {}) or {}).get("trigger_event", "")).strip()
        final_state = str((arc.get("end", {}) or {}).get("final_state", "")).strip()
        bonus = 0
        if trigger and "未识别" not in trigger:
            bonus += 2
        if final_state and "未判定" not in final_state:
            bonus += 2
        return max(1, min(10, min(6, points) + bonus))

    def _infer_speech_style(self, lines: List[str], archetype: str) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("speech_style", "")).strip() if archetype != "default" else ""
        if not lines:
            return configured or self.style_templates.get("quiet", "发言偏少，更多通过态度和分寸表明立场。")
        avg_len = sum(len(item) for item in lines) / max(1, len(lines))
        exclaim_ratio = sum(1 for item in lines if any(token in item for token in ("！", "!", "？", "?")))
        if avg_len <= 12:
            return self.style_templates.get("short_direct", "句式偏短，较少铺垫，态度来得直接。")
        if exclaim_ratio >= max(1, len(lines) // 3):
            return self.style_templates.get("emotional", "情绪浮在表面，回应时容易带出锋芒或波动。")
        if avg_len >= 26:
            return self.style_templates.get("long_reflective", "句式较长，喜欢把轻重和前因后果慢慢展开。")
        return self.style_templates.get("balanced", "表达有分寸，既不极短，也不刻意铺陈。")

    def _infer_decision_rules(
        self,
        thoughts: List[str],
        descriptions: List[str],
        dialogues: List[str],
        archetype: str,
    ) -> List[str]:
        corpus_lines = self._dedupe_texts(thoughts[:12] + dialogues[:12] + descriptions[:12], 30)
        scored_rules: List[Tuple[int, str]] = []

        for _, config in self.decision_rule_signals.items():
            markers = [str(item).strip() for item in config.get("markers", []) if str(item).strip()]
            template = str(config.get("template", "")).strip()
            if not markers or not template:
                continue

            marker_hits = 0
            sentence_hits = 0
            for line in corpus_lines:
                hit_count = sum(line.count(marker) for marker in markers)
                if hit_count <= 0:
                    continue
                marker_hits += min(3, hit_count)
                sentence_hits += 1

            if marker_hits <= 0:
                continue
            scored_rules.append((marker_hits + min(3, sentence_hits), template))

        scored_rules.sort(key=lambda item: item[0], reverse=True)
        rules = [rule for _, rule in scored_rules[:3]]

        archetype_rules = [
            str(item).strip() for item in self.archetypes.get(archetype, {}).get("decision_rules", []) if str(item).strip()
        ]
        if len(rules) < 2:
            rules.extend(archetype_rules[: 2 - len(rules)])

        joined = "".join(dialogues[:8])
        if any(token in joined for token in ("先", "且慢", "慢些", "等等")):
            rules.append("不会一上来把话说死，通常会先留一步判断。")
        if any(token in joined for token in ("不可", "不能", "休得", "岂可")):
            rules.append("遇到底线问题时，会明显收紧语气并立即表态。")
        if not rules:
            rules.append("高压情境下，会先分清轻重和后果，再决定动作。")
        return self._dedupe_texts(rules, 8)

    def _infer_identity_anchor(
        self,
        core_traits: List[str],
        values: Dict[str, int],
        decision_rules: List[str],
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("identity_anchor", "")).strip()
        if configured:
            return configured
        top_value = self._top_dimensions(values, count=2)
        if "责任" in top_value:
            return "遇到局面时，习惯先把担子接住的人"
        if "忠诚" in top_value:
            return "把信义和跟随关系看得很重的人"
        if "正义" in top_value:
            return "先分是非，再谈利害的人"
        if "智慧" in top_value or "谨慎" in core_traits:
            return "凡事先探虚实和后势的人"
        if any("自己人" in rule for rule in decision_rules):
            return "见不得身边人独自受压的人"
        return "不会轻率交出真实态度的人"

    def _infer_soul_goal(self, values: Dict[str, int], core_traits: List[str], archetype: str) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("soul_goal", "")).strip()
        if configured:
            return configured
        top_value = self._top_dimensions(values, count=1)[0]
        mapping = {
            "责任": "把眼前的人和局面尽量稳住，不让局势轻易散掉",
            "忠诚": "守住已经认下的承诺与关系，不轻易失信",
            "正义": "把轻重和是非摆正，不让局势被歪理带偏",
            "智慧": "先看清局势再动手，尽量少走弯路",
            "勇气": "真到要紧处，愿意先一步站到前面",
            "善良": "尽量少伤人心，也少伤无辜之人",
            "自由": "不给自己和身边人活成任人摆布的棋子",
            "野心": "借势把局面推向更远的位置，而不止是应付眼前",
        }
        if "执拗" in core_traits and "正义" not in mapping:
            return "认准了就要做到底，不愿轻易退回去"
        return mapping.get(top_value, "把事情看透，再把自己真正想守的东西守住")

    def _infer_life_experience(
        self,
        descriptions: List[str],
        dialogues: List[str],
        thoughts: List[str],
        decision_rules: List[str],
        values: Dict[str, int],
        archetype: str,
    ) -> List[str]:
        configured = self.archetypes.get(archetype, {}).get("life_experience", "")
        lines = [str(configured).strip()] if str(configured).strip() else []
        corpus = " ".join(descriptions[:6] + thoughts[:6])
        if any(token in corpus for token in ("旧事", "往年", "从前", "昔日")):
            lines.append("过往经历仍在影响当下的分寸和判断。")
        if any("先收住" in rule or "后势" in rule for rule in decision_rules):
            lines.append("见过局势反覆之后，更少只凭一时热气定夺。")
        if values.get("责任", 5) >= 8:
            lines.append("这些经历让他更习惯替旁人托底，而不是只顾自己。")
        if values.get("善良", 5) >= 8:
            lines.append("看过人心冷暖之后，更不愿把无辜者推到前面。")
        if not lines:
            lines.append("经历过人情与局势的反覆，因此很少只看眼前这一层。")
        return self._dedupe_texts(lines, 4)

    def _infer_worldview(self, values: Dict[str, int], core_traits: List[str], archetype: str) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("worldview", "")).strip()
        if configured:
            return configured
        top_value = self._top_dimensions(values, count=2)
        if "忠诚" in top_value:
            return "先看人是否可靠，再看事值不值得做。"
        if "正义" in top_value:
            return "是非若站不稳，利益再大也不该轻动。"
        if "智慧" in top_value:
            return "世事最怕只看一面，虚实和后势都要算进去。"
        if "责任" in top_value or "善良" in top_value:
            return "局面再乱，也不能把身边人与无辜者轻易丢下。"
        if "谨慎" in core_traits:
            return "先看清，再落子，宁慢一步，不乱一步。"
        return "说话做事都不能只图一时痛快，还得顾后果。"

    def _infer_thinking_style(
        self,
        values: Dict[str, int],
        core_traits: List[str],
        speech_style: str,
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("thinking_style", "")).strip()
        if configured:
            return configured
        top_value = self._top_dimensions(values, count=1)[0]
        if top_value == "智慧" or "谨慎" in core_traits:
            return "先拆局势，再定立场。"
        if top_value in {"忠诚", "正义"}:
            return "先问对错与名分，再谈成败。"
        if top_value == "勇气":
            return "先看该不该顶上，再看怎么顶。"
        if "敏感" in core_traits:
            return "先感受人心冷暖，再决定把话说到几分。"
        if "直白" in speech_style:
            return "先抓最要紧的一点，直接给态度。"
        return "先稳住分寸，再把轻重说清。"

    def _infer_speech_habits(self, dialogues: List[str], speech_style: str) -> Dict[str, Any]:
        cadence = "medium"
        if dialogues:
            window = dialogues[:8]
            avg_len = sum(len(item) for item in window) / max(1, len(window))
            questionish = sum(1 for item in window if any(token in item for token in ("？", "?", "何", "怎", "吗")))
            exclaimish = sum(1 for item in window if any(token in item for token in ("！", "!", "快", "休", "莫")))
            if avg_len <= 11 or questionish >= max(2, len(window) // 2):
                cadence = "short"
            elif avg_len >= 24 and exclaimish <= max(1, len(window) // 4):
                cadence = "long"
        if cadence == "medium":
            if "句式偏短" in speech_style or "直白" in speech_style:
                cadence = "short"
            elif "句式较长" in speech_style or "铺陈" in speech_style:
                cadence = "long"

        signature_phrases: List[str] = []
        for line in dialogues[:6]:
            for fragment in self.signature_fragments:
                if fragment in line and fragment not in signature_phrases:
                    signature_phrases.append(fragment)
        for fragment in self._extract_signature_phrases(dialogues):
            if fragment not in signature_phrases:
                signature_phrases.append(fragment)

        return {
            "cadence": cadence,
            "signature_phrases": signature_phrases[:4],
            "sentence_openers": self._extract_dialogue_markers(dialogues, self.opener_patterns, position="start"),
            "connective_tokens": self._extract_dialogue_markers(dialogues, self.connective_patterns, position="any"),
            "sentence_endings": self._extract_dialogue_markers(dialogues, self.ending_patterns, position="end"),
            "forbidden_fillers": list(self.generic_fillers),
        }

    @staticmethod
    def _infer_emotion_profile(
        dialogues: List[str],
        thoughts: List[str],
        speech_style: str,
        core_traits: List[str],
    ) -> Dict[str, Any]:
        anger = "怒时会先压住锋芒，说话更冷更短。" if "克制" in speech_style else "怒时会把边界和态度讲得更硬。"
        joy = "高兴时也不轻浮，只会略略放松语气。" if "克制" in speech_style else "高兴时语气会明显松快一些。"
        grievance = "受委屈时多半先忍住，不肯立刻摊开。" if "敏感" in core_traits else "受委屈时会把态度说得更直。"
        if any("叹" in item for item in thoughts[:6]):
            grievance = "受屈时往往先把情绪收在心里，再慢慢露出来。"
        return {
            "anger_style": anger,
            "joy_style": joy,
            "grievance_style": grievance,
        }

    def _infer_taboo_topics(
        self,
        values: Dict[str, int],
        core_traits: List[str],
        decision_rules: List[str],
    ) -> List[str]:
        topics: List[str] = []
        for value_name, configured_topics in self.taboo_topics_by_value.items():
            if values.get(value_name, 5) >= 8:
                topics.extend(str(item).strip() for item in configured_topics if str(item).strip())
        if "敏感" in core_traits:
            topics.append("拿人心取笑")
        if any("自己人" in rule for rule in decision_rules):
            topics.append("牺牲自己人")
        return self._dedupe_texts(topics, 6)

    def _infer_forbidden_behaviors(
        self,
        values: Dict[str, int],
        core_traits: List[str],
        speech_style: str,
    ) -> List[str]:
        bans: List[str] = []
        for value_name, configured_bans in self.forbidden_behaviors_by_value.items():
            if values.get(value_name, 5) >= 8:
                bans.extend(str(item).strip() for item in configured_bans if str(item).strip())
        if "克制" in speech_style:
            bans.append("不会无缘无故撒泼失态")
        if "谨慎" in core_traits:
            bans.append("不会在虚实未明时把话说死")
        return self._dedupe_texts(bans, 6)

    @staticmethod
    def _infer_core_identity(
        identity_anchor: str,
        core_traits: List[str],
        descriptions: List[str],
        dialogues: List[str],
    ) -> str:
        if identity_anchor:
            return identity_anchor
        first_scene = next((line for line in descriptions[:6] if line.strip()), "")
        if first_scene:
            return first_scene[:36]
        if core_traits:
            return f"在众人眼里，多半以{'、'.join(core_traits[:2])}的一面被记住。"
        if dialogues:
            return "多通过说话和临场态度来定义自己。"
        return "身份轮廓仍需更多正文证据补全。"

    @staticmethod
    def _infer_faction_position(
        name: str,
        descriptions: List[str],
        dialogues: List[str],
        thoughts: List[str],
        values: Dict[str, int],
    ) -> str:
        corpus = descriptions[:10] + dialogues[:6] + thoughts[:6]
        identity_tokens = ("氏", "宗主", "家主", "公子", "少主", "门下", "弟子", "门生", "师门", "世家", "本家")
        for line in corpus:
            if name not in line:
                continue
            if NovelDistiller._looks_like_metadata_sentence(line):
                continue
            if not any(token in line for token in identity_tokens):
                continue
            clauses = [part.strip() for part in re.split(r"[，。！？；：、]", line) if part.strip()]
            for clause in clauses:
                if name in clause and any(token in clause for token in identity_tokens) and len(clause) <= 28:
                    return clause
        if values.get("忠诚", 5) >= 7:
            return "立场通常会向自己认定的人与所属一侧收拢，不会轻易改换。"
        if values.get("自由", 5) >= 7:
            return "对阵营与规训保持距离，更倾向保留自主转圜。"
        return "立场更多随关系轻重与局势演变而显形。"

    @staticmethod
    def _infer_background_imprint(
        life_experience: List[str],
        values: Dict[str, int],
        descriptions: List[str],
    ) -> str:
        if life_experience:
            return life_experience[0]
        if any(token in "".join(descriptions[:8]) for token in ("旧事", "从前", "少年", "幼时", "家中", "门下")):
            return "成长环境与旧事仍在影响如今的取舍和分寸。"
        if values.get("责任", 5) >= 7:
            return "长期处在要接事、扛事的位置，环境把人磨得更会托底。"
        return "生存处境留下的烙印更多体现在谨慎与边界感上。"

    @staticmethod
    def _infer_world_rule_fit(values: Dict[str, int], decision_rules: List[str], speech_style: str) -> str:
        if any("边界" in rule or "规矩" in rule for rule in decision_rules):
            return "更倾向在现有规则内划清边界，必要时才顶着规则推进。"
        if values.get("自由", 5) >= 7:
            return "会和世界规则保持拉扯，能借势时借势，受制时就想挣开。"
        if "克制" in speech_style:
            return "整体与世界运转规则较为相容，除非底线被逼到眼前。"
        return "对世界规则既不盲从，也不会无端硬撞，更多看局势取舍。"

    @staticmethod
    def _infer_strengths(core_traits: List[str], decision_rules: List[str], speech_style: str) -> List[str]:
        mapping = {
            "勇敢": "关键时刻敢于顶上承压",
            "聪慧": "擅长拆解局势与看出破口",
            "克制": "能在情绪上头时收束表达",
            "沉稳": "能在混乱里稳住节奏和后手",
            "忠诚": "对认定的人和承诺有持续性",
            "善良": "照顾人心与无辜者时不容易失手",
            "机变": "面对变化时转身快、补位快",
            "诙谐": "会用语言缓冲气氛或卸力",
            "执拗": "认准方向后执行力强",
            "敏感": "对情绪、气氛和关系变化更早觉察",
        }
        strengths = [mapping[trait] for trait in core_traits if trait in mapping]
        if any("护住" in rule or "自己人" in rule for rule in decision_rules):
            strengths.append("在关系压力下仍愿意主动护人")
        if "句式偏短" in speech_style:
            strengths.append("表态快，不容易在关键处含混")
        return NovelDistiller._dedupe_texts(strengths, 5)

    @staticmethod
    def _infer_weaknesses(
        core_traits: List[str],
        emotion_profile: Dict[str, Any],
        speech_style: str,
    ) -> List[str]:
        mapping = {
            "傲气": "不肯轻易低头，容易把关系逼紧",
            "敏感": "旧事和情绪牵动时会放大心里落差",
            "执拗": "认准之后回头慢，容易和现实硬碰",
            "勇敢": "容易在高压里先把自己推到前面",
            "诙谐": "有时会用玩笑遮掩真正的在意",
            "克制": "太能压住情绪时，真实想法不易被旁人看懂",
        }
        weaknesses = [mapping[trait] for trait in core_traits if trait in mapping]
        if "更冷更短" in str(emotion_profile.get("anger_style", "")):
            weaknesses.append("怒时会迅速关上沟通窗口")
        if "句式偏短" in speech_style:
            weaknesses.append("说得太短时，容易让人只看到锋芒")
        return NovelDistiller._dedupe_texts(weaknesses, 5)

    @staticmethod
    def _infer_cognitive_limits(values: Dict[str, int], core_traits: List[str]) -> List[str]:
        limits: List[str] = []
        if values.get("忠诚", 5) >= 7:
            limits.append("容易把关系旧账和情分看得过重")
        if values.get("自由", 5) >= 7:
            limits.append("一旦感到被钳制，判断会更偏向先挣脱")
        if values.get("勇气", 5) >= 7:
            limits.append("容易高估自己顶住局面的能力")
        if "敏感" in core_traits:
            limits.append("对态度和语气变化容易产生额外联想")
        if "傲气" in core_traits:
            limits.append("面对挑衅时不容易完全抽离情绪")
        return NovelDistiller._dedupe_texts(limits, 4)

    @staticmethod
    def _infer_action_style(values: Dict[str, int], decision_rules: List[str], speech_style: str) -> str:
        if any("先辨清" in rule or "虚实" in rule for rule in decision_rules):
            return "先探局、后落子，确认虚实后才会真正压上。"
        if any("护住" in rule or "出手" in rule for rule in decision_rules):
            return "遇到人和局面同时承压时，往往会边护边推进。"
        if "句式偏短" in speech_style:
            return "行事和发言一样偏直接，确认方向后动作不拖。"
        return "行事风格更看当时轻重，会在直进与收手之间找平衡。"

    @staticmethod
    def _infer_social_mode(values: Dict[str, int], core_traits: List[str], speech_style: str) -> str:
        if values.get("忠诚", 5) >= 7 or values.get("责任", 5) >= 7:
            return "对自己人会明显偏护，对陌生人先看分寸和可靠度。"
        if values.get("自由", 5) >= 7:
            return "与人相处先保留边界，不喜欢被人一步步拿住。"
        if "克制" in speech_style:
            return "不轻易交底，亲疏远近要靠时间和事来慢慢试。"
        return "表面进退都快，但真正认人与否仍有自己的门槛。"

    @staticmethod
    def _infer_key_bonds(values: Dict[str, int], decision_rules: List[str], taboo_topics: List[str]) -> List[str]:
        bonds: List[str] = []
        if any("护住" in rule or "自己人" in rule for rule in decision_rules):
            bonds.append("一旦认定为自己人，牵绊会深到影响后续所有选择")
        if values.get("忠诚", 5) >= 7:
            bonds.append("对共同经历风险的人更容易形成长期同盟感")
        if "背叛" in taboo_topics:
            bonds.append("关系一旦触及失信，往往很难彻底回到从前")
        if not bonds:
            bonds.append("关系深浅通常要经过试探、兑现和并肩之后才会坐实")
        return NovelDistiller._dedupe_texts(bonds, 4)

    @staticmethod
    def _infer_reward_logic(values: Dict[str, int], core_traits: List[str]) -> str:
        if values.get("忠诚", 5) >= 7:
            return "记恩也记失信，认定后会长期回护，翻脸时也很难装作无事。"
        if values.get("正义", 5) >= 7:
            return "更看是非和底线，赏罚首先取决于事情本身站不站得住。"
        if values.get("自由", 5) >= 7:
            return "对强压与操控格外记仇，对给空间的人会自然放软。"
        if "敏感" in core_traits:
            return "对态度冷热记得很深，报答和疏远都会来得直接。"
        return "恩怨判断常看对方是否越线，以及关键时候有没有站住。"

    @staticmethod
    def _infer_hidden_desire(values: Dict[str, int], soul_goal: str) -> str:
        if values.get("责任", 5) >= 7:
            return "比起表面赢输，更深处想守住能让自己安心的人与位置。"
        if values.get("自由", 5) >= 7:
            return "最深处仍想保住不被摆布、不被定死的活法。"
        if values.get("忠诚", 5) >= 7:
            return "深层里渴望关系能被确认，也害怕自己认下的东西再次散掉。"
        if values.get("正义", 5) >= 7:
            return "真正放不下的是是非被颠倒、真相被压住。"
        return soul_goal or "表面目标之外，仍有一层不愿被人轻易看穿的心里执念。"

    @staticmethod
    def _infer_inner_conflict(values: Dict[str, int], core_traits: List[str], decision_rules: List[str]) -> str:
        if values.get("勇气", 5) >= 7 and values.get("智慧", 5) >= 6:
            return "一边想立刻顶上，一边又不肯在虚实未明时贸然落子。"
        if values.get("忠诚", 5) >= 7 and values.get("正义", 5) >= 7:
            return "既想护住亲近之人，又不愿彻底把是非让给关系。"
        if values.get("自由", 5) >= 7 and values.get("责任", 5) >= 7:
            return "想保留自己的转圜空间，但关键时候又很难真正抽身。"
        if "敏感" in core_traits and any("边界" in rule for rule in decision_rules):
            return "心里在意远近冷热，表面却还要把边界和硬气撑住。"
        return "内心常在分寸、关系和自我立场之间来回拉扯。"

    @staticmethod
    def _infer_fear_triggers(
        values: Dict[str, int],
        taboo_topics: List[str],
        forbidden_behaviors: List[str],
    ) -> List[str]:
        fears = list(taboo_topics[:3])
        if values.get("自由", 5) >= 7:
            fears.append("被强行摆布或失去选择")
        if values.get("责任", 5) >= 7 or values.get("忠诚", 5) >= 7:
            fears.append("眼看自己人出事却来不及接住")
        if values.get("正义", 5) >= 7:
            fears.append("黑白被颠倒、该追的账没人去追")
        for item in forbidden_behaviors[:2]:
            if "不会" in item:
                fears.append(item.replace("不会", "最怕自己被逼到").replace("无缘无故", ""))
        return NovelDistiller._dedupe_texts(fears, 5)

    @staticmethod
    def _infer_private_self(speech_style: str, emotion_profile: Dict[str, Any], social_mode: str) -> str:
        if "克制" in speech_style:
            return "表面收得很紧，私下反而把轻重、牵挂和受过的伤记得更深。"
        if "句式偏短" in speech_style:
            return "表面锋利干脆，独处时其实更容易反复掂量关系与后果。"
        if "委屈" in str(emotion_profile.get("grievance_style", "")):
            return "外面未必肯示弱，真正难受时多半只在无人处慢慢消化。"
        return f"表面与私下并不完全一致，真正松下来时更在意：{social_mode}"

    @staticmethod
    def _infer_story_role(
        descriptions: List[str],
        dialogues: List[str],
        thoughts: List[str],
        decision_rules: List[str],
    ) -> str:
        presence = len(descriptions) + len(dialogues) + len(thoughts)
        if presence >= 40:
            base = "剧情核心推动者"
        elif presence >= 24:
            base = "主要支点角色"
        elif presence >= 12:
            base = "重要牵动者"
        else:
            base = "辅助推动角色"
        if any("护住" in rule or "后手" in rule for rule in decision_rules):
            return f"{base}，同时常承担兜底或接应压力。"
        if len(dialogues) >= max(4, len(descriptions) // 2):
            return f"{base}，更常通过对话和态度推动场面。"
        return f"{base}，对局势走向有持续影响。"

    @staticmethod
    def _infer_belief_anchor(values: Dict[str, int], worldview: str) -> str:
        if values.get("忠诚", 5) >= 7:
            return "信义和认下的人不能轻易后置。"
        if values.get("正义", 5) >= 7:
            return "是非必须站稳，否则其余一切都容易变形。"
        if values.get("责任", 5) >= 7:
            return "人在局中就该把该接的担子接住。"
        if values.get("自由", 5) >= 7:
            return "再大的局，也不能把自己活成别人手里的棋。"
        return worldview or "真正撑住他的，是一套不会轻易改口的内在秩序。"

    @staticmethod
    def _infer_stance_stability(values: Dict[str, int], decision_rules: List[str]) -> str:
        ordered = sorted((int(score), key) for key, score in values.items())
        if ordered:
            top_score, _ = ordered[-1]
            second_score = ordered[-2][0] if len(ordered) > 1 else top_score
            if top_score - second_score >= 2:
                return "立场较稳，轻易不会因为外界一句话就倒向另一边。"
        if any("留一步" in rule or "转圜" in rule for rule in decision_rules):
            return "表面会留转圜，但真正底线并不飘，更多是策略性松紧。"
        return "会受关系与局势牵动，但整体底线仍相对稳定。"

    @classmethod
    def _looks_like_metadata_sentence(cls, line: str) -> bool:
        text = str(line or "").strip()
        metadata_tokens = (
            "内容标签",
            "搜索关键字",
            "主角",
            "配角",
            "作者",
            "文案",
            "简介",
            "作品",
            "版权",
            "编辑评价",
            "作者笔下",
            "我的文",
            "读者",
            "微博",
            "专栏",
            "安利",
            "公告",
            "世界和平",
            "请不要",
            "收藏",
            "推荐",
            "点击",
            "1V1",
            "HE",
        )
        if any(token in text for token in metadata_tokens):
            return True
        if text.startswith(("PS", "P.S", "ps", "Ps")):
            return True
        return False

    @classmethod
    def _prepare_novel_text(cls, text: str) -> str:
        raw_lines = [line.rstrip() for line in str(text or "").splitlines()]
        lines = list(raw_lines)
        for idx, line in enumerate(raw_lines[:400]):
            stripped = line.strip()
            if not stripped:
                continue
            if any(pattern.search(stripped) for pattern in cls.CHAPTER_HEADING_PATTERNS):
                if idx >= 5:
                    lines = raw_lines[idx:]
                break

        filtered: List[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                filtered.append("")
                continue
            if cls._looks_like_metadata_sentence(stripped):
                continue
            filtered.append(line)
        return "\n".join(filtered).strip()

    def _export_persona_bundle(self, out_dir: Path, profile: Dict[str, Any]) -> None:
        char_dir = ensure_dir(out_dir / safe_filename(profile.get("name", "unnamed")))
        profile_content = self._render_profile_md(profile)
        (char_dir / "PROFILE.generated.md").write_text(profile_content, encoding="utf-8")
        editable_profile = char_dir / "PROFILE.md"
        if not editable_profile.exists():
            editable_profile.write_text(profile_content, encoding="utf-8")

        bundle = {
            "SOUL": self._render_soul_md(profile),
            "IDENTITY": self._render_identity_md(profile),
            "BACKGROUND": self._render_background_md(profile),
            "CAPABILITY": self._render_capability_md(profile),
            "BONDS": self._render_bonds_md(profile),
            "CONFLICTS": self._render_conflicts_md(profile),
            "ROLE": self._render_role_md(profile),
            "AGENTS": self._render_agents_md(profile),
            "MEMORY": self._render_memory_md(profile),
        }
        if self._should_create_goals_md(profile):
            bundle["GOALS"] = self._render_goals_md(profile)
        if self._should_create_style_md(profile):
            bundle["STYLE"] = self._render_style_md(profile)
        if self._should_create_trauma_md(profile):
            bundle["TRAUMA"] = self._render_trauma_md(profile)

        for base_name, content in bundle.items():
            generated = char_dir / f"{base_name}.generated.md"
            generated.write_text(content, encoding="utf-8")
            editable = char_dir / f"{base_name}.md"
            if not editable.exists():
                editable.write_text(content, encoding="utf-8")

        self.refresh_persona_navigation(char_dir, str(profile.get("name", "")))

    @classmethod
    def refresh_persona_navigation(cls, persona_dir: Path, character_name: str) -> None:
        generated = persona_dir / "NAVIGATION.generated.md"
        generated.write_text(cls._render_navigation_generated_md(persona_dir, character_name), encoding="utf-8")
        editable = persona_dir / "NAVIGATION.md"
        if not editable.exists():
            editable.write_text(cls._render_navigation_override_md(), encoding="utf-8")

    @classmethod
    def _render_navigation_generated_md(cls, persona_dir: Path, character_name: str) -> str:
        active_order = [
            base_name for base_name in cls.DEFAULT_NAV_LOAD_ORDER if cls._persona_file_is_active(persona_dir, base_name)
        ]
        if not active_order:
            active_order = ["SOUL", "IDENTITY", "AGENTS", "MEMORY"]

        lines = [
            "# NAVIGATION",
            "<!-- Runtime entrypoint. Read this file first, then follow load_order. -->",
            "",
            "## Runtime",
            f"- character: {character_name}",
            f"- load_order: {' -> '.join(active_order)}",
            "- first_read: NAVIGATION.generated.md -> NAVIGATION.md overrides",
            "- write_back: MEMORY handles durable user guidance and corrections; RELATIONS handles target-specific manual edits",
            "",
        ]
        for base_name in cls.DEFAULT_NAV_LOAD_ORDER:
            meta = cls.PERSONA_FILE_CATALOG.get(base_name, {})
            lines.extend(
                [
                    f"## {base_name}",
                    f"- status: {'active' if cls._persona_file_is_active(persona_dir, base_name) else 'inactive'}",
                    f"- optional: {'yes' if meta.get('optional', True) else 'no'}",
                    f"- file: {base_name}.md",
                    f"- fallback: {base_name}.generated.md",
                    f"- present: {'yes' if cls._persona_file_exists(persona_dir, base_name) else 'no'}",
                    f"- role: {meta.get('role', '')}",
                    f"- behaviors: {meta.get('behaviors', '')}",
                    f"- write_policy: {meta.get('write_policy', 'manual_edit')}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _render_navigation_override_md() -> str:
        return (
            "# NAVIGATION\n"
            "<!-- Optional overrides for the generated navigation map.\n"
            "Use the same key format as NAVIGATION.generated.md.\n"
            "-->\n"
        )

    @staticmethod
    def _persona_file_exists(persona_dir: Path, base_name: str) -> bool:
        return (persona_dir / f"{base_name}.md").exists() or (persona_dir / f"{base_name}.generated.md").exists()

    @classmethod
    def _persona_file_is_active(cls, persona_dir: Path, base_name: str) -> bool:
        if not cls.PERSONA_FILE_CATALOG.get(base_name, {}).get("optional", True):
            return True
        return cls._persona_file_exists(persona_dir, base_name)

    def _render_profile_md(self, profile: Dict[str, Any]) -> str:
        speech_habits = profile.get("speech_habits", {}) if isinstance(profile.get("speech_habits", {}), dict) else {}
        emotion = profile.get("emotion_profile", {}) if isinstance(profile.get("emotion_profile", {}), dict) else {}
        arc = profile.get("arc", {}) if isinstance(profile.get("arc", {}), dict) else {}
        evidence = profile.get("evidence", {}) if isinstance(profile.get("evidence", {}), dict) else {}
        return (
            "# PROFILE\n"
            "<!-- Canonical markdown profile storage. Runtime loads this file before persona overlays. -->\n\n"
            "## Meta\n"
            f"- name: {profile.get('name', '')}\n"
            f"- novel_id: {profile.get('novel_id', '')}\n"
            f"- source_path: {profile.get('source_path', '')}\n\n"
            "## Core\n"
            f"- core_traits: {self._join_items(profile.get('core_traits', []))}\n"
            f"- values: {self._join_metric_map(profile.get('values', {}))}\n"
            f"- speech_style: {profile.get('speech_style', '')}\n"
            f"- identity_anchor: {profile.get('identity_anchor', '')}\n"
            f"- soul_goal: {profile.get('soul_goal', '')}\n"
            f"- worldview: {profile.get('worldview', '')}\n"
            f"- thinking_style: {profile.get('thinking_style', '')}\n\n"
            "## Deep Persona\n"
            f"- core_identity: {profile.get('core_identity', '')}\n"
            f"- faction_position: {profile.get('faction_position', '')}\n"
            f"- background_imprint: {profile.get('background_imprint', '')}\n"
            f"- world_rule_fit: {profile.get('world_rule_fit', '')}\n"
            f"- social_mode: {profile.get('social_mode', '')}\n"
            f"- hidden_desire: {profile.get('hidden_desire', '')}\n"
            f"- inner_conflict: {profile.get('inner_conflict', '')}\n"
            f"- story_role: {profile.get('story_role', '')}\n"
            f"- belief_anchor: {profile.get('belief_anchor', '')}\n"
            f"- private_self: {profile.get('private_self', '')}\n"
            f"- stance_stability: {profile.get('stance_stability', '')}\n"
            f"- reward_logic: {profile.get('reward_logic', '')}\n"
            f"- strengths: {self._join_items(profile.get('strengths', []))}\n"
            f"- weaknesses: {self._join_items(profile.get('weaknesses', []))}\n"
            f"- cognitive_limits: {self._join_items(profile.get('cognitive_limits', []))}\n"
            f"- fear_triggers: {self._join_items(profile.get('fear_triggers', []))}\n"
            f"- key_bonds: {self._join_items(profile.get('key_bonds', []))}\n"
            f"- action_style: {profile.get('action_style', '')}\n\n"
            "## Voice\n"
            f"- typical_lines: {self._join_items(profile.get('typical_lines', []))}\n"
            f"- decision_rules: {self._join_items(profile.get('decision_rules', []))}\n"
            f"- life_experience: {self._join_items(profile.get('life_experience', []))}\n"
            f"- taboo_topics: {self._join_items(profile.get('taboo_topics', []))}\n"
            f"- forbidden_behaviors: {self._join_items(profile.get('forbidden_behaviors', []))}\n"
            f"- cadence: {speech_habits.get('cadence', '')}\n"
            f"- signature_phrases: {self._join_items(speech_habits.get('signature_phrases', []))}\n"
            f"- sentence_openers: {self._join_items(speech_habits.get('sentence_openers', []))}\n"
            f"- connective_tokens: {self._join_items(speech_habits.get('connective_tokens', []))}\n"
            f"- sentence_endings: {self._join_items(speech_habits.get('sentence_endings', []))}\n"
            f"- forbidden_fillers: {self._join_items(speech_habits.get('forbidden_fillers', []))}\n"
            f"- anger_style: {emotion.get('anger_style', '')}\n"
            f"- joy_style: {emotion.get('joy_style', '')}\n"
            f"- grievance_style: {emotion.get('grievance_style', '')}\n\n"
            "## Arc\n"
            f"- arc_start: {self._join_metric_map(arc.get('start', {}))}\n"
            f"- arc_mid: {self._join_metric_map(arc.get('mid', {}))}\n"
            f"- arc_end: {self._join_metric_map(arc.get('end', {}))}\n"
            f"- arc_summary: {profile.get('arc_summary', '')}\n"
            f"- arc_confidence: {profile.get('arc_confidence', 0)}\n\n"
            "## Evidence\n"
            f"- description_count: {evidence.get('description_count', 0)}\n"
            f"- dialogue_count: {evidence.get('dialogue_count', 0)}\n"
            f"- thought_count: {evidence.get('thought_count', 0)}\n"
            f"- chunk_count: {evidence.get('chunk_count', 0)}\n"
        )

    def _render_soul_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# SOUL\n\n"
            "## Core\n"
            f"- identity_anchor: {profile.get('identity_anchor', '')}\n"
            f"- soul_goal: {profile.get('soul_goal', '')}\n"
            f"- worldview: {profile.get('worldview', '')}\n"
            f"- thinking_style: {profile.get('thinking_style', '')}\n"
            f"- taboo_topics: {self._join_items(profile.get('taboo_topics', []))}\n"
            f"- forbidden_behaviors: {self._join_items(profile.get('forbidden_behaviors', []))}\n"
        )

    def _render_goals_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# GOALS\n\n"
            "## Long Arc\n"
            f"- soul_goal: {profile.get('soul_goal', '')}\n"
            f"- decision_rules: {self._join_items(profile.get('decision_rules', []))}\n"
            f"- arc_end: {self._join_metric_map(profile.get('arc', {}).get('end', {}))}\n"
        )

    def _render_style_md(self, profile: Dict[str, Any]) -> str:
        speech_habits = profile.get("speech_habits", {}) if isinstance(profile.get("speech_habits", {}), dict) else {}
        return (
            "# STYLE\n\n"
            "## Expression\n"
            f"- speech_style: {profile.get('speech_style', '')}\n"
            f"- typical_lines: {self._join_items(profile.get('typical_lines', []))}\n"
            f"- cadence: {speech_habits.get('cadence', '')}\n"
            f"- signature_phrases: {self._join_items(speech_habits.get('signature_phrases', []))}\n"
            f"- sentence_openers: {self._join_items(speech_habits.get('sentence_openers', []))}\n"
            f"- connective_tokens: {self._join_items(speech_habits.get('connective_tokens', []))}\n"
            f"- sentence_endings: {self._join_items(speech_habits.get('sentence_endings', []))}\n"
            f"- forbidden_fillers: {self._join_items(speech_habits.get('forbidden_fillers', []))}\n"
        )

    def _render_trauma_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# TRAUMA\n\n"
            "## Boundaries\n"
            f"- taboo_topics: {self._join_items(profile.get('taboo_topics', []))}\n"
            f"- forbidden_behaviors: {self._join_items(profile.get('forbidden_behaviors', []))}\n"
            f"- grievance_style: {profile.get('emotion_profile', {}).get('grievance_style', '')}\n"
        )

    def _render_identity_md(self, profile: Dict[str, Any]) -> str:
        emotion = profile.get("emotion_profile", {}) if isinstance(profile.get("emotion_profile", {}), dict) else {}
        return (
            "# IDENTITY\n\n"
            "## Self\n"
            f"- identity_anchor: {profile.get('identity_anchor', '')}\n"
            f"- life_experience: {self._join_items(profile.get('life_experience', []))}\n"
            f"- core_traits: {self._join_items(profile.get('core_traits', []))}\n"
            f"- values: {self._join_metric_map(profile.get('values', {}))}\n"
            f"- anger_style: {emotion.get('anger_style', '')}\n"
            f"- joy_style: {emotion.get('joy_style', '')}\n"
            f"- grievance_style: {emotion.get('grievance_style', '')}\n"
        )

    def _render_background_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# BACKGROUND\n\n"
            "## World Position\n"
            f"- core_identity: {profile.get('core_identity', '')}\n"
            f"- faction_position: {profile.get('faction_position', '')}\n"
            f"- background_imprint: {profile.get('background_imprint', '')}\n"
            f"- world_rule_fit: {profile.get('world_rule_fit', '')}\n"
        )

    def _render_capability_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# CAPABILITY\n\n"
            "## Strength And Cost\n"
            f"- strengths: {self._join_items(profile.get('strengths', []))}\n"
            f"- weaknesses: {self._join_items(profile.get('weaknesses', []))}\n"
            f"- cognitive_limits: {self._join_items(profile.get('cognitive_limits', []))}\n"
            f"- action_style: {profile.get('action_style', '')}\n"
        )

    def _render_bonds_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# BONDS\n\n"
            "## Relationship Habit\n"
            f"- social_mode: {profile.get('social_mode', '')}\n"
            f"- key_bonds: {self._join_items(profile.get('key_bonds', []))}\n"
            f"- reward_logic: {profile.get('reward_logic', '')}\n"
            f"- belief_anchor: {profile.get('belief_anchor', '')}\n"
        )

    def _render_conflicts_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# CONFLICTS\n\n"
            "## Inner Pull\n"
            f"- hidden_desire: {profile.get('hidden_desire', '')}\n"
            f"- inner_conflict: {profile.get('inner_conflict', '')}\n"
            f"- fear_triggers: {self._join_items(profile.get('fear_triggers', []))}\n"
            f"- private_self: {profile.get('private_self', '')}\n"
        )

    def _render_role_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# ROLE\n\n"
            "## Plot Function\n"
            f"- story_role: {profile.get('story_role', '')}\n"
            f"- stance_stability: {profile.get('stance_stability', '')}\n"
            f"- world_rule_fit: {profile.get('world_rule_fit', '')}\n"
            f"- arc_end: {self._join_metric_map(profile.get('arc', {}).get('end', {}))}\n"
        )

    def _render_agents_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# AGENTS\n\n"
            "## Runtime Rules\n"
            "- group_chat_policy: 群聊中优先回应明确点名、关系最紧密或当前冲突最相关的对象\n"
            "- silence_policy: 未被点名且无强关联时可保持一拍沉默，不抢戏\n"
            "- correction_policy: 用户纠正与持续提示要写入 MEMORY，并在后续对话沿用\n"
            f"- decision_rules: {self._join_items(profile.get('decision_rules', []))}\n"
        )

    def _render_memory_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# MEMORY\n\n"
            "## Stable Memory\n"
            f"- canon_memory: {self._join_items(profile.get('life_experience', []))}\n"
            f"- relationship_updates: \n"
            "\n## Mutable Notes\n"
            "- user_edits: \n"
            "- notable_interactions: \n"
        )

    @staticmethod
    def _should_create_goals_md(profile: Dict[str, Any]) -> bool:
        return bool(str(profile.get("soul_goal", "")).strip() or profile.get("decision_rules"))

    @staticmethod
    def _should_create_style_md(profile: Dict[str, Any]) -> bool:
        return bool(str(profile.get("speech_style", "")).strip() or profile.get("typical_lines"))

    @staticmethod
    def _should_create_trauma_md(profile: Dict[str, Any]) -> bool:
        return bool(profile.get("taboo_topics") or profile.get("forbidden_behaviors"))

    def _extract_spoken_content(
        self,
        sentence: str,
        aliases: List[str],
        prev_sent: str = "",
        next_sent: str = "",
    ) -> str:
        verb_pattern = "|".join(re.escape(item) for item in self.speech_verbs)
        for alias in aliases:
            escaped = re.escape(alias)
            leading = rf"{escaped}[^\n“”\"]{{0,8}}(?:{verb_pattern})(?:[：:，,\s]{{0,2}})?[“\"](?P<quote>[^”\"]+)"
            for match in re.finditer(leading, sentence):
                if self._looks_like_subject_position(sentence, match.start()):
                    return str(match.group("quote") or "").strip()
            trailing = rf"[“\"](?P<quote>[^”\"]+)[”\"]?[^\n“”\"]{{0,8}}{escaped}[^\n“”\"]{{0,4}}(?:{verb_pattern})"
            for match in re.finditer(trailing, sentence):
                alias_start = match.start() + str(match.group(0)).find(alias)
                if self._looks_like_subject_position(sentence, alias_start):
                    return str(match.group("quote") or "").strip()
        return ""

    def _is_likely_spoken_by(
        self,
        sentence: str,
        aliases: List[str],
        prev_sent: str = "",
        next_sent: str = "",
    ) -> bool:
        verb_pattern = "|".join(re.escape(item) for item in self.speech_verbs)
        contexts = [sentence, f"{prev_sent}{sentence}", f"{sentence}{next_sent}", f"{prev_sent}{sentence}{next_sent}"]
        for alias in aliases:
            escaped = re.escape(alias)
            for context in contexts:
                outside_quotes = self._strip_quoted_content(context)
                patterns = [
                    rf"{escaped}[^\n“”\"]{{0,8}}(?:{verb_pattern})(?:[：:，,\s]{{0,2}})?",
                    rf"{escaped}[^\n“”\"]{{0,4}}[：:]",
                ]
                for pattern in patterns:
                    for match in re.finditer(pattern, outside_quotes):
                        if self._looks_like_subject_position(outside_quotes, match.start()):
                            return True
        return False

    def _looks_like_subject_position(self, text: str, alias_start: int) -> bool:
        prefix = text[:alias_start].rstrip()
        if not prefix:
            return True
        if prefix[-1] in "，。！？；：、“”\"'（）()[]【】<>《》 \t\r\n":
            return True
        tail = prefix[-4:]
        if any(tail.endswith(marker) for marker in self.object_leaders):
            return False
        if any(tail.endswith(marker) for marker in ("只见", "却说", "忽见", "便见", "原来", "那", "这", "又", "便")):
            return True
        return False

    def _text_mentions_any_alias(self, text: str, aliases: List[str]) -> bool:
        return any(self._contains_token(text, alias) for alias in aliases)

    @staticmethod
    def _contains_token(text: str, token: str) -> bool:
        return bool(token) and token in text

    @staticmethod
    def _count_token_mentions(text: str, token: str) -> int:
        return text.count(token) if token else 0

    @staticmethod
    def _strip_quoted_content(text: str) -> str:
        stripped = re.sub(r"“[^”]*”", "", text)
        return re.sub(r'"[^"]*"', "", stripped)

    @staticmethod
    def _looks_like_name(name: str) -> bool:
        if len(name) < 2 or len(name) > 4:
            return False
        bad = {"但是", "于是", "因为", "如果", "然后", "突然", "还是", "已经", "不能", "不会"}
        bad_suffixes = {"说", "道", "笑", "听", "问", "看", "想", "叹", "喊", "叫", "哭", "忙"}
        return name not in bad and name[-1] not in bad_suffixes

    @staticmethod
    def _empty_bucket() -> Dict[str, List[str]]:
        return {"descriptions": [], "dialogues": [], "thoughts": [], "timeline": []}

    def _value_dimensions(self) -> List[str]:
        dims = self.config.get("distillation.values_dimensions", []) or list(self.value_markers.keys())
        return [str(item).strip() for item in dims if str(item).strip()]

    @staticmethod
    def _join_items(items: Iterable[Any]) -> str:
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        return "；".join(cleaned)

    @staticmethod
    def _join_metric_map(items: Dict[str, Any]) -> str:
        if not isinstance(items, dict):
            return ""
        parts = []
        for key, value in items.items():
            key_text = str(key).strip()
            if key_text:
                parts.append(f"{key_text}={value}")
        return "；".join(parts)

    @staticmethod
    def _dedupe_texts(items: Iterable[str], limit: int) -> List[str]:
        cleaned = NovelDistiller._unique_texts(
            re.sub(r"\s+", " ", str(item).strip()) for item in items if str(item).strip()
        )
        return cleaned[:limit]

    @staticmethod
    def _unique_texts(items: Iterable[str]) -> List[str]:
        ordered: List[str] = []
        seen = set()
        for item in items:
            clean = str(item).strip()
            if not clean or clean in seen:
                continue
            ordered.append(clean)
            seen.add(clean)
        return ordered

    def _extract_signature_phrases(self, dialogues: List[str]) -> List[str]:
        scored: Dict[str, int] = {}
        for line in dialogues[:8]:
            parts = [part.strip("，。！？；：、\"' ") for part in re.split(r"[，。！？；：、]", line) if part.strip()]
            for idx, part in enumerate(parts):
                if not self._looks_like_signature_fragment(part):
                    continue
                score = 4 if idx == 0 else 2
                score += max(0, 8 - abs(len(part) - 5))
                if any(token in part for token in ("我", "这", "那", "只", "再", "罢", "未", "何", "可", "倒")):
                    score += 2
                if part.endswith(("罢了", "就是了", "未为不可", "何必", "不必", "也不迟")):
                    score += 3
                scored[part] = max(scored.get(part, 0), score)

        ordered = sorted(scored.items(), key=lambda item: (item[1], -len(item[0]), item[0]), reverse=True)
        return [text for text, _ in ordered[:4]]

    def _extract_dialogue_markers(
        self,
        dialogues: List[str],
        configured_patterns: tuple[str, ...],
        *,
        position: str,
    ) -> List[str]:
        scored: Dict[str, int] = {}
        patterns = [str(item).strip() for item in configured_patterns if str(item).strip()]

        for line in dialogues[:8]:
            parts = [part.strip("，。！？；：、\"' ") for part in re.split(r"[，。！？；：、]", line) if part.strip()]
            if not parts:
                continue
            clauses = []
            if position == "start":
                clauses = [(parts[0], True, False)]
            elif position == "end":
                clauses = [(parts[-1], False, True)]
            else:
                clauses = [(part, idx == 0, idx == len(parts) - 1) for idx, part in enumerate(parts)]

            for clause, is_opener, is_closer in clauses:
                matched_configured = False
                for marker in patterns:
                    if not marker:
                        continue
                    if position == "start" and clause.startswith(marker):
                        scored[marker] = scored.get(marker, 0) + 6 + len(marker)
                        matched_configured = True
                    elif position == "end" and clause.endswith(marker):
                        scored[marker] = scored.get(marker, 0) + 6 + len(marker)
                        matched_configured = True
                    elif position == "any" and marker in clause:
                        scored[marker] = scored.get(marker, 0) + 2 + clause.count(marker)

                if position == "any" or matched_configured:
                    continue
                fallback = self._fallback_fragment_candidate(clause, position=position)
                if fallback:
                    score = self._fallback_fragment_score(fallback, is_opener=is_opener, is_closer=is_closer)
                    scored[fallback] = max(scored.get(fallback, 0), score)

        ordered = sorted(scored.items(), key=lambda item: (item[1], -len(item[0]), item[0]), reverse=True)
        return [text for text, _ in ordered[:4]]

    def _fallback_fragment_candidate(self, clause: str, *, position: str) -> str:
        text = str(clause or "").strip()
        if len(text) < 2:
            return ""
        lengths = (4, 3, 2)
        for size in lengths:
            if len(text) < size:
                continue
            candidate = text[:size] if position != "end" else text[-size:]
            if self._looks_like_dialogue_marker(candidate) and self._fallback_fragment_allowed(candidate, position=position):
                return candidate
        return ""

    def _looks_like_dialogue_marker(self, fragment: str) -> bool:
        text = str(fragment or "").strip()
        if len(text) < 2 or len(text) > 8:
            return False
        if text in self.fragment_stopwords:
            return False
        if any(token in text for token in ("《", "》", "<", ">", "<<", ">>")):
            return False
        if any(ch.isdigit() for ch in text):
            return False
        return True

    def _fallback_fragment_score(self, fragment: str, *, is_opener: bool, is_closer: bool) -> int:
        score = max(1, 8 - abs(len(fragment) - 4))
        if is_opener:
            score += 2
        if is_closer:
            score += 1
        if fragment[:1] in self.preferred_leading_chars:
            score += 3
        if fragment[-1:] in self.preferred_trailing_chars:
            score += 2
        return score

    def _fallback_fragment_allowed(self, fragment: str, *, position: str) -> bool:
        if position == "start":
            return fragment[:1] in self.preferred_leading_chars and (len(fragment) <= 3 or fragment[-1:] in self.preferred_trailing_chars)
        if position == "end":
            return fragment[-1:] in self.preferred_trailing_chars
        return False

    @staticmethod
    def _looks_like_signature_fragment(fragment: str) -> bool:
        text = str(fragment or "").strip()
        if len(text) < 2 or len(text) > 12:
            return False
        if any(token in text for token in ("《", "》", "<", ">", "“", "”", "<<", ">>")):
            return False
        if any(ch.isdigit() for ch in text):
            return False
        too_generic = {
            "不可",
            "可以",
            "只是",
            "不过",
            "如今",
            "今日",
            "明日",
            "知道",
            "一个",
            "这个",
            "那个",
            "这样",
            "那里",
            "这里",
            "不是",
            "没有",
            "不得",
            "你们",
            "我们",
            "他们",
        }
        return text not in too_generic

    @staticmethod
    def _top_dimensions(values: Dict[str, int], count: int) -> List[str]:
        if not values:
            return ["责任"] * count
        ordered = sorted(values.items(), key=lambda item: int(item[1]), reverse=True)
        top = [name for name, _ in ordered[:count]]
        while len(top) < count:
            top.append(top[0] if top else "责任")
        return top
