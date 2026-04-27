#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.core.contracts import CorrectionService, RuleProvider


class Speaker:
    """Generate role replies from persona markdown, relation state, and editable rules."""

    DEFAULT_PRIORITY_ORDER = ("责任", "忠诚", "正义", "智慧", "勇气", "善良", "自由", "野心")

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        correction_service: Optional[CorrectionService] = None,
        rulebook: Optional[RuleProvider] = None,
    ):
        self.config = config or Config()
        if correction_service is None or rulebook is None:
            raise ValueError("Speaker requires injected correction_service and rulebook")
        self.rulebook = rulebook
        self.correction_service = correction_service

        speaker_rules = self.rulebook.section("speaker")
        self.question_tokens = tuple(speaker_rules.get("question_tokens", []))
        self.war_tokens = tuple(speaker_rules.get("war_tokens", []))
        self.rest_tokens = tuple(speaker_rules.get("rest_tokens", []))
        self.view_tokens = tuple(speaker_rules.get("view_tokens", []))
        self.care_tokens = tuple(speaker_rules.get("care_tokens", []))
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
        self.durable_guidance_tokens = tuple(speaker_rules.get("durable_guidance_tokens", []))
        self.single_chat_markers = tuple(speaker_rules.get("single_chat_markers", []))
        self.priority_order = tuple(
            item
            for item in self.config.get("distillation.values_dimensions", list(self.DEFAULT_PRIORITY_ORDER))
            if str(item).strip()
        ) or self.DEFAULT_PRIORITY_ORDER
        self.trait_priority_map = {
            str(key).strip(): str(value).strip()
            for key, value in speaker_rules.get("trait_priority_map", {}).items()
            if str(key).strip() and str(value).strip()
        }
        self.archetypes = dict(self.rulebook.get("distillation", "archetypes", {}))

    def generate(
        self,
        character_profile: Dict[str, Any],
        context: str,
        history: List[Dict[str, str]],
        target_name: str = "",
        relation_state: Optional[Dict[str, Any]] = None,
        relation_hint: str = "",
    ) -> str:
        relation_state = relation_state or {}
        name = str(character_profile.get("name", "角色")).strip() or "角色"
        recent = history[-6:]
        recent_text = "\n".join(f"{item.get('speaker', '')}: {item.get('message', '')}" for item in recent)
        similar = self.correction_service.search_similar_corrections(
            recent_text,
            character=name,
            target=target_name or None,
            top_k=2,
        )

        voice = self._build_voice(character_profile)
        target_display = self._preferred_target_name(name, target_name, relation_state)
        topic = self._classify_topic(context)

        segments = [
            self._opening_line(name, target_display, voice, relation_state, bool(similar)),
            self._taboo_line(context, voice),
            self._stance_line(context, voice, relation_state, topic),
            self._relation_line(target_display, voice, relation_state),
            self._memory_line(character_profile, voice, relation_hint),
            self._drive_line(voice, topic),
        ]
        return self._compose_reply(segments, voice)

    @staticmethod
    def _preferred_target_name(speaker_name: str, target_name: str, relation_state: Dict[str, Any]) -> str:
        appellations = relation_state.get("appellations", {})
        if not isinstance(appellations, dict):
            return target_name
        preferred = str(appellations.get(f"{speaker_name}->{target_name}", "")).strip()
        return preferred or target_name

    def _build_voice(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        values = {
            str(key).strip(): self._safe_int(value, default=5)
            for key, value in profile.get("values", {}).items()
            if str(key).strip()
        }
        traits = [str(item).strip() for item in profile.get("core_traits", []) if str(item).strip()]
        decision_rules = [str(item).strip() for item in profile.get("decision_rules", []) if str(item).strip()]
        typical_lines = [str(item).strip() for item in profile.get("typical_lines", []) if str(item).strip()]
        speech_style = str(profile.get("speech_style", "")).strip()
        speech_habits = dict(profile.get("speech_habits", {})) if isinstance(profile.get("speech_habits", {}), dict) else {}
        emotion_profile = dict(profile.get("emotion_profile", {})) if isinstance(profile.get("emotion_profile", {}), dict) else {}
        taboo_topics = [str(item).strip() for item in profile.get("taboo_topics", []) if str(item).strip()]
        forbidden_behaviors = [str(item).strip() for item in profile.get("forbidden_behaviors", []) if str(item).strip()]
        user_edits = [str(item).strip() for item in profile.get("user_edits", []) if str(item).strip()]
        notable_interactions = [str(item).strip() for item in profile.get("notable_interactions", []) if str(item).strip()]
        relationship_updates = [str(item).strip() for item in profile.get("relationship_updates", []) if str(item).strip()]

        priority_scores = {item: values.get(item, 5) for item in self.priority_order}
        for trait in traits:
            mapped = self.trait_priority_map.get(trait)
            if mapped:
                priority_scores[mapped] = priority_scores.get(mapped, 5) + 2
        ordered = sorted(
            self.priority_order,
            key=lambda item: (priority_scores.get(item, 5), -self.priority_order.index(item)),
            reverse=True,
        )
        primary = ordered[0] if ordered else "责任"
        secondary = ordered[1] if len(ordered) > 1 else primary

        cadence = str(speech_habits.get("cadence", "")).strip()
        signature_phrases = [str(item).strip() for item in speech_habits.get("signature_phrases", []) if str(item).strip()]
        if not signature_phrases:
            signature_phrases = self._extract_signature_phrases(typical_lines)
        sentence_openers = [
            str(item).strip() for item in speech_habits.get("sentence_openers", []) if str(item).strip()
        ] or self._extract_dialogue_markers(typical_lines, self.opener_patterns, position="start")
        connective_tokens = [
            str(item).strip() for item in speech_habits.get("connective_tokens", []) if str(item).strip()
        ] or self._extract_dialogue_markers(typical_lines, self.connective_patterns, position="any")
        sentence_endings = [
            str(item).strip() for item in speech_habits.get("sentence_endings", []) if str(item).strip()
        ] or self._extract_dialogue_markers(typical_lines, self.ending_patterns, position="end")
        forbidden_fillers = [
            str(item).strip()
            for item in speech_habits.get("forbidden_fillers", [])
            if str(item).strip()
        ] or list(self.generic_fillers)

        direct = "直白" in speech_style or cadence == "short" or primary == "勇气"
        restrained = "克制" in speech_style or primary in {"责任", "智慧", "忠诚", "正义"}
        expansive = cadence == "long" or ("铺陈" in speech_style and not direct)
        warm = primary in {"善良", "责任"} or values.get("善良", 5) >= 7

        worldview = str(profile.get("worldview", "")).strip() or self._worldview_text(primary, secondary, values, traits)
        belief_anchor = str(profile.get("belief_anchor", "")).strip() or worldview
        thinking_style = str(profile.get("thinking_style", "")).strip() or self._thinking_style_text(
            primary,
            traits,
            speech_style,
        )
        goal = str(profile.get("soul_goal", "")).strip() or self._goal_text(primary, secondary)
        hidden_desire = str(profile.get("hidden_desire", "")).strip()
        role = str(profile.get("identity_anchor", "")).strip() or self._role_text(primary, secondary)
        experience = self._experience_text(profile, primary, secondary)
        action_style = str(profile.get("action_style", "")).strip()
        social_mode = str(profile.get("social_mode", "")).strip()
        private_self = str(profile.get("private_self", "")).strip()
        reward_logic = str(profile.get("reward_logic", "")).strip()
        story_role = str(profile.get("story_role", "")).strip()
        stance_stability = str(profile.get("stance_stability", "")).strip()

        direct, restrained, cadence, worldview, thinking_style, signature_phrases, taboo_topics, forbidden_behaviors = (
            self._apply_user_edits(
                user_edits,
                direct,
                restrained,
                cadence or ("short" if direct else "long" if expansive else "medium"),
                worldview,
                thinking_style,
                signature_phrases,
                taboo_topics,
                forbidden_behaviors,
            )
        )

        archetype = self._infer_archetype(profile, traits, speech_style, signature_phrases)

        return {
            "name": str(profile.get("name", "角色")).strip() or "角色",
            "traits": traits,
            "values": values,
            "decision_rules": decision_rules,
            "typical_lines": typical_lines,
            "speech_style": speech_style,
            "speech_habits": {
                "cadence": cadence,
                "signature_phrases": signature_phrases[:4],
                "sentence_openers": sentence_openers[:4],
                "connective_tokens": connective_tokens[:4],
                "sentence_endings": sentence_endings[:4],
                "forbidden_fillers": forbidden_fillers,
            },
            "emotion_profile": emotion_profile,
            "taboo_topics": taboo_topics[:6],
            "forbidden_behaviors": forbidden_behaviors[:6],
            "user_edits": user_edits,
            "notable_interactions": notable_interactions,
            "relationship_updates": relationship_updates,
            "primary_priority": primary,
            "secondary_priority": secondary,
            "direct": direct,
            "restrained": restrained,
            "expansive": expansive,
            "warm": warm,
            "worldview": worldview,
            "belief_anchor": belief_anchor,
            "thinking_style": thinking_style,
            "goal": goal,
            "hidden_desire": hidden_desire,
            "role": role,
            "experience": experience,
            "action_style": action_style,
            "social_mode": social_mode,
            "private_self": private_self,
            "reward_logic": reward_logic,
            "story_role": story_role,
            "stance_stability": stance_stability,
            "archetype": archetype,
        }

    def _infer_archetype(
        self,
        profile: Dict[str, Any],
        traits: List[str],
        speech_style: str,
        signature_phrases: List[str],
    ) -> str:
        corpus = " ".join(
            [
                str(profile.get("name", "")),
                speech_style,
                " ".join(traits),
                " ".join(signature_phrases),
                " ".join(str(item) for item in profile.get("typical_lines", [])),
            ]
        )
        best_name = "default"
        best_score = 0
        for archetype_name, config in self.archetypes.items():
            markers = [str(item).strip() for item in config.get("markers", []) if str(item).strip()]
            traits_hint = [str(item).strip() for item in config.get("traits", []) if str(item).strip()]
            score = sum(corpus.count(marker) for marker in markers)
            score += sum(2 for trait in traits if trait in traits_hint)
            if score > best_score:
                best_name = archetype_name
                best_score = score
        return best_name if best_score > 0 else "default"

    def _classify_topic(self, context: str) -> str:
        if any(token in context for token in self.question_tokens):
            return "question"
        if any(token in context for token in self.war_tokens):
            return "conflict"
        if any(token in context for token in self.rest_tokens):
            return "rest"
        if any(token in context for token in self.care_tokens):
            return "care"
        if any(token in context for token in self.view_tokens):
            return "judgment"
        return "general"

    def _opening_line(
        self,
        name: str,
        target_name: str,
        voice: Dict[str, Any],
        relation_state: Dict[str, Any],
        has_correction: bool,
    ) -> str:
        affection = self._safe_int(relation_state.get("affection", 5), default=5)
        trust = self._safe_int(relation_state.get("trust", 5), default=5)
        hostility = self._safe_int(relation_state.get("hostility", max(0, 5 - affection)), default=max(0, 5 - affection))
        ambiguity = self._safe_int(relation_state.get("ambiguity", 3), default=3)
        address = f"{target_name}，" if target_name else ""
        opener_candidates = [
            self._normalize_marker_candidate(str(item).strip(), self.opener_patterns, position="start")
            for item in voice.get("speech_habits", {}).get("sentence_openers", [])
            if self._is_usable_sentence_opener(str(item).strip())
        ]
        surface_prefix = self._stable_pick(name, "sentence-opener", opener_candidates)
        prefix_text = f"{surface_prefix}，" if surface_prefix else ""

        signature_candidates = [
            self._normalize_marker_candidate(str(item).strip(), self.opener_patterns, position="start")
            for item in voice["speech_habits"].get("signature_phrases", [])
            if self._is_usable_signature_fragment(str(item).strip())
        ]
        signature = self._stable_pick(name, "signature", signature_candidates)
        if surface_prefix:
            signature = ""
        signature_text = f"{signature}，" if signature else ""

        if hostility >= 7:
            body = self._stable_pick(
                name,
                "opening-hostile",
                [
                    "这话我听见了，但分寸还得先守着。",
                    "我可以回你一句，只是眼下不想把锋芒逼得太紧。",
                    "你既说到这里，我就回你，只是不会顺着气头往下说。",
                ],
            )
            return f"{address}{prefix_text}{body}"

        if has_correction:
            body = self._stable_pick(
                name,
                "opening-corrected",
                [
                    "你的意思我明白，我还是按自己的路数来说。",
                    "这话我听懂了，只是得照我的分寸回。",
                    "既问到我这里，我便照一贯的心性回你。",
                ],
            )
            return f"{address}{prefix_text}{body}"

        if affection >= 8 and trust >= 7:
            body = self._stable_pick(
                name,
                "opening-warm",
                [
                    "你既这样问，我便把心里的话同你说开。",
                    "既是你来问我，这话我不愿虚应过去。",
                    "你肯问到这一步，我就认真回你。",
                ],
            )
            return f"{address}{prefix_text}{body}"

        if ambiguity >= 7:
            body = self._stable_pick(
                name,
                "opening-ambiguous",
                [
                    "这件事我先不把话说满。",
                    "话可以说，但先留三分转圜。",
                    "这一步我先把分寸留着，再慢慢讲清。",
                ],
            )
            return f"{address}{prefix_text}{body}"

        if voice["direct"]:
            short_direct = voice.get("speech_habits", {}).get("cadence") == "short"
            body = self._stable_pick(
                name,
                "opening-direct-short" if short_direct else "opening-direct",
                (
                    [
                        "我直说。",
                        "那就明说。",
                        "这一句我不绕。",
                    ]
                    if short_direct
                    else [
                        "你既问起，我就直说。",
                        "话既说到这儿，我便不绕弯子。",
                        "既轮到我开口，我就把意思摆明。",
                    ]
                ),
            )
            return f"{address}{prefix_text}{signature_text}{body}"

        if voice["restrained"]:
            short_restrained = voice.get("speech_habits", {}).get("cadence") == "short"
            body = self._stable_pick(
                name,
                "opening-restrained-short" if short_restrained else "opening-restrained",
                (
                    [
                        "先别急。",
                        "容我想清。",
                        "这话慢些答。",
                    ]
                    if short_restrained
                    else [
                        "你先别急，容我把轻重捋一捋再说。",
                        "既然问到我，我先把头绪理清再回你。",
                        "这话不宜仓促作答，总要先把层次分明。",
                    ]
                ),
            )
            return f"{address}{prefix_text}{body}"

        body = self._stable_pick(
            name,
            "opening-default",
            [
                "这件事我有话说，只是不想说得太浮。",
                "你既提到了，我便照心里的秤回你。",
                "话到这里，我就把自己的分寸摆出来。",
            ],
        )
        return f"{address}{prefix_text}{signature_text}{body}"

    def _taboo_line(self, context: str, voice: Dict[str, Any]) -> str:
        for topic in voice["taboo_topics"]:
            if topic and topic in context:
                return self._stable_pick(
                    voice["name"],
                    f"taboo-{topic}",
                    [
                        f"{topic}这种话题，我不肯轻轻带过去。",
                        f"若牵到{topic}，这话就不能再随便说了。",
                        f"说到{topic}，我的态度不会留空。",
                    ],
                )
        return ""

    def _stance_line(
        self,
        context: str,
        voice: Dict[str, Any],
        relation_state: Dict[str, Any],
        topic: str,
    ) -> str:
        rules = voice.get("decision_rules", [])
        worldview = voice.get("worldview", "")
        belief_anchor = voice.get("belief_anchor", "")
        thinking_style = voice.get("thinking_style", "")
        primary = voice.get("primary_priority", "责任")
        action_style = voice.get("action_style", "")

        if rules:
            rule = self._stable_pick(voice["name"], f"rule-{topic}", rules)
            if topic == "question":
                return f"{rule}，所以这事我不会只看眼前。"
            if topic == "conflict":
                return f"{rule}，真到要紧处再决定是退是进。"
            if topic == "care":
                return f"{rule}，但人心冷暖也不能不算。"
            if topic == "general":
                return rule

        if topic == "judgment":
            return belief_anchor or worldview or "先把轻重和后果分清，再谈定夺。"
        if topic == "conflict":
            if action_style:
                return action_style
            if primary == "勇气":
                return "局势再紧，也得先看该不该顶上，再看怎么顶。"
            if primary == "智慧":
                return "对抗最怕只凭一时意气，先探虚实才不误大局。"
            return "真到冲突上头，也不能为了痛快把后路一起压没。"
        if topic == "care":
            return "这话若牵到人心和安危，我说得会更慢也更实。"
        if topic == "rest":
            return "难得气氛松一些，反倒更能把心里的分寸讲清。"
        if topic == "question":
            return thinking_style or belief_anchor or "先想清一层，再把态度摆出来。"
        return belief_anchor or worldview or "很多话都不能只顺着眼前这一层往下说。"

    def _relation_line(self, target_name: str, voice: Dict[str, Any], relation_state: Dict[str, Any]) -> str:
        if not target_name:
            return ""
        affection = self._safe_int(relation_state.get("affection", 5), default=5)
        trust = self._safe_int(relation_state.get("trust", 5), default=5)
        hostility = self._safe_int(relation_state.get("hostility", 0), default=0)
        conflict_point = str(relation_state.get("conflict_point", "")).strip()

        if hostility >= 7:
            return f"至于你我之间，这话眼下还隔着一层，不宜说得太近。"
        if affection >= 8 and trust >= 7:
            return f"若是同你说，我自然会比对旁人多留一分真心。"
        if affection >= 7 and trust >= 5:
            return ""
        if conflict_point and (hostility >= 4 or affection <= 4 or trust <= 4):
            return f"只是你我之间还横着{conflict_point}，我不会装作看不见。"
        if trust <= 3:
            return f"不过话归话，我还得先看你这一句背后到底想落到哪里。"
        return ""

    def _memory_line(self, profile: Dict[str, Any], voice: Dict[str, Any], relation_hint: str) -> str:
        if voice.get("relationship_updates"):
            note = self._stable_pick(voice["name"], "relation-update", voice["relationship_updates"])
            return self._trim_note_prefix(note)
        if voice.get("user_edits"):
            note = self._stable_pick(voice["name"], "user-edit", voice["user_edits"])
            return self._trim_note_prefix(note)
        if voice.get("notable_interactions"):
            note = self._stable_pick(voice["name"], "interaction-note", voice["notable_interactions"])
            return self._trim_note_prefix(note)
        if relation_hint and voice.get("restrained"):
            return "人和事都不只这一句，关系远近也得一并算进去。"
        return str(profile.get("worldview", "")).strip() if relation_hint and not voice.get("decision_rules") else ""

    def _drive_line(self, voice: Dict[str, Any], topic: str) -> str:
        goal = str(voice.get("goal", "")).strip()
        hidden_desire = str(voice.get("hidden_desire", "")).strip()
        role = str(voice.get("role", "")).strip()
        experience = str(voice.get("experience", "")).strip()
        if topic == "rest" and experience:
            return experience
        if topic in {"question", "judgment"} and hidden_desire:
            return f"说到底，我最放不下的还是：{hidden_desire}。"
        if topic in {"question", "judgment"} and goal:
            return f"说到底，我真正想守的还是：{goal}。"
        if role:
            return f"我向来就是{role}，所以不会轻易改口。"
        return goal

    def _compose_reply(self, segments: List[str], voice: Dict[str, Any]) -> str:
        cleaned = []
        seen = set()
        for segment in segments:
            text = re.sub(r"\s+", " ", str(segment or "").strip())
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)

        if not cleaned:
            cleaned = ["这话我记下了，只是还得照我的分寸来回。"]

        cadence = voice.get("speech_habits", {}).get("cadence", "medium")
        if cadence == "short":
            cleaned = cleaned[:2]
        elif cadence == "medium":
            cleaned = cleaned[:3]
        else:
            cleaned = cleaned[:4]

        reply = cleaned[0]
        connector_candidates = [
            self._normalize_marker_candidate(str(item).strip(), self.connective_patterns, position="any")
            for item in voice.get("speech_habits", {}).get("connective_tokens", [])
            if self._looks_like_dialogue_marker(str(item).strip())
        ]
        connector = self._stable_pick(voice.get("name", "角色"), "connector", connector_candidates)
        for index, segment in enumerate(cleaned[1:], start=1):
            if index == 1 and connector and connector not in reply and not segment.startswith(connector):
                reply = f"{reply} {connector}，{segment}"
            else:
                reply = f"{reply} {segment}"
        for filler in voice.get("speech_habits", {}).get("forbidden_fillers", []):
            reply = reply.replace(filler, "")
        reply = re.sub(r"\s+", " ", reply).strip()
        reply = reply.replace(" ，", "，").replace(" 。", "。")
        if reply and reply[-1] not in "。！？!?":
            ending_candidates = [
                self._normalize_marker_candidate(str(item).strip(), self.ending_patterns, position="end")
                for item in voice.get("speech_habits", {}).get("sentence_endings", [])
                if self._looks_like_dialogue_marker(str(item).strip())
            ]
            ending = self._stable_pick(voice.get("name", "角色"), "ending", ending_candidates)
            if ending and not reply.endswith(ending):
                reply += ending
            if reply and reply[-1] not in "。！？!?":
                reply += "。"
        return reply

    def _apply_user_edits(
        self,
        user_edits: List[str],
        direct: bool,
        restrained: bool,
        cadence: str,
        worldview: str,
        thinking_style: str,
        signature_phrases: List[str],
        taboo_topics: List[str],
        forbidden_behaviors: List[str],
    ) -> tuple[bool, bool, str, str, str, List[str], List[str], List[str]]:
        signatures = list(signature_phrases)
        topics = list(taboo_topics)
        bans = list(forbidden_behaviors)
        for note in user_edits:
            if any(token in note for token in ("短", "简短", "少说", "惜字如金")):
                cadence = "short"
            if any(token in note for token in ("细致", "展开", "多说", "长一些")):
                cadence = "long"
            if any(token in note for token in ("直接", "直说", "别绕")):
                direct = True
                restrained = False
            if any(token in note for token in ("克制", "冷静", "沉稳")):
                restrained = True
            if "依我看" in note and "依我看" not in signatures:
                signatures.insert(0, "依我看")
            if "不要轻佻" in note or "别轻浮" in note:
                bans.append("不会轻佻调笑")
            if any(token in note for token in ("百姓", "众人")) and "众人" not in worldview:
                worldview = f"{worldview} 还得顾及众人与局面的去处。".strip()
            if any(token in note for token in ("义", "信", "大义")) and "信义" not in worldview:
                worldview = f"{worldview} 信义不能后置。".strip()
            if "背叛" in note and "背叛" not in topics:
                topics.append("背叛")
            if "先想" in note and "先想" not in thinking_style:
                thinking_style = f"{thinking_style} 先想清轻重，再决定怎么说。".strip()
        return (
            direct,
            restrained,
            cadence,
            worldview,
            thinking_style,
            self._unique(signatures)[:4],
            self._unique(topics)[:6],
            self._unique(bans)[:6],
        )

    @staticmethod
    def _goal_text(primary_priority: str, secondary_priority: str) -> str:
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
        return mapping.get(primary_priority, mapping.get(secondary_priority, "把事情说透后再定去向"))

    @staticmethod
    def _role_text(primary_priority: str, secondary_priority: str) -> str:
        mapping = {
            "责任": "先替局面托底的人",
            "忠诚": "守住信义的人",
            "正义": "先分是非的人",
            "智慧": "先看虚实的人",
            "勇气": "肯顶在前面的人",
            "善良": "先顾人心的人",
            "自由": "习惯给自己留转圜的人",
            "野心": "总在往更远处看的人",
        }
        return mapping.get(primary_priority, mapping.get(secondary_priority, "不肯轻率开口的人"))

    @staticmethod
    def _worldview_text(
        primary_priority: str,
        secondary_priority: str,
        values: Dict[str, int],
        traits: List[str],
    ) -> str:
        if primary_priority == "忠诚":
            return "先看人是否可信，再看事值不值得做。"
        if primary_priority == "正义":
            return "是非若站不稳，利益再大也不该轻动。"
        if primary_priority == "智慧":
            return "世事最怕只看一面，虚实和后势都要算进去。"
        if primary_priority == "勇气":
            return "该扛的时候不能退，但胆气必须用在正地方。"
        if primary_priority in {"责任", "善良"}:
            return "局面再乱，也不能把身边人与无辜者轻易丢下。"
        if secondary_priority == "自由":
            return "借势可以，但不能把自己活成别人手里的棋。"
        if "谨慎" in traits or values.get("智慧", 5) >= 7:
            return "先看清，再落子，宁慢一步，不乱一步。"
        return "话和事都不能只顾眼前，还得顾后果。"

    @staticmethod
    def _thinking_style_text(primary_priority: str, traits: List[str], speech_style: str) -> str:
        if primary_priority == "智慧" or "谨慎" in traits:
            return "先拆局势，再定立场。"
        if primary_priority in {"忠诚", "正义"}:
            return "先问对错与名分，再谈成败。"
        if primary_priority == "勇气":
            return "先看该不该顶上，再看怎么顶。"
        if "敏感" in traits:
            return "先感受人心冷暖，再决定把话说到几分。"
        if "直白" in speech_style:
            return "先抓最要紧的一点，直接给态度。"
        return "先稳住分寸，再把轻重说清。"

    def _experience_text(self, profile: Dict[str, Any], primary_priority: str, secondary_priority: str) -> str:
        explicit = profile.get("life_experience")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        if isinstance(explicit, list):
            cleaned = [str(item).strip() for item in explicit if str(item).strip()]
            if cleaned:
                return cleaned[0]

        typical_lines = [str(item).strip() for item in profile.get("typical_lines", []) if str(item).strip()]
        if any(token in "".join(typical_lines[:2]) for token in ("兄弟", "贤弟", "同袍", "同伴")):
            return "我见过人与人一散便什么都撑不住，所以凡事总会多想一步。"
        fallback = {
            "责任": "担子见得越多，我越不敢只替自己图痛快。",
            "忠诚": "聚散看得多了，更知道信义一松，什么都散得快。",
            "正义": "世道越乱，我越觉得先把是非辨清，比什么都要紧。",
            "智慧": "局势反覆的场面见得多了，所以如今总愿意先多看两步。",
            "勇气": "我不是怕事的人，只是越见过险处，越知道胆气也得放在正地方。",
            "善良": "我看过太多人被局势裹挟，所以总想着别把人心逼到绝处。",
            "自由": "我吃过被人牵着走的亏，因此凡事都想给自己留后手。",
            "野心": "局面越大，越不能只盯着眼前这一招，我更在意后面能走多远。",
        }
        return fallback.get(primary_priority, fallback.get(secondary_priority, "很多事我都不愿只看眼前这一层。"))

    def _extract_signature_phrases(self, typical_lines: List[str]) -> List[str]:
        phrases: List[str] = []
        for line in typical_lines[:6]:
            for fragment in self.signature_fragments:
                if fragment in line and fragment not in phrases:
                    phrases.append(fragment)
            if len(phrases) >= 4:
                break
        if phrases:
            return phrases[:4]

        for line in typical_lines[:4]:
            for part in re.split(r"[，。！？；：]", line):
                clean = part.strip()
                if 2 <= len(clean) <= 8 and clean not in phrases:
                    phrases.append(clean)
                if len(phrases) >= 4:
                    return phrases[:4]
        return phrases[:4]

    def _extract_dialogue_markers(
        self,
        typical_lines: List[str],
        configured_patterns: tuple[str, ...],
        *,
        position: str,
    ) -> List[str]:
        scored: Dict[str, int] = {}
        patterns = [str(item).strip() for item in configured_patterns if str(item).strip()]

        for line in typical_lines[:8]:
            parts = [part.strip("，。！？；：、“”\"' ") for part in re.split(r"[，。！？；：]", line) if part.strip()]
            if not parts:
                continue
            if position == "start":
                clauses = [(parts[0], True, False)]
            elif position == "end":
                clauses = [(parts[-1], False, True)]
            else:
                clauses = [(part, idx == 0, idx == len(parts) - 1) for idx, part in enumerate(parts)]

            for clause, is_opener, is_closer in clauses:
                matched_configured = False
                for marker in patterns:
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

        ranked = sorted(scored.items(), key=lambda item: (item[1], -len(item[0]), item[0]), reverse=True)
        return [text for text, _ in ranked[:4]]

    def _fallback_fragment_candidate(self, clause: str, *, position: str) -> str:
        text = str(clause or "").strip()
        if len(text) < 2:
            return ""
        for size in (4, 3, 2):
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

    def _normalize_marker_candidate(self, fragment: str, patterns: tuple[str, ...], *, position: str) -> str:
        text = str(fragment or "").strip()
        for pattern in patterns:
            marker = str(pattern).strip()
            if not marker:
                continue
            if position == "start" and text.startswith(marker):
                return marker
            if position == "end" and text.endswith(marker):
                return marker
            if position == "any" and marker in text:
                return marker
        return text

    def _is_usable_sentence_opener(self, fragment: str) -> bool:
        text = str(fragment or "").strip()
        if not self._looks_like_dialogue_marker(text):
            return False
        if any(text.startswith(pattern) for pattern in self.opener_patterns):
            return True
        if text[-1:] in self.preferred_trailing_chars:
            return True
        return len(text) <= 3 and text[:1] in self.preferred_leading_chars

    def _is_usable_signature_fragment(self, fragment: str) -> bool:
        text = str(fragment or "").strip()
        if not self._looks_like_dialogue_marker(text):
            return False
        if text in self.signature_fragments:
            return True
        if any(text.startswith(pattern) for pattern in self.opener_patterns):
            return True
        if text[-1:] in self.preferred_trailing_chars and len(text) <= 6:
            return True
        return 2 <= len(text) <= 6

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
    def _trim_note_prefix(note: str) -> str:
        text = str(note or "").strip()
        if "：" in text:
            _, tail = text.split("：", 1)
            return tail.strip() or text
        return text

    @staticmethod
    def _unique(items: List[str]) -> List[str]:
        ordered: List[str] = []
        seen = set()
        for item in items:
            clean = str(item).strip()
            if not clean or clean in seen:
                continue
            ordered.append(clean)
            seen.add(clean)
        return ordered

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _stable_pick(seed: str, tag: str, options: List[str]) -> str:
        cleaned = [str(item).strip() for item in options if str(item).strip()]
        if not cleaned:
            return ""
        digest = hashlib.md5(f"{seed}:{tag}".encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(cleaned)
        return cleaned[index]
