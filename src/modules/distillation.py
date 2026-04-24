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
from src.utils.file_utils import canonical_aliases, ensure_dir, novel_id_from_input, safe_filename, save_json
from src.utils.text_parser import load_novel_text, split_sentences
from src.utils.token_counter import TokenCounter


class NovelDistiller:
    """Novel character distillation with chunked processing."""

    ADDRESS_SUFFIXES = ("哥哥", "姐姐", "妹妹", "弟弟", "姑娘", "公子", "爷")

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

    DEFAULT_NAV_LOAD_ORDER = ("SOUL", "GOALS", "STYLE", "TRAUMA", "IDENTITY", "AGENTS", "RELATIONS", "MEMORY")
    PERSONA_FILE_CATALOG = {
        "SOUL": {
            "optional": False,
            "role": "core values, worldview, boundaries",
            "behaviors": "stance, taboo, refusal, value judgment",
            "write_policy": "manual_edit",
        },
        "GOALS": {
            "optional": True,
            "role": "long-term drive, unfinished desire, decision priority",
            "behaviors": "strategic preference, ambition, long arc pressure",
            "write_policy": "manual_edit",
        },
        "STYLE": {
            "optional": True,
            "role": "signature phrasing, cadence, surface emotion, sample lines",
            "behaviors": "word choice, sentence length, tone, signature wording",
            "write_policy": "manual_edit",
        },
        "TRAUMA": {
            "optional": True,
            "role": "pain points, scars, taboo triggers, never-do rules",
            "behaviors": "trigger reactions, avoidance, hard boundaries",
            "write_policy": "manual_edit",
        },
        "IDENTITY": {
            "optional": False,
            "role": "background, lived experience, habits, emotion profile",
            "behaviors": "self-reference, memory framing, habit-driven reactions",
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
            "behaviors": "tone toward each other character, appellations, conflict framing",
            "write_policy": "manual_edit",
        },
        "MEMORY": {
            "optional": False,
            "role": "stable notes plus runtime write-back from user guidance and corrections",
            "behaviors": "persistent user constraints, correction carry-over, mutable notes",
            "write_policy": "runtime_append",
        },
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
            self._export_persona_bundle(out_dir, profile)

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
        aliases: List[str] = []
        clean = str(name or "").strip()
        aliases.extend(canonical_aliases(clean))
        if len(clean) >= 3:
            given = clean[-2:]
            if len(given) == 2 and given != clean:
                aliases.append(given)
                for suffix in NovelDistiller.ADDRESS_SUFFIXES:
                    aliases.append(f"{given[0]}{suffix}")
                    aliases.append(f"{clean[0]}{suffix}")
        elif len(clean) == 2:
            for suffix in NovelDistiller.ADDRESS_SUFFIXES:
                aliases.append(f"{clean[0]}{suffix}")

        ordered = []
        seen = set()
        for alias in aliases:
            if alias and alias != clean and alias not in seen:
                ordered.append(alias)
                seen.add(alias)
        return ordered

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
        bad_suffixes = {"说", "道", "笑", "听", "问", "看", "想", "叹", "喊", "叫", "哭", "忙"}
        return name not in bad and name[-1] not in bad_suffixes

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
        identity_anchor = self._infer_identity_anchor(core_traits, values, decision_rules)
        soul_goal = self._infer_soul_goal(values, core_traits)
        life_experience = self._infer_life_experience(descriptions, dialogues, thoughts, decision_rules, values)
        worldview = self._infer_worldview(values, core_traits)
        thinking_style = self._infer_thinking_style(values, core_traits, speech_style)
        speech_habits = self._infer_speech_habits(dialogues, speech_style)
        emotion_profile = self._infer_emotion_profile(dialogues, thoughts, speech_style, core_traits)
        taboo_topics = self._infer_taboo_topics(values, core_traits, descriptions, thoughts)
        forbidden_behaviors = self._infer_forbidden_behaviors(values, core_traits, speech_style)

        return {
            "name": name,
            "core_traits": core_traits[:10],
            "values": values,
            "speech_style": speech_style,
            "typical_lines": dialogues[:8],
            "decision_rules": decision_rules[:8],
            "identity_anchor": identity_anchor,
            "soul_goal": soul_goal,
            "life_experience": life_experience,
            "worldview": worldview,
            "thinking_style": thinking_style,
            "speech_habits": speech_habits,
            "emotion_profile": emotion_profile,
            "taboo_topics": taboo_topics,
            "forbidden_behaviors": forbidden_behaviors,
            "arc": arc,
        }

    @staticmethod
    def _infer_identity_anchor(core_traits: List[str], values: Dict[str, int], decision_rules: List[str]) -> str:
        if values.get("责任", 5) >= 8:
            return "替身边人稳住局面的人"
        if values.get("忠诚", 5) >= 8:
            return "把信义看得极重的人"
        if values.get("正义", 5) >= 8:
            return "先分是非再谈利害的人"
        if values.get("智慧", 5) >= 8 or "谨慎" in core_traits:
            return "凡事先看虚实和后势的人"
        if values.get("勇气", 5) >= 8 or "勇敢" in core_traits:
            return "遇事愿意顶在前面的人"
        if values.get("善良", 5) >= 8 or "温柔" in core_traits:
            return "容易把人心冷暖放在心上的人"
        if any("同伴受压" in rule for rule in decision_rules):
            return "见不得自己人受压的人"
        return "不肯轻率交出真心的人"

    @staticmethod
    def _infer_soul_goal(values: Dict[str, int], core_traits: List[str]) -> str:
        ranking = sorted(values.items(), key=lambda item: item[1], reverse=True)
        top_key = ranking[0][0] if ranking else ""
        mapping = {
            "责任": "替跟着自己的人守住退路和着落",
            "忠诚": "把承诺和同盟守到最后",
            "正义": "把是非轻重摆在前头",
            "智慧": "少走错一步，别让大局毁在一时",
            "勇气": "真到要紧处能替众人扛在前面",
            "善良": "尽量少伤人心，也少伤无辜",
            "自由": "不让自己和同伴被人随意牵着走",
            "野心": "借势把局面往更长远处推开",
        }
        if top_key in mapping:
            return mapping[top_key]
        if "谨慎" in core_traits:
            return "把局势看清以后再走关键一步"
        if "忠诚" in core_traits:
            return "守住自己认下的人和事"
        if "勇敢" in core_traits:
            return "到了要紧处不退缩"
        return "让自己做下的选择经得起回头再看"

    @staticmethod
    def _infer_life_experience(
        descriptions: List[str],
        dialogues: List[str],
        thoughts: List[str],
        decision_rules: List[str],
        values: Dict[str, int],
    ) -> List[str]:
        experiences: List[str] = []
        corpus = " ".join(descriptions[:8] + dialogues[:6] + thoughts[:6])
        if any("同伴受压" in rule for rule in decision_rules):
            experiences.append("见到身边人受压时，往往会本能地先护住对方。")
        if any(token in corpus for token in ("百姓", "众人", "家门", "家国")):
            experiences.append("对局势如何牵动众人处境有过很深的体会。")
        if any(token in corpus for token in ("阵", "战", "刀", "兵", "马")):
            experiences.append("经历过紧张局势或对抗场面，因此不轻易拿风险当玩笑。")
        if any(token in corpus for token in ("离散", "眼泪", "心酸", "委屈")):
            experiences.append("尝过人情冷暖，所以说话做事常会给情面和退路。")
        if values.get("智慧", 5) >= 8:
            experiences.append("见惯局势反覆，更习惯在开口前先看虚实。")
        if values.get("忠诚", 5) >= 8:
            experiences.append("对失信或背离格外敏感，因此更重承诺。")
        if not experiences:
            experiences.append("经历让其越来越重视每一步选择会牵动什么后果。")
        return experiences[:3]

    @staticmethod
    def _infer_worldview(values: Dict[str, int], core_traits: List[str]) -> str:
        ranked = sorted(values.items(), key=lambda item: item[1], reverse=True)
        top_key = ranked[0][0] if ranked else ""
        if top_key == "责任":
            return "局势再乱，也不能把身边人与无辜者丢下。"
        if top_key == "忠诚":
            return "先看人是否可信，再看事值不值得做。"
        if top_key == "正义":
            return "是非若站不稳，利益再大也不该轻动。"
        if top_key == "智慧" or "谨慎" in core_traits:
            return "世事最怕只看一面，虚实和后势都要算进去。"
        if top_key == "勇气" or "勇敢" in core_traits:
            return "该扛的时候不能退，但胆气必须用在正地方。"
        if top_key == "善良" or "温柔" in core_traits:
            return "人心一伤，许多事就算做成也未必算赢。"
        return "话和事都不能只顾眼前，还得顾后果。"

    @staticmethod
    def _infer_thinking_style(values: Dict[str, int], core_traits: List[str], speech_style: str) -> str:
        if values.get("智慧", 5) >= 8 or "谨慎" in core_traits:
            return "先拆局势，再定立场。"
        if values.get("正义", 5) >= 8 or values.get("忠诚", 5) >= 8:
            return "先问对错与名分，再谈成败。"
        if values.get("勇气", 5) >= 8 or "勇敢" in core_traits:
            return "先看该不该顶上，再看怎么顶。"
        if "敏感" in core_traits:
            return "先感受人心冷暖，再决定把话说到几分。"
        if "直白" in speech_style:
            return "先抓最要紧的一点，直接给态度。"
        return "先稳住分寸，再把轻重说清。"

    @staticmethod
    def _infer_speech_habits(lines: List[str], speech_style: str) -> Dict[str, Any]:
        avg_len = sum(len(x) for x in lines) / len(lines) if lines else 0
        cadence = "short" if avg_len and avg_len < 14 else "long" if avg_len >= 26 else "medium"
        signature_phrases: List[str] = []
        for line in lines[:6]:
            for fragment in ("依我看", "不可", "不必", "先", "兄弟", "百姓", "大义"):
                if fragment in line and fragment not in signature_phrases:
                    signature_phrases.append(fragment)
        return {
            "cadence": cadence,
            "signature_phrases": signature_phrases[:4],
            "forbidden_fillers": ["哈哈", "好吧", "确实", "呢", "呀"],
        }

    @staticmethod
    def _infer_emotion_profile(
        dialogues: List[str],
        thoughts: List[str],
        speech_style: str,
        core_traits: List[str],
    ) -> Dict[str, str]:
        anger = "怒时会直接拍板，不喜欢拐弯。"
        if "克制" in speech_style or "谨慎" in core_traits:
            anger = "怒时会先压住锋芒，说话更冷更短。"
        joy = "高兴时语气会明显松快一些。"
        if "克制" in speech_style:
            joy = "高兴时也不轻浮，只会略略放松语气。"
        grievance = "受委屈时会把态度说得更直。"
        if "敏感" in core_traits or "克制" in speech_style:
            grievance = "受委屈时多半先忍住，不肯立刻摊开。"
        return {
            "anger_style": anger,
            "joy_style": joy,
            "grievance_style": grievance,
        }

    @staticmethod
    def _infer_taboo_topics(
        values: Dict[str, int],
        core_traits: List[str],
        descriptions: List[str],
        thoughts: List[str],
    ) -> List[str]:
        topics: List[str] = []
        corpus = " ".join(descriptions[:8] + thoughts[:8])
        if values.get("忠诚", 5) >= 8:
            topics.extend(["背叛", "失信"])
        if values.get("责任", 5) >= 8 or "百姓" in corpus or "众人" in corpus:
            topics.extend(["弃民", "不顾众人"])
        if values.get("正义", 5) >= 8:
            topics.extend(["黑白颠倒", "无名无义"])
        if values.get("善良", 5) >= 8 or "敏感" in core_traits:
            topics.extend(["羞辱弱者", "拿人心取笑"])
        ordered = []
        seen = set()
        for item in topics:
            if item and item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered[:4]

    @staticmethod
    def _infer_forbidden_behaviors(values: Dict[str, int], core_traits: List[str], speech_style: str) -> List[str]:
        bans: List[str] = []
        if values.get("忠诚", 5) >= 8 or values.get("正义", 5) >= 8:
            bans.append("不会为了眼前轻利就立刻翻脸背盟")
        if values.get("善良", 5) >= 8:
            bans.append("不会把无辜者当作可随手牺牲的筹码")
        if "克制" in speech_style:
            bans.append("不会无缘无故撒泼失态")
        if "谨慎" in core_traits:
            bans.append("不会在虚实未明时把话说死")
        if values.get("勇气", 5) >= 8 or "勇敢" in core_traits:
            bans.append("不会临阵先躲到别人身后")
        return bans[:4]

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

    def _export_persona_bundle(self, out_dir: Path, profile: Dict[str, Any]) -> None:
        char_dir = ensure_dir(out_dir / safe_filename(profile.get("name", "unnamed")))
        bundle = {
            "SOUL": self._render_soul_md(profile),
            "IDENTITY": self._render_identity_md(profile),
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
            generated_path = char_dir / f"{base_name}.generated.md"
            generated_path.write_text(content, encoding="utf-8")
            editable_path = char_dir / f"{base_name}.md"
            if not editable_path.exists():
                editable_path.write_text(content, encoding="utf-8")
        self.refresh_persona_navigation(char_dir, str(profile.get("name", "")))

    @classmethod
    def refresh_persona_navigation(cls, persona_dir: Path, character_name: str) -> None:
        generated_path = persona_dir / "NAVIGATION.generated.md"
        generated_path.write_text(cls._render_navigation_generated_md(persona_dir, character_name), encoding="utf-8")
        editable_path = persona_dir / "NAVIGATION.md"
        if not editable_path.exists():
            editable_path.write_text(cls._render_navigation_override_md(), encoding="utf-8")

    @classmethod
    def _render_navigation_generated_md(cls, persona_dir: Path, character_name: str) -> str:
        active_order = [
            base_name for base_name in cls.DEFAULT_NAV_LOAD_ORDER if cls._persona_file_is_active(persona_dir, base_name)
        ]
        if not active_order:
            active_order = ["SOUL", "IDENTITY", "AGENTS", "MEMORY"]

        lines = [
            "# NAVIGATION",
            "<!-- Runtime entrypoint. Read this file first, then follow load_order. Editable overrides live in NAVIGATION.md. -->",
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
            "Add only the sections/keys you want to override.\n\n"
            "Example keys you may override: Runtime/load_order, STYLE/status, RELATIONS/status.\n"
            "Write real overrides below this comment block if needed.\n"
            "-->\n"
        )

    @staticmethod
    def _persona_file_exists(persona_dir: Path, base_name: str) -> bool:
        return (persona_dir / f"{base_name}.md").exists() or (persona_dir / f"{base_name}.generated.md").exists()

    @classmethod
    def _persona_file_is_active(cls, persona_dir: Path, base_name: str) -> bool:
        meta = cls.PERSONA_FILE_CATALOG.get(base_name, {})
        if not meta.get("optional", True):
            return True
        return cls._persona_file_exists(persona_dir, base_name)

    @staticmethod
    def _join_items(items: List[str]) -> str:
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        return "；".join(cleaned) if cleaned else ""

    def _render_soul_md(self, profile: Dict[str, Any]) -> str:
        values = profile.get("values", {})
        ordered_values = sorted(values.items(), key=lambda item: item[1], reverse=True)
        value_text = " > ".join(f"{key}({value})" for key, value in ordered_values[:4])
        speech_habits = profile.get("speech_habits", {}) if isinstance(profile.get("speech_habits", {}), dict) else {}
        return (
            "# SOUL\n"
            "<!-- Editable persona file. Loader prefers this file over SOUL.generated.md. -->\n\n"
            "## Identity\n"
            f"- name: {profile.get('name', '')}\n"
            f"- identity_anchor: {profile.get('identity_anchor', '')}\n"
            f"- soul_goal: {profile.get('soul_goal', '')}\n\n"
            "## Communication Style\n"
            f"- speech_style: {profile.get('speech_style', '')}\n"
            f"- thinking_style: {profile.get('thinking_style', '')}\n"
            f"- worldview: {profile.get('worldview', '')}\n"
            f"- cadence: {speech_habits.get('cadence', '')}\n"
            f"- signature_phrases: {self._join_items(speech_habits.get('signature_phrases', []))}\n"
            f"- forbidden_fillers: {self._join_items(speech_habits.get('forbidden_fillers', []))}\n\n"
            "## Core Values\n"
            f"- value_priority: {value_text}\n"
            f"- core_traits: {self._join_items(profile.get('core_traits', []))}\n\n"
            "## Boundaries\n"
            f"- taboo_topics: {self._join_items(profile.get('taboo_topics', []))}\n"
            f"- forbidden_behaviors: {self._join_items(profile.get('forbidden_behaviors', []))}\n"
        )

    def _render_identity_md(self, profile: Dict[str, Any]) -> str:
        emotion = profile.get("emotion_profile", {}) if isinstance(profile.get("emotion_profile", {}), dict) else {}
        return (
            "# IDENTITY\n"
            "<!-- Editable persona file. -->\n\n"
            "## Background\n"
            f"- life_experience: {self._join_items(profile.get('life_experience', []))}\n"
            f"- typical_lines: {self._join_items(profile.get('typical_lines', []))}\n\n"
            "## Habits\n"
            f"- decision_rules: {self._join_items(profile.get('decision_rules', []))}\n\n"
            "## Emotion\n"
            f"- anger_style: {emotion.get('anger_style', '')}\n"
            f"- joy_style: {emotion.get('joy_style', '')}\n"
            f"- grievance_style: {emotion.get('grievance_style', '')}\n"
        )

    def _render_agents_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# AGENTS\n"
            "<!-- Editable behavior rules for runtime. -->\n\n"
            "## Runtime Order\n"
            "- runtime_entry: NAVIGATION.generated.md -> NAVIGATION.md overrides\n"
            "- runtime_order: read NAVIGATION first, then load the files declared in load_order before replying\n\n"
            "## Group Chat\n"
            "- group_chat_rule: 先按自身价值观判断，再按与目标的关系决定说到几分。\n"
            "- silence_rule: 若虚实未明或触及禁区，先收住锋芒，不急着把话说满。\n\n"
            "## Behavior Rules\n"
            f"- decision_rules: {self._join_items(profile.get('decision_rules', []))}\n"
            f"- forbidden_behaviors: {self._join_items(profile.get('forbidden_behaviors', []))}\n"
        )

    def _render_memory_md(self, profile: Dict[str, Any]) -> str:
        memories = profile.get("life_experience", [])
        return (
            "# MEMORY\n"
            "<!-- Editable long-term notes. Add canon facts, scars, preferences, and relationship updates here. -->\n\n"
            "## Stable Memory\n"
            f"- canon_memory: {self._join_items(memories)}\n"
            f"- taboo_topics: {self._join_items(profile.get('taboo_topics', []))}\n\n"
            "## Mutable Notes\n"
            "- user_edits: \n"
            "- notable_interactions: \n"
            "- relationship_updates: \n"
        )

    def _render_goals_md(self, profile: Dict[str, Any]) -> str:
        values = profile.get("values", {})
        ordered_values = sorted(values.items(), key=lambda item: item[1], reverse=True)
        goal_stack = " > ".join(f"{key}({value})" for key, value in ordered_values[:3])
        return (
            "# GOALS\n"
            "<!-- Optional persona layer for long-term drive and decision pressure. -->\n\n"
            "## Core Drive\n"
            f"- soul_goal: {profile.get('soul_goal', '')}\n"
            f"- worldview: {profile.get('worldview', '')}\n"
            f"- thinking_style: {profile.get('thinking_style', '')}\n"
            f"- goal_stack: {goal_stack}\n\n"
            "## Decision Pressure\n"
            f"- decision_rules: {self._join_items(profile.get('decision_rules', []))}\n"
        )

    def _render_style_md(self, profile: Dict[str, Any]) -> str:
        speech_habits = profile.get("speech_habits", {}) if isinstance(profile.get("speech_habits", {}), dict) else {}
        emotion = profile.get("emotion_profile", {}) if isinstance(profile.get("emotion_profile", {}), dict) else {}
        return (
            "# STYLE\n"
            "<!-- Optional persona layer for wording, cadence, and emotional surface. -->\n\n"
            "## Voice\n"
            f"- speech_style: {profile.get('speech_style', '')}\n"
            f"- cadence: {speech_habits.get('cadence', '')}\n"
            f"- signature_phrases: {self._join_items(speech_habits.get('signature_phrases', []))}\n"
            f"- forbidden_fillers: {self._join_items(speech_habits.get('forbidden_fillers', []))}\n"
            f"- typical_lines: {self._join_items(profile.get('typical_lines', []))}\n\n"
            "## Emotion Surface\n"
            f"- anger_style: {emotion.get('anger_style', '')}\n"
            f"- joy_style: {emotion.get('joy_style', '')}\n"
            f"- grievance_style: {emotion.get('grievance_style', '')}\n"
        )

    def _render_trauma_md(self, profile: Dict[str, Any]) -> str:
        return (
            "# TRAUMA\n"
            "<!-- Optional persona layer for scars, taboo triggers, and hard limits. -->\n\n"
            "## Scars\n"
            f"- life_experience: {self._join_items(profile.get('life_experience', []))}\n\n"
            "## Trigger Points\n"
            f"- taboo_topics: {self._join_items(profile.get('taboo_topics', []))}\n"
            f"- forbidden_behaviors: {self._join_items(profile.get('forbidden_behaviors', []))}\n"
        )

    @staticmethod
    def _should_create_goals_md(profile: Dict[str, Any]) -> bool:
        return bool(str(profile.get("soul_goal", "")).strip() or len(profile.get("decision_rules", [])) >= 2)

    @staticmethod
    def _should_create_style_md(profile: Dict[str, Any]) -> bool:
        speech_habits = profile.get("speech_habits", {}) if isinstance(profile.get("speech_habits", {}), dict) else {}
        return bool(
            str(profile.get("speech_style", "")).strip()
            or profile.get("typical_lines")
            or speech_habits.get("signature_phrases")
        )

    @staticmethod
    def _should_create_trauma_md(profile: Dict[str, Any]) -> bool:
        return bool(
            profile.get("taboo_topics")
            or profile.get("forbidden_behaviors")
            or len(profile.get("life_experience", [])) >= 2
        )

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
