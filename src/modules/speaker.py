#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.modules.reflection import ReflectionEngine


class Speaker:
    """Character utterance generator with correction-memory retrieval."""

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

        affection = int(relation_state.get("affection", 5))
        trust = int(relation_state.get("trust", 5))
        hostility = int(relation_state.get("hostility", max(0, 5 - affection)))
        ambiguity = int(relation_state.get("ambiguity", 3))

        traits = [str(item).strip() for item in character_profile.get("core_traits", []) if str(item).strip()]
        speech_style = str(character_profile.get("speech_style", ""))
        has_correction = bool(similar)
        preferred_target = self._preferred_target_name(name, target_name, relation_state)

        context_reply = self._context_reply(context, traits, affection, trust, hostility, ambiguity)
        opening = self._opening_line(
            target_name=preferred_target,
            affection=affection,
            trust=trust,
            hostility=hostility,
            ambiguity=ambiguity,
            speech_style=speech_style,
            has_correction=has_correction,
        )
        return f"{opening}{context_reply}"

    @staticmethod
    def _preferred_target_name(speaker_name: str, target_name: str, relation_state: Dict[str, Any]) -> str:
        appellations = relation_state.get("appellations", {})
        if not isinstance(appellations, dict):
            return target_name
        key = f"{speaker_name}->{target_name}"
        preferred = str(appellations.get(key, "")).strip()
        return preferred or target_name

    @staticmethod
    def _opening_line(
        target_name: str,
        affection: int,
        trust: int,
        hostility: int,
        ambiguity: int,
        speech_style: str,
        has_correction: bool,
    ) -> str:
        address = f"{target_name}，" if target_name else ""
        if hostility >= 7:
            return f"{address}这话我听见了，只是眼下不想逼得太近。"
        if has_correction:
            return f"{address}你的意思我明白，我还是照一向的心性慢慢说。"
        if affection >= 8 and trust >= 7:
            return f"{address}你既这样问，我便认真回你。"
        if ambiguity >= 7:
            return f"{address}这件事我先不把话说死。"
        if "克制" in speech_style:
            return f"{address}你先别急，容我缓一缓再说。"
        if "直白" in speech_style:
            return f"{address}你既问起，我就直说。"
        return f"{address}你既开了口，我便照实回你。"

    @staticmethod
    def _context_reply(
        context: str,
        traits: List[str],
        affection: int,
        trust: int,
        hostility: int,
        ambiguity: int,
    ) -> str:
        primary_trait = traits[0] if traits else ""

        if any(token in context for token in ("是否", "要不要", "该不该", "可否", "能否", "应否")):
            if hostility >= 7:
                return "依我看，此事不宜轻动，免得再添枝节。"
            if primary_trait in {"聪慧", "谨慎"} or ambiguity >= 6:
                return "依我看，还要先探明虚实，再作定夺。"
            if primary_trait in {"敏感", "克制"}:
                return "依我看，可以先留一步余地，不必急着把路走绝。"
            if affection >= 8 and trust >= 7:
                return "依我看，可以一试，但务必要把后手留稳。"
            return "依我看，此事能做，但要先把轻重想明白。"

        if any(token in context for token in ("战事", "对抗", "联合", "出兵", "退兵", "攻", "守")):
            if primary_trait in {"聪慧", "谨慎"}:
                return "战阵上的事，最怕只凭一时意气，还是先看局势再动。"
            if primary_trait in {"敏感", "克制"}:
                return "兵事一起，牵动的就不止你我，断不可轻率。"
            return "战事虽急，也总要先把利害分清。"

        if any(token in context for token in ("安稳", "清闲", "共聚", "团聚", "难得清闲")):
            if affection >= 8 and trust >= 7:
                return "难得有这一刻安稳，倒也该把心里的话说得和缓些。"
            if primary_trait in {"敏感", "克制"}:
                return "眼下虽得片刻清闲，可后面的事终究还在。"
            return "难得暂歇片刻，也该趁此把后面的安排想清楚。"

        if any(token in context for token in ("怎么看", "如何", "何如", "怎么想")):
            if primary_trait in {"聪慧", "谨慎"}:
                return "依我看，眼下还需多看两步，不能只凭眼前。"
            if primary_trait in {"敏感", "克制"}:
                return "依我看，这事不必说得太满，先留一点转圜更稳。"
            return "依我看，事情总该一层层分明白。"

        if hostility >= 7:
            return "今日先说到这里，再逼近一步也无益。"
        if affection >= 8 and trust >= 7:
            return "你既挂念，我心里自然记着。"
        if ambiguity >= 7:
            return "待我再想一想，改日再把余下的话补全。"
        if trust <= 3:
            return "这事我还要再看，不便立刻说透。"
        if primary_trait in {"敏感", "克制"}:
            return "我不愿把情绪说得太满，但意思你该明白。"
        if primary_trait in {"聪慧", "谨慎"}:
            return "眼下先看一步，再定后话。"
        return "事情总要一层层说明白。"
