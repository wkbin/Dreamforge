#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple


class DistillationProfileBuilderMixin:
    _INSUFFICIENT_EVIDENCE = "证据不足"

    def _build_profile(
        self,
        name: str,
        bucket: Dict[str, List[str]],
        arc_values: List[Tuple[int, Dict[str, int]]],
    ) -> Dict[str, Any]:
        character_hint = self._resolve_character_hint(name)
        descriptions = self._dedupe_texts(bucket["descriptions"], 24)
        dialogues = self._dedupe_texts(bucket["dialogues"], 8)
        thoughts = self._dedupe_texts(bucket["thoughts"], 12)
        timeline = list(bucket.get("timeline", []))
        evidence_lines = self._dedupe_texts([*descriptions, *thoughts, *dialogues], 32)
        narrative_lines = self._dedupe_texts([*descriptions, *thoughts], 16)
        archetype = self._infer_archetype(name, descriptions, dialogues, thoughts)
        values = self._infer_values_from_corpus(self._merge_arc_values(arc_values), descriptions, dialogues, thoughts, archetype)
        core_traits = self._infer_traits(descriptions + dialogues + thoughts, archetype)
        speech_style = self._infer_speech_style(dialogues, archetype)
        decision_rules = self._dedupe_texts([*thoughts, *descriptions, *dialogues], 8)
        if not decision_rules:
            decision_rules = self._infer_decision_rules(thoughts, descriptions, dialogues, archetype)
        arc = self._build_arc(arc_values, values, timeline)
        life_experience = narrative_lines[:4] or dialogues[:2]
        if not life_experience:
            life_experience = [name]

        used_scalars: Set[str] = set()
        identity_anchor = self._select_distinct_seed(narrative_lines, dialogues, fallback=name, used=used_scalars)
        soul_goal = self._select_distinct_seed(thoughts, decision_rules, fallback=self._INSUFFICIENT_EVIDENCE, used=used_scalars)
        trauma_scar = self._select_distinct_seed(
            thoughts,
            [self._infer_trauma_scar(life_experience, thoughts, descriptions, archetype)],
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        worldview = self._select_reasoned_scalar_seed(
            thoughts,
            descriptions,
            fallback=self._infer_worldview(values, core_traits, archetype),
            used=used_scalars,
        )
        thinking_style = self._infer_thinking_style(values, core_traits, speech_style, archetype)
        speech_habits = self._infer_speech_habits(dialogues, speech_style)
        emotion_profile = self._infer_emotion_profile(dialogues, thoughts, speech_style, core_traits)
        temperament_type = self._infer_temperament_type(core_traits, speech_style, values, archetype)
        taboo_topics = self._infer_taboo_topics(values, core_traits, decision_rules)
        forbidden_behaviors = self._infer_forbidden_behaviors(values, core_traits, speech_style)
        core_identity = self._select_distinct_seed(descriptions, [identity_anchor], fallback=identity_anchor, used=used_scalars)
        faction_position = self._infer_faction_position(name, descriptions, dialogues, thoughts, values)
        background_imprint = self._select_distinct_seed(
            life_experience,
            descriptions,
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        world_rule_fit = self._infer_world_rule_fit(values, decision_rules, speech_style)
        strengths = self._infer_strengths(core_traits, decision_rules, speech_style)
        weaknesses = self._infer_weaknesses(core_traits, emotion_profile, speech_style)
        cognitive_limits = self._infer_cognitive_limits(values, core_traits)
        action_style = self._select_distinct_seed(
            descriptions,
            dialogues,
            [speech_style],
            fallback=speech_style or self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        social_mode = self._select_distinct_seed(
            dialogues,
            descriptions,
            [speech_style, action_style],
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        key_bonds = self._infer_key_bonds(values, decision_rules, taboo_topics)
        reward_logic = self._select_distinct_seed(
            decision_rules,
            thoughts,
            [worldview],
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        hidden_desire = self._select_distinct_seed(thoughts, [soul_goal], fallback=soul_goal, used=used_scalars)
        inner_conflict = self._select_distinct_seed(
            thoughts[1:],
            [hidden_desire],
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        fear_triggers = self._infer_fear_triggers(values, taboo_topics, forbidden_behaviors)
        private_self = self._select_distinct_seed(
            thoughts,
            [self._infer_private_self(speech_style, emotion_profile, social_mode)],
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        story_role = self._select_distinct_seed(
            descriptions,
            [self._infer_story_role(descriptions, dialogues, thoughts, decision_rules)],
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        belief_anchor = self._select_reasoned_scalar_seed(
            [worldview, soul_goal],
            fallback=self._infer_belief_anchor(values, worldview),
            used=used_scalars,
        )
        stance_stability = self._infer_stance_stability(values, decision_rules)
        moral_bottom_line = self._select_reasoned_scalar_seed(
            forbidden_behaviors,
            [belief_anchor],
            fallback=self._infer_moral_bottom_line(values, forbidden_behaviors, belief_anchor, archetype),
            used=used_scalars,
        )
        self_cognition = self._select_distinct_seed(
            thoughts,
            [identity_anchor],
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        stress_response = self._select_distinct_seed(
            [
                self._infer_stress_response(
                    emotion_profile,
                    decision_rules,
                    speech_style,
                    forbidden_behaviors,
                    archetype,
                )
            ],
            thoughts,
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        others_impression = self._select_distinct_seed(
            descriptions,
            [speech_style, identity_anchor],
            fallback=self._INSUFFICIENT_EVIDENCE,
            used=used_scalars,
        )
        restraint_threshold = self._select_reasoned_scalar_seed(
            thoughts,
            forbidden_behaviors,
            [hidden_desire],
            fallback=self._infer_restraint_threshold(values, speech_style, hidden_desire, forbidden_behaviors, archetype),
            used=used_scalars,
        )

        profile = {
            "name": name,
            "core_traits": core_traits[: int(self.config.get("distillation.traits_max_count", 10))],
            "values": values,
            "speech_style": speech_style,
            "typical_lines": dialogues[:8],
            "decision_rules": decision_rules[:8],
            "identity_anchor": identity_anchor,
            "soul_goal": soul_goal,
            "life_experience": life_experience[:4],
            "trauma_scar": trauma_scar,
            "worldview": worldview,
            "thinking_style": thinking_style,
            "temperament_type": temperament_type,
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
            "moral_bottom_line": moral_bottom_line,
            "self_cognition": self_cognition,
            "stress_response": stress_response,
            "others_impression": others_impression,
            "restraint_threshold": restraint_threshold,
            "stance_stability": stance_stability,
            "arc": arc,
            "arc_summary": self._infer_arc_summary(arc),
            "arc_confidence": self._infer_arc_confidence(arc, timeline),
            "archetype": archetype,
            "evidence_excerpt": evidence_lines[:8],
        }
        return self._apply_character_hint(profile, character_hint)

    def _select_distinct_seed(
        self,
        *groups: List[str],
        fallback: str,
        used: Set[str],
    ) -> str:
        for group in groups:
            for raw in group:
                candidate = str(raw or "").strip()
                normalized = self._normalize_seed(candidate)
                if not normalized or normalized in used:
                    continue
                used.add(normalized)
                return candidate
        fallback_text = str(fallback or "").strip() or self._INSUFFICIENT_EVIDENCE
        normalized_fallback = self._normalize_seed(fallback_text)
        if normalized_fallback:
            used.add(normalized_fallback)
        return fallback_text

    @staticmethod
    def _normalize_seed(value: str) -> str:
        return "".join(str(value or "").split())

    def _select_reasoned_scalar_seed(
        self,
        *groups: List[str],
        fallback: str,
        used: Set[str],
    ) -> str:
        for group in groups:
            for raw in group:
                candidate = str(raw or "").strip()
                normalized = self._normalize_seed(candidate)
                if not normalized or normalized in used:
                    continue
                if not self._looks_like_reasoned_scalar(candidate):
                    continue
                used.add(normalized)
                return candidate
        fallback_text = str(fallback or "").strip() or self._INSUFFICIENT_EVIDENCE
        normalized_fallback = self._normalize_seed(fallback_text)
        if normalized_fallback:
            used.add(normalized_fallback)
        return fallback_text

    @classmethod
    def _looks_like_reasoned_scalar(cls, value: str) -> bool:
        text = str(value or "").strip()
        if not text or text == cls._INSUFFICIENT_EVIDENCE:
            return False
        if cls._looks_like_metadata_sentence(text):
            return False
        if any(token in text for token in ('"', "“", "”", "‘", "’", "「", "」")):
            return False
        if text.endswith(("：", ":", "，", ",", "；", ";", "、")):
            return False
        if re.search(r"(只见|忽见|回头|转过|只听|听见|听得|说道|笑道|问道|喝道|骂道|叹道|叫道|想道)", text):
            return False
        if re.search(r"(心里还自|大家想着|拍着手|走了出来|走进去|看了.*一眼)", text):
            return False
        if len(text) > 40:
            return False
        return True
