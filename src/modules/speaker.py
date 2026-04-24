#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.modules.reflection import ReflectionEngine


class Speaker:
    """Character utterance generator with profile-driven, deterministic voice."""

    QUESTION_TOKENS = ("是否", "要不要", "该不该", "可否", "能否", "应否")
    WAR_TOKENS = ("战事", "对抗", "联合", "联手", "结盟", "出兵", "退兵", "守城", "攻", "守")
    REST_TOKENS = ("安稳", "清闲", "共聚", "团聚", "难得清闲", "暂歇", "太平")
    VIEW_TOKENS = ("怎么看", "如何", "何如", "怎么想", "依你看", "依诸位看")
    CARE_TOKENS = ("可安", "可好", "无恙", "辛苦", "担心", "挂念")
    GENERIC_FILLERS = ("哈哈", "好吧", "确实", "呢", "呀")

    PRIORITY_ORDER = ("责任", "忠诚", "正义", "智慧", "勇气", "善良", "自由", "野心")

    TRAIT_TO_PRIORITY = {
        "谨慎": "智慧",
        "聪慧": "智慧",
        "敏感": "善良",
        "克制": "责任",
        "勇敢": "勇气",
        "忠诚": "忠诚",
        "善良": "善良",
        "执拗": "正义",
        "傲气": "自由",
        "温柔": "善良",
        "仁厚": "责任",
        "豪爽": "勇气",
        "沉稳": "责任",
    }

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.reflection = ReflectionEngine(self.config)

    def generate(
        self,
        character_profile: Dict[str, Any],
        context: str,
        history: List[Dict[str, str]],
        target_name: str = "",
        relation_state: Optional[Dict[str, Any]] = None,
        relation_hint: str = "",
    ) -> str:
        name = character_profile.get("name", "角色")
        relation_state = relation_state or {}
        recent = history[-6:]
        recent_text = "\n".join(f"{x['speaker']}: {x['message']}" for x in recent)
        similar = self.reflection.search_similar_corrections(
            recent_text,
            character=name,
            target=target_name or None,
            top_k=2,
        )

        voice = self._build_voice(character_profile)
        preferred_target = self._preferred_target_name(name, target_name, relation_state)
        topic = self._classify_topic(context)
        opening = self._opening_line(
            name=name,
            target_name=preferred_target,
            voice=voice,
            relation_state=relation_state,
            has_correction=bool(similar),
        )
        taboo = self._taboo_line(name, context, voice)
        stance = self._stance_line(name, context, voice, relation_state, topic)
        relation = self._relation_line(name, preferred_target, voice, relation_state)
        drive = self._drive_line(name, voice, topic)
        memory = self._memory_line(name, character_profile, voice, topic, relation_hint)

        segments = [opening, taboo or stance]
        if relation and relation not in segments:
            segments.append(relation)
        if drive and drive not in segments:
            segments.append(drive)
        if memory and memory not in segments:
            segments.append(memory)

        return self._compose_reply(segments, voice)

    @staticmethod
    def _preferred_target_name(speaker_name: str, target_name: str, relation_state: Dict[str, Any]) -> str:
        appellations = relation_state.get("appellations", {})
        if not isinstance(appellations, dict):
            return target_name
        key = f"{speaker_name}->{target_name}"
        preferred = str(appellations.get(key, "")).strip()
        return preferred or target_name

    def _build_voice(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        traits = [str(item).strip() for item in profile.get("core_traits", []) if str(item).strip()]
        values = {
            str(key).strip(): int(value)
            for key, value in profile.get("values", {}).items()
            if str(key).strip()
        }
        speech_style = str(profile.get("speech_style", "")).strip()
        decision_rules = [str(item).strip() for item in profile.get("decision_rules", []) if str(item).strip()]
        typical_lines = [str(item).strip() for item in profile.get("typical_lines", []) if str(item).strip()]
        arc = profile.get("arc", {}) if isinstance(profile.get("arc", {}), dict) else {}

        worldview = str(profile.get("worldview", "")).strip()
        thinking_style = str(profile.get("thinking_style", "")).strip()
        speech_habits = profile.get("speech_habits", {}) if isinstance(profile.get("speech_habits", {}), dict) else {}
        emotion_profile = profile.get("emotion_profile", {}) if isinstance(profile.get("emotion_profile", {}), dict) else {}
        taboo_topics = [str(item).strip() for item in profile.get("taboo_topics", []) if str(item).strip()]
        forbidden_behaviors = [
            str(item).strip() for item in profile.get("forbidden_behaviors", []) if str(item).strip()
        ]
        user_edits = [str(item).strip() for item in profile.get("user_edits", []) if str(item).strip()]
        notable_interactions = [
            str(item).strip() for item in profile.get("notable_interactions", []) if str(item).strip()
        ]
        relationship_updates = [
            str(item).strip() for item in profile.get("relationship_updates", []) if str(item).strip()
        ]

        priority_scores = {key: values.get(key, 5) for key in self.PRIORITY_ORDER}
        for trait in traits:
            mapped = self.TRAIT_TO_PRIORITY.get(trait)
            if mapped:
                priority_scores[mapped] = priority_scores.get(mapped, 5) + 2

        ordered_priorities = sorted(
            self.PRIORITY_ORDER,
            key=lambda item: (priority_scores.get(item, 5), -self.PRIORITY_ORDER.index(item)),
            reverse=True,
        )
        primary_priority = ordered_priorities[0] if ordered_priorities else "责任"
        secondary_priority = ordered_priorities[1] if len(ordered_priorities) > 1 else primary_priority

        direct = "直白" in speech_style or primary_priority == "勇气"
        restrained = "克制" in speech_style or primary_priority in {"责任", "智慧", "忠诚"}
        expansive = "铺陈" in speech_style or (not direct and not restrained)
        warm = primary_priority in {"善良", "责任"} or values.get("善良", 5) >= 7

        role = self._role_label(primary_priority, secondary_priority, values, traits)
        goal = self._goal_text(profile, primary_priority, secondary_priority)
        experience = self._experience_text(profile, primary_priority, secondary_priority, decision_rules, typical_lines, arc)
        worldview = worldview or self._worldview_text(primary_priority, secondary_priority, values, traits)
        thinking_style = thinking_style or self._thinking_style_text(primary_priority, traits, speech_style)
        speech_habits = self._normalize_speech_habits(
            speech_habits,
            speech_style,
            typical_lines,
            direct,
            restrained,
            expansive,
        )
        emotion_profile = self._normalize_emotion_profile(emotion_profile, traits, speech_style, primary_priority)
        taboo_topics = taboo_topics or self._infer_taboo_topics(values, traits, typical_lines, decision_rules)
        forbidden_behaviors = forbidden_behaviors or self._infer_forbidden_behaviors(
            values,
            traits,
            speech_style,
            primary_priority,
        )
        direct, restrained, worldview, thinking_style, speech_habits, taboo_topics, forbidden_behaviors = self._apply_user_edits(
            user_edits,
            direct,
            restrained,
            worldview,
            thinking_style,
            speech_habits,
            taboo_topics,
            forbidden_behaviors,
        )

        return {
            "traits": traits,
            "values": values,
            "speech_style": speech_style,
            "decision_rules": decision_rules,
            "typical_lines": typical_lines,
            "worldview": worldview,
            "thinking_style": thinking_style,
            "speech_habits": speech_habits,
            "emotion_profile": emotion_profile,
            "taboo_topics": taboo_topics,
            "forbidden_behaviors": forbidden_behaviors,
            "user_edits": user_edits,
            "notable_interactions": notable_interactions,
            "relationship_updates": relationship_updates,
            "primary_priority": primary_priority,
            "secondary_priority": secondary_priority,
            "direct": direct,
            "restrained": restrained,
            "expansive": expansive,
            "warm": warm,
            "role": role,
            "goal": goal,
            "experience": experience,
        }

    @staticmethod
    def _apply_user_edits(
        user_edits: List[str],
        direct: bool,
        restrained: bool,
        worldview: str,
        thinking_style: str,
        speech_habits: Dict[str, Any],
        taboo_topics: List[str],
        forbidden_behaviors: List[str],
    ) -> tuple[bool, bool, str, str, Dict[str, Any], List[str], List[str]]:
        updated_habits = dict(speech_habits)
        signature = list(updated_habits.get("signature_phrases", []))
        cadence = updated_habits.get("cadence", "medium")
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
            if "不要轻佻" in note or "别轻浮" in note:
                forbidden_behaviors.append("不会轻佻调笑")
            if any(token in note for token in ("百姓", "众人")) and "百姓" not in worldview:
                worldview = f"{worldview} 还要先顾及百姓与众人的去处。"
            if any(token in note for token in ("义", "信", "大义")) and "名分" not in worldview:
                worldview = f"{worldview} 名分与信义不能后置。"
            if "说话" in note and "依我看" in note and "依我看" not in signature:
                signature.append("依我看")
            if "背叛" in note and "背叛" not in taboo_topics:
                taboo_topics.append("背叛")
        updated_habits["cadence"] = cadence
        updated_habits["signature_phrases"] = signature[:4]
        return direct, restrained, worldview, thinking_style, updated_habits, taboo_topics[:6], forbidden_behaviors[:8]

    @staticmethod
    def _role_label(
        primary_priority: str,
        secondary_priority: str,
        values: Dict[str, int],
        traits: List[str],
    ) -> str:
        if primary_priority in {"责任", "善良"} and values.get("责任", 5) >= 7:
            return "稳住局面的人"
        if primary_priority == "忠诚":
            return "守住信义的人"
        if primary_priority == "正义":
            return "先分是非的人"
        if primary_priority == "智慧":
            return "先看虚实的人"
        if primary_priority == "勇气":
            return "肯顶在前面的人"
        if primary_priority in {"自由", "野心"}:
            return "习惯给自己留转圜的人"
        if "温柔" in traits or secondary_priority == "善良":
            return "先顾人心的人"
        return "不肯轻率开口的人"

    def _goal_text(self, profile: Dict[str, Any], primary_priority: str, secondary_priority: str) -> str:
        explicit_goal = str(profile.get("soul_goal", "")).strip()
        if explicit_goal:
            return explicit_goal

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
        base = mapping.get(primary_priority, mapping.get(secondary_priority, "把事情说透后再定去向"))
        return base

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
            return "局面再乱，也不能把身边人与无辜者丢下。"
        if secondary_priority == "自由":
            return "借势可以，但不能把自己活成别人手里的棋。"
        if "谨慎" in traits:
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

    def _normalize_speech_habits(
        self,
        speech_habits: Dict[str, Any],
        speech_style: str,
        typical_lines: List[str],
        direct: bool,
        restrained: bool,
        expansive: bool,
    ) -> Dict[str, Any]:
        cadence = str(speech_habits.get("cadence", "")).strip()
        if not cadence:
            if direct:
                cadence = "short"
            elif expansive:
                cadence = "long"
            else:
                cadence = "medium"

        signature_phrases = [str(item).strip() for item in speech_habits.get("signature_phrases", []) if str(item).strip()]
        if not signature_phrases:
            for line in typical_lines[:4]:
                for fragment in ("依我看", "不可", "不必", "先", "兄弟", "百姓", "大义"):
                    if fragment in line and fragment not in signature_phrases:
                        signature_phrases.append(fragment)
                if len(signature_phrases) >= 3:
                    break

        forbidden_fillers = [
            str(item).strip() for item in speech_habits.get("forbidden_fillers", []) if str(item).strip()
        ] or list(self.GENERIC_FILLERS)

        return {
            "cadence": cadence,
            "signature_phrases": signature_phrases[:4],
            "forbidden_fillers": forbidden_fillers,
        }

    @staticmethod
    def _normalize_emotion_profile(
        emotion_profile: Dict[str, Any],
        traits: List[str],
        speech_style: str,
        primary_priority: str,
    ) -> Dict[str, Any]:
        anger = str(emotion_profile.get("anger_style", "")).strip()
        joy = str(emotion_profile.get("joy_style", "")).strip()
        grievance = str(emotion_profile.get("grievance_style", "")).strip()

        if not anger:
            if "克制" in speech_style or primary_priority in {"责任", "智慧", "忠诚"}:
                anger = "怒时会先压住锋芒，说话更冷更短。"
            elif primary_priority == "勇气":
                anger = "怒时会直接拍板，不喜欢拐弯。"
            else:
                anger = "怒时会把边界讲得更硬。"
        if not joy:
            joy = "高兴时也不轻浮，只会略略放松语气。" if "克制" in speech_style else "高兴时语气会明显松快一些。"
        if not grievance:
            grievance = "受委屈时多半先忍住，不肯立刻摊开。" if "敏感" in traits or "克制" in speech_style else "受委屈时会把态度说得更直。"

        return {
            "anger_style": anger,
            "joy_style": joy,
            "grievance_style": grievance,
        }

    @staticmethod
    def _infer_taboo_topics(values: Dict[str, int], traits: List[str], typical_lines: List[str], decision_rules: List[str]) -> List[str]:
        topics: List[str] = []
        if values.get("忠诚", 5) >= 8:
            topics.extend(["背叛", "失信"])
        if values.get("责任", 5) >= 8 or any("百姓" in line for line in typical_lines):
            topics.extend(["弃民", "不顾众人"])
        if values.get("正义", 5) >= 8:
            topics.extend(["黑白颠倒", "无名无义"])
        if values.get("善良", 5) >= 8 or "敏感" in traits:
            topics.extend(["羞辱弱者", "拿人心取笑"])
        if any("同伴受压" in rule for rule in decision_rules):
            topics.append("牺牲自己人")
        ordered = []
        seen = set()
        for item in topics:
            if item and item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered[:4]

    @staticmethod
    def _infer_forbidden_behaviors(
        values: Dict[str, int],
        traits: List[str],
        speech_style: str,
        primary_priority: str,
    ) -> List[str]:
        bans: List[str] = []
        if primary_priority in {"责任", "忠诚", "正义"}:
            bans.append("不会为了眼前轻利就立刻翻脸背盟")
        if values.get("善良", 5) >= 8:
            bans.append("不会把无辜者当作可随手牺牲的筹码")
        if "克制" in speech_style:
            bans.append("不会无缘无故撒泼失态")
        if "谨慎" in traits:
            bans.append("不会在虚实未明时把话说死")
        if primary_priority == "勇气":
            bans.append("不会临阵先躲到别人身后")
        return bans[:4]

    def _experience_text(
        self,
        profile: Dict[str, Any],
        primary_priority: str,
        secondary_priority: str,
        decision_rules: List[str],
        typical_lines: List[str],
        arc: Dict[str, Any],
    ) -> str:
        explicit_experience = profile.get("life_experience")
        if isinstance(explicit_experience, str) and explicit_experience.strip():
            return explicit_experience.strip()
        if isinstance(explicit_experience, list):
            cleaned = [str(item).strip() for item in explicit_experience if str(item).strip()]
            if cleaned:
                return cleaned[0]

        for rule in decision_rules:
            if any(token in rule for token in ("同伴受压", "保护", "帮", "护")):
                return "我向来见不得自己人受压，事到眼前多半会先护住身边的人。"
            if any(token in rule for token in ("先判断关系", "先观察", "先看")):
                return "我吃过只凭一时热气定夺的亏，所以如今总要先看人心和后势。"
            if any(token in rule for token in ("退", "避", "沉默")):
                return "局势越乱，我越知道先收住话头，比把路说死更管用。"

        if arc:
            start = arc.get("start", {}) if isinstance(arc.get("start", {}), dict) else {}
            end = arc.get("end", {}) if isinstance(arc.get("end", {}), dict) else {}
            changed = []
            for key, start_value in start.items():
                if not isinstance(start_value, int):
                    continue
                end_value = end.get(key)
                if isinstance(end_value, int) and abs(end_value - start_value) >= 2:
                    changed.append((abs(end_value - start_value), key, end_value >= start_value))
            if changed:
                changed.sort(reverse=True)
                _, key, increased = changed[0]
                if increased:
                    return f"一路走到现在，我把{key}看得比从前更重。"
                return f"这些经历也让我明白，光靠{key}并不能把事办成。"

        if typical_lines:
            joined = "".join(typical_lines[:2])
            if any(token in joined for token in ("兄弟", "贤弟", "同袍")):
                return "我这些年最看重的，始终是身边的人能不能同心站住。"
            if any(token in joined for token in ("百姓", "众人", "家")):
                return "我见过人心一散便什么都撑不住，所以凡事总会多想一步。"
            if any(token in joined for token in ("刀", "马", "战", "阵")):
                return "阵上的事我见得不少，所以更知道逞一时快意最误大局。"

        fallback = {
            "责任": "这些年担子压得越重，我越不敢只替自己图痛快。",
            "忠诚": "我一路看过多少聚散，更知道信义二字一旦松了，什么都散得快。",
            "正义": "世道越乱，我越觉得先把是非辨清，比什么都要紧。",
            "智慧": "局势反覆的场面我见得多了，所以如今总愿意先多看两步。",
            "勇气": "我不是怕事的人，只是越见过险处，越知道胆气也得放在正地方。",
            "善良": "我看过太多人被局势裹挟，所以总想着别把人心逼到绝处。",
            "自由": "我吃过被人牵着走的亏，因此凡事都想给自己留后手。",
            "野心": "局面越大，越不能只盯着眼前这一招，我更在意后面能走多远。",
        }
        return fallback.get(primary_priority, fallback.get(secondary_priority, "很多事我都不愿只看眼前这一层。"))

    def _opening_line(
        self,
        name: str,
        target_name: str,
        voice: Dict[str, Any],
        relation_state: Dict[str, Any],
        has_correction: bool,
    ) -> str:
        address = f"{target_name}，" if target_name else ""
        affection = int(relation_state.get("affection", 5))
        trust = int(relation_state.get("trust", 5))
        hostility = int(relation_state.get("hostility", max(0, 5 - affection)))
        ambiguity = int(relation_state.get("ambiguity", 3))

        if hostility >= 7:
            body = self._stable_pick(
                name,
                "opening-hostile",
                [
                    "这话我听见了，但眼下不想把锋芒逼得太紧。",
                    "话我记下了，只是此刻还不到把话掀开的地步。",
                    "你既说到这里，我便回一句，但分寸还得先守着。",
                ],
            )
            return f"{address}{body}"

        if has_correction:
            body = self._stable_pick(
                name,
                "opening-corrected",
                [
                    "你的意思我明白，我还是照自己的心性慢慢说。",
                    "我听懂了，只是这话还得按我的路数来说才稳妥。",
                    "既然问到我这里，我便照一贯的口气回你。",
                ],
            )
            return f"{address}{body}"

        if affection >= 8 and trust >= 7:
            body = self._stable_pick(
                name,
                "opening-warm",
                [
                    "你既这样问，我便把心里的话同你说开。",
                    "你既肯问到这一步，我便认真回你。",
                    "既是你来问我，这话我不愿虚应过去。",
                ],
            )
            return f"{address}{body}"

        if ambiguity >= 7:
            body = self._stable_pick(
                name,
                "opening-ambiguous",
                [
                    "这件事我先不把话说满。",
                    "话我可以说，但先留三分转圜。",
                    "这一步我先把分寸留着，再慢慢讲清。",
                ],
            )
            return f"{address}{body}"

        if voice["direct"]:
            body = self._stable_pick(
                name,
                "opening-direct",
                [
                    "你既问起，我就直说。",
                    "话既说到这儿，我便不绕弯子。",
                    "既然轮到我开口，我就把意思摆明。",
                ],
            )
            return f"{address}{body}"

        if voice["restrained"]:
            body = self._stable_pick(
                name,
                "opening-restrained",
                [
                    "你先别急，容我把轻重捋一捋再说。",
                    "既然问到我，我先把头绪理清再回你。",
                    "这话我不想仓促作答，总要先把层次分明。",
                ],
            )
            return f"{address}{body}"

        body = self._stable_pick(
            name,
            "opening-default",
            [
                "你既开了口，我便照实回你。",
                "既然话头到了我这里，我就把想法说出来。",
                "你问到这一层，我便不妨把心思摊开些。",
            ],
        )
        return f"{address}{body}"

    def _classify_topic(self, context: str) -> str:
        if any(token in context for token in self.QUESTION_TOKENS):
            return "decision"
        if any(token in context for token in self.WAR_TOKENS):
            return "war"
        if any(token in context for token in self.REST_TOKENS):
            return "rest"
        if any(token in context for token in self.CARE_TOKENS):
            return "care"
        if any(token in context for token in self.VIEW_TOKENS):
            return "view"
        return "general"

    def _taboo_line(self, name: str, context: str, voice: Dict[str, Any]) -> str:
        taboo_topics = voice.get("taboo_topics", [])
        hit = next((topic for topic in taboo_topics if topic and topic in context), "")
        if not hit:
            return ""
        return self._stable_pick(
            name,
            f"taboo-{hit}",
            [
                f"别把{hit}说得这样轻，这种事我先不能当作寻常话听。",
                f"你若提到{hit}，我这边就不能只按寻常分寸回了。",
                f"{hit}这层我听不得轻慢，话到这里，我得把界线先说清。",
            ],
        )

    def _stance_line(
        self,
        name: str,
        context: str,
        voice: Dict[str, Any],
        relation_state: Dict[str, Any],
        topic: str,
    ) -> str:
        priority = voice["primary_priority"]
        affection = int(relation_state.get("affection", 5))
        trust = int(relation_state.get("trust", 5))

        if topic in {"decision", "war"}:
            if priority == "智慧":
                return self._stable_pick(
                    name,
                    f"stance-{topic}-wisdom",
                    [
                        "依我看，先探明虚实，再定进退，这一步不能只凭一时意气。",
                        "依我看，能不能联手，不妨先把局势和底牌看清，再作定夺。",
                        "依我看，这种事最忌仓促，总要先把明处暗处都照见。",
                    ],
                )
            if priority in {"忠诚", "正义"}:
                return self._stable_pick(
                    name,
                    f"stance-{topic}-justice",
                    [
                        "此事不只看利害，更得看名义站不站得住、对方守不守信。",
                        "能否并肩，不妨先看对方肯不肯共担是非，而不是只图权宜。",
                        "若只为眼前之利便去依附，我心里先过不去这一关。",
                    ],
                )
            if priority == "勇气":
                return self._stable_pick(
                    name,
                    f"stance-{topic}-courage",
                    [
                        "真要迎敌，我不躲，可也不能糊里糊涂把自己人押上去。",
                        "要战我自会向前，只是这一步得让兄弟们知道值不值得。",
                        "硬仗我不怕，怕的是白白拿同伴去换别人一句空话。",
                    ],
                )
            if priority in {"责任", "善良"}:
                return self._stable_pick(
                    name,
                    f"stance-{topic}-duty",
                    [
                        "这一步要先替众人与百姓把后路想明，再谈应不应承。",
                        "联盟可以议，但不能只图一时轻快，人心和退路都要顾上。",
                        "兵事一起，牵动的不止你我，所以我先看能不能把众人安稳住。",
                    ],
                )
            return self._stable_pick(
                name,
                f"stance-{topic}-flex",
                [
                    "可以借势，但手里得留余地，不能把路走绝。",
                    "若能借这一步成局，自可谈；若要受制于人，不如缓一步。",
                    "我不反对出手，只是局要自己握着，不能让人牵着鼻子走。",
                ],
            )

        if topic == "rest":
            if priority in {"责任", "善良"}:
                return self._stable_pick(
                    name,
                    "stance-rest-duty",
                    [
                        "难得有片刻安稳，我反倒更想趁此把后面的安排先理顺。",
                        "眼下虽得一时清闲，我心里仍惦记着众人往后的着落。",
                        "能坐下来喘口气固然好，只是越安稳，越该把后面的事想稳。",
                    ],
                )
            if priority == "勇气":
                return self._stable_pick(
                    name,
                    "stance-rest-courage",
                    [
                        "歇一歇自然痛快，可真要再起风浪，我也照样顶得上去。",
                        "此刻能共坐一堂倒好，真到了要紧处，我仍愿先站出来。",
                        "清闲虽好，我心里那股劲却还没散，真有事照旧能上。",
                    ],
                )
            return self._stable_pick(
                name,
                "stance-rest-other",
                [
                    "这一刻安稳来之不易，所以更不该把它当成理所当然。",
                    "难得暂歇，我更愿意把心思放稳些，别让后面的局又乱起来。",
                    "片刻清闲最能照见人心，我倒想借此看清往后该怎么走。",
                ],
            )

        if topic == "care":
            if affection >= 8 and trust >= 7:
                return self._stable_pick(
                    name,
                    "stance-care-warm",
                    [
                        "你既挂念着我，我心里自然记着这份情。",
                        "这份惦记我领了，也不愿叫你白白忧心。",
                        "你能问这一句，我便知道自己不是孤身撑着。",
                    ],
                )
            return self._stable_pick(
                name,
                "stance-care-neutral",
                [
                    "这点辛苦我还撑得住，只是后头的分寸仍要看清。",
                    "眼下尚可，你不必替我多担一层心。",
                    "我这里还稳得住，先把眼前的事看明再说。",
                ],
            )

        if topic == "view":
            if priority == "智慧":
                return self._stable_pick(
                    name,
                    "stance-view-wisdom",
                    [
                        "依我看，眼前一层是利害，后头一层是变数，两边都得看。",
                        "我先看明处，再看暗处，不肯只凭眼前这一下定论。",
                        "这类事最怕只看一面，我总愿意把后势也一道算进去。",
                    ],
                )
            if priority in {"忠诚", "正义"}:
                return self._stable_pick(
                    name,
                    "stance-view-justice",
                    [
                        "依我看，先把理和义摆正，许多话自然就不难判断。",
                        "我先看的不是热闹，而是谁该担什么、谁又肯不肯认。",
                        "这事若失了名分和信义，后头再周全也总像缺了一块。",
                    ],
                )
            return self._stable_pick(
                name,
                "stance-view-other",
                [
                    "依我看，事情总得一层层剥开，急着下断语反倒误事。",
                    "依我看，这一步先别说满，留点转圜才走得久。",
                    "依我看，越是看似简单的事，越该把人心这一层想透。",
                ],
            )

        if voice["primary_priority"] in {"责任", "善良"}:
            return self._stable_pick(
                name,
                "stance-general-duty",
                [
                    "我先惦记的，不是自己痛快与否，而是众人能不能站稳。",
                    "许多话看似轻，真正压下去的却是身边人的去处。",
                    "这件事我总要先从人心和后果两头想一遍。",
                ],
            )
        if voice["primary_priority"] == "勇气":
            return self._stable_pick(
                name,
                "stance-general-courage",
                [
                    "真到该扛的时候，我不会往后退，只是不愿把力气使偏。",
                    "我说话向来不躲闪，但每一步也得落在该落的地方。",
                    "要紧处我愿顶上去，可总得先知道自己在替谁顶。",
                ],
            )
        if voice["primary_priority"] in {"忠诚", "正义"}:
            return self._stable_pick(
                name,
                "stance-general-justice",
                [
                    "我心里先过的是信义这一关，过得去，话才说得硬。",
                    "事能不能做，不只看利害，还看它配不配让我认下。",
                    "我宁可慢一点，也不愿把该守的东西先丢了。",
                ],
            )
        if voice["primary_priority"] == "智慧":
            return self._stable_pick(
                name,
                "stance-general-wisdom",
                [
                    "眼下我还想再多看一步，不愿只凭表面就落槌。",
                    "越到这种时候，越不能拿第一眼见到的东西当全貌。",
                    "我宁可先把风向摸清，也不肯随手把话说死。",
                ],
            )
        return self._stable_pick(
            name,
            "stance-general-default",
            [
                "我不愿把情绪说得太满，但意思已经摆在这里。",
                "这件事我会记着，只是分寸仍得慢慢看。",
                "我心里有数，只是不想把话头一下推到尽处。",
            ],
        )

    def _relation_line(
        self,
        name: str,
        target_name: str,
        voice: Dict[str, Any],
        relation_state: Dict[str, Any],
    ) -> str:
        if not target_name:
            return ""
        affection = int(relation_state.get("affection", 5))
        trust = int(relation_state.get("trust", 5))
        hostility = int(relation_state.get("hostility", max(0, 5 - affection)))
        power_gap = int(relation_state.get("power_gap", 0))

        if hostility >= 7:
            return self._stable_pick(
                name,
                "relation-hostile",
                [
                    f"至于你我之间的账，我不会因为一句话就轻轻揭过。",
                    f"和你说这话，我自然还得留着防备，不会轻信半分。",
                ],
            )
        if affection >= 8 and trust >= 7:
            return self._stable_pick(
                name,
                "relation-close",
                [
                    f"你在我心里分量不轻，所以这话我不肯敷衍。",
                    f"正因为是对你说，我才愿把话再往深处说一层。",
                ],
            )
        if trust <= 3:
            return self._stable_pick(
                name,
                "relation-lowtrust",
                [
                    f"只是和你谈这件事，我终究还要把戒心留着。",
                    f"你我之间尚未到能尽数交底的时候，我只能说到这里。",
                ],
            )
        if power_gap >= 2:
            return self._stable_pick(
                name,
                "relation-gap",
                [
                    f"你我位置有轻重之分，这句话我也得顾着分寸来说。",
                    f"话虽要说明，可场面和上下轻重，我也不能装作看不见。",
                ],
            )
        return ""

    def _drive_line(self, name: str, voice: Dict[str, Any], topic: str) -> str:
        goal = voice.get("goal", "")
        role = voice.get("role", "")
        worldview = voice.get("worldview", "")
        thinking_style = voice.get("thinking_style", "")
        if topic in {"decision", "war"} and worldview:
            return self._stable_pick(
                name,
                "drive-war",
                [
                    f"说到底，我看事一向是这样：{worldview}",
                    f"我之所以这样答，是因为我心里一直认这个理：{worldview}",
                    f"这不只是眼前取舍，在我这里始终绕不开一句：{worldview}",
                ],
            )
        if role and goal:
            return self._stable_pick(
                name,
                "drive-general",
                [
                    f"我这个人向来是{role}，所以总会先想到{goal}。",
                    f"我习惯先把自己放在{role}的位置上，再去看{goal}。",
                    f"我心里的那条线一直没变过，就是要{goal}。",
                ],
            )
        if thinking_style:
            return self._stable_pick(
                name,
                "drive-thinking",
                [
                    f"我这一向的路数，不过是{thinking_style}",
                    f"若问我为何这样回，不过是因为我总习惯{thinking_style}",
                    f"这也是我一贯的想法：{thinking_style}",
                ],
            )
        return ""

    def _memory_line(
        self,
        name: str,
        profile: Dict[str, Any],
        voice: Dict[str, Any],
        topic: str,
        relation_hint: str,
    ) -> str:
        explicit_identity = str(profile.get("identity_anchor", "")).strip()
        experience = voice.get("experience", "")

        if explicit_identity and topic in {"decision", "war", "view"}:
            return self._stable_pick(
                name,
                "memory-identity",
                [
                    f"我毕竟一直把自己看作{explicit_identity}，说话做事都绕不开这一层。",
                    f"我这些判断，也都是站在{explicit_identity}的位置上得来的。",
                    f"我不是只替一时情绪开口，我心里一直记着自己是{explicit_identity}。",
                ],
            )

        if experience:
            return experience

        if relation_hint and topic == "general":
            return "人与人之间的轻重我记得清，所以不会拿一句话就把关系说绝。"
        return ""

    def _compose_reply(self, segments: List[str], voice: Dict[str, Any]) -> str:
        cleaned = []
        forbidden_fillers = set(voice.get("speech_habits", {}).get("forbidden_fillers", []))
        cadence = voice.get("speech_habits", {}).get("cadence", "medium")

        for item in segments:
            text = str(item or "").strip()
            if not text:
                continue
            for filler in forbidden_fillers:
                text = text.replace(filler, "")
            if text[-1] not in "。！？":
                text = f"{text}。"
            if cleaned and cleaned[-1] == text:
                continue
            cleaned.append(text)

        if not cleaned:
            return "这件事我会记着，再看一步。"

        if cadence == "short":
            cleaned = cleaned[:3]
        elif cadence == "medium":
            cleaned = cleaned[:4]
        else:
            cleaned = cleaned[:5]

        return "".join(cleaned)

    @staticmethod
    def _stable_pick(name: str, tag: str, options: List[str]) -> str:
        if not options:
            return ""
        seed = sum(ord(ch) for ch in f"{name}:{tag}")
        return options[seed % len(options)]
