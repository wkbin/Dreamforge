#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Dict, Iterable, List, Tuple


class DistillationInferenceMixin:
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
        best_name = "default"
        best_score = 0
        second_score = 0
        for archetype_name, config in self.archetypes.items():
            markers = [str(item).strip() for item in config.get("markers", []) if str(item).strip()]
            score = 0
            for marker in markers:
                score += 2 * sum(line.count(marker) for line in dialogues[:10])
                score += 2 * sum(line.count(marker) for line in thoughts[:10])
                score += sum(line.count(marker) for line in descriptions[:10])
                score += name.count(marker)
            if score > best_score:
                second_score = best_score
                best_name = archetype_name
                best_score = score
            elif score > second_score:
                second_score = score
        if best_score >= 4:
            return best_name
        if best_score >= 2 and best_score >= second_score + 1:
            return best_name
        return "default"

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
        description_corpus = " ".join(descriptions[:12])
        dialogue_corpus = " ".join(dialogues[:12])
        thought_corpus = " ".join(thoughts[:12])
        merged = {dim: int(values.get(dim, 5)) for dim in dims}
        for dim in dims:
            config = self.value_markers.get(dim, {})
            positive = (
                sum(description_corpus.count(token) for token in config.get("positive", []))
                + 2 * sum(dialogue_corpus.count(token) for token in config.get("positive", []))
                + 2 * sum(thought_corpus.count(token) for token in config.get("positive", []))
            )
            negative = (
                sum(description_corpus.count(token) for token in config.get("negative", []))
                + 2 * sum(dialogue_corpus.count(token) for token in config.get("negative", []))
                + 2 * sum(thought_corpus.count(token) for token in config.get("negative", []))
            )
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
        return DistillationInferenceMixin._dedupe_texts(lines, 12)

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
        if configured:
            return configured
        if not lines:
            return "少言留分寸"
        avg_len = sum(len(item) for item in lines) / max(1, len(lines))
        exclaim_ratio = sum(1 for item in lines if any(token in item for token in ("!", "！", "?", "？")))
        if avg_len <= 12:
            return "短句直给"
        if exclaim_ratio >= max(1, len(lines) // 3):
            return "情绪外露"
        if avg_len >= 26:
            return "长句铺陈"
        return "分寸平稳"

    def _infer_decision_rules(
        self,
        thoughts: List[str],
        descriptions: List[str],
        dialogues: List[str],
        archetype: str,
    ) -> List[str]:
        corpus_lines = self._dedupe_texts(thoughts[:12] + dialogues[:12] + descriptions[:12], 30)
        signal_map = {
            "先辨虚实": ("先看", "看清", "试探", "探明", "真假", "虚实"),
            "先守边界": ("不可", "不能", "休得", "越线", "底线", "规矩"),
            "先护自己人": ("保护", "护住", "拦住", "挡住", "守住", "自己人"),
            "先稳局面": ("稳住", "收住", "安顿", "接应", "后手", "后路"),
            "先留转圆": ("罢了", "不过", "何必", "且慢", "等等"),
        }
        scored_rules: List[Tuple[int, str]] = []
        for label, markers in signal_map.items():
            marker_hits = 0
            sentence_hits = 0
            for line in corpus_lines:
                hit_count = sum(line.count(marker) for marker in markers)
                if hit_count <= 0:
                    continue
                marker_hits += min(3, hit_count)
                sentence_hits += 1
            if marker_hits > 0:
                scored_rules.append((marker_hits + min(3, sentence_hits), label))
        scored_rules.sort(key=lambda item: item[0], reverse=True)
        rules = [rule for _, rule in scored_rules[:3]]
        archetype_rules = [
            str(item).strip() for item in self.archetypes.get(archetype, {}).get("decision_rules", []) if str(item).strip()
        ]
        if len(rules) < 2:
            rules.extend(archetype_rules[: 2 - len(rules)])
        if not rules:
            rules.append("先分轻重")
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

    def _infer_trauma_scar(
        self,
        life_experience: List[str],
        thoughts: List[str],
        descriptions: List[str],
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("trauma_scar", "")).strip()
        if configured:
            return configured
        corpus = " ".join(thoughts[:6] + descriptions[:6])
        if any(token in corpus for token in ("不敢", "心里一沉", "发冷", "后怕", "旧事", "刺痛", "噎住")):
            return "旧伤在高压时会被重新扯开，因此一旦触到痛点，反应会比表面更深。"
        if any("失去" in item or "来不及" in item for item in life_experience[:4]):
            return "经历里留下过“没能接住”或“终究失去”的痕迹，所以面对类似局面会明显绷紧。"
        if life_experience:
            return "过往经历留下的精神擦痕仍在，平时压着不说，遇到相似处境就会浮上来。"
        return "旧伤更多以边界感和防御姿态存在，未必常说，但会在关键时刻显形。"

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

    def _infer_temperament_type(
        self,
        core_traits: List[str],
        speech_style: str,
        values: Dict[str, int],
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("temperament_type", "")).strip()
        if configured:
            return configured
        if "敏感" in core_traits and "克制" in speech_style:
            return "高敏感、外冷内热型"
        if "傲气" in core_traits:
            return "清冷带锋芒型"
        if "勇敢" in core_traits and values.get("勇气", 5) >= 7:
            return "直接顶压型"
        if "沉稳" in core_traits or values.get("责任", 5) >= 7:
            return "沉稳托底型"
        if "诙谐" in core_traits:
            return "松弛外放型"
        return "克制观察型" if "克制" in speech_style else "外显行动型"

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
            if DistillationInferenceMixin._looks_like_metadata_sentence(line):
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
        return DistillationInferenceMixin._dedupe_texts(strengths, 5)

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
        return DistillationInferenceMixin._dedupe_texts(weaknesses, 5)

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
        return DistillationInferenceMixin._dedupe_texts(limits, 4)

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
        return DistillationInferenceMixin._dedupe_texts(bonds, 4)


    @staticmethod
    def _infer_reward_logic(values: Dict[str, int], core_traits: List[str]) -> str:
        if values.get("忠诚", 5) >= 7:
            return "记恩，也记失信"
        if values.get("正义", 5) >= 7:
            return "先看是非，再看亲疏"
        if values.get("自由", 5) >= 7:
            return "记操控，也记留余地"
        if "敏感" in core_traits:
            return "对冷热态度记得很深"
        return "看越没越线，也看关键时刻站没站住"

    @staticmethod
    def _infer_hidden_desire(values: Dict[str, int], soul_goal: str) -> str:
        if values.get("责任", 5) >= 7:
            return "想守住能让自己安心的人和位置"
        if values.get("自由", 5) >= 7:
            return "想保住不被摆布的活法"
        if values.get("忠诚", 5) >= 7:
            return "想确认关系不会再散"
        if values.get("正义", 5) >= 7:
            return "想让真相别被压住"
        return soul_goal or "有一层不愿被人轻易看穿的执念"
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
        return DistillationInferenceMixin._dedupe_texts(fears, 5)


    @staticmethod
    def _infer_private_self(speech_style: str, emotion_profile: Dict[str, Any], social_mode: str) -> str:
        if "克制" in speech_style:
            return "表面收紧，私下记得更深"
        if "短句" in speech_style:
            return "表面利落，独处时会反复掂量"
        if "委屈" in str(emotion_profile.get("grievance_style", "")):
            return "难受多半留到无人处消化"
        return f"表里不完全一致，更在意：{social_mode}"

    @staticmethod
    def _infer_story_role(
        descriptions: List[str],
        dialogues: List[str],
        thoughts: List[str],
        decision_rules: List[str],
    ) -> str:
        presence = len(descriptions) + len(dialogues) + len(thoughts)
        if presence >= 40:
            base = "核心推动者"
        elif presence >= 24:
            base = "主要支点"
        elif presence >= 12:
            base = "重要牵动者"
        else:
            base = "辅助推动者"
        if any("护" in rule or "后手" in rule for rule in decision_rules):
            return f"{base}，兼顾托底"
        if len(dialogues) >= max(4, len(descriptions) // 2):
            return f"{base}，更多靠对话推动"
        return f"{base}，会持续影响走向"

    @staticmethod
    def _infer_belief_anchor(values: Dict[str, int], worldview: str) -> str:
        if values.get("忠诚", 5) >= 7:
            return "信义不能后置"
        if values.get("正义", 5) >= 7:
            return "是非必须站稳"
        if values.get("责任", 5) >= 7:
            return "该接的担子要接住"
        if values.get("自由", 5) >= 7:
            return "不能活成别人手里的棋"
        return worldview or "有一套不轻易改口的内在秩序"
    def _infer_moral_bottom_line(
        self,
        values: Dict[str, int],
        forbidden_behaviors: List[str],
        belief_anchor: str,
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("moral_bottom_line", "")).strip()
        if configured:
            return configured
        if values.get("正义", 5) >= 7:
            return "可以周旋，但不能把黑白彻底倒过来，更不能拿无辜者垫底。"
        if values.get("忠诚", 5) >= 7:
            return "可以吃亏、可以承压，但不能主动卖掉自己认下的人。"
        if values.get("责任", 5) >= 7:
            return "再难也不能把该接的责任甩给更弱的人。"
        if forbidden_behaviors:
            return forbidden_behaviors[0].replace("不会", "底线是不肯").replace("无缘无故", "平白")
        return belief_anchor or "底线通常落在不肯自毁原则、也不肯轻易伤及无辜。"

    def _infer_self_cognition(
        self,
        identity_anchor: str,
        core_traits: List[str],
        private_self: str,
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("self_cognition", "")).strip()
        if configured:
            return configured
        if identity_anchor:
            return f"自我认知偏向：{identity_anchor}"
        if "敏感" in core_traits:
            return "知道自己不是迟钝的人，所以更容易先一步察觉气氛与裂痕。"
        if "勇敢" in core_traits:
            return "默认关键时刻该由自己先顶上，但也清楚这种习惯会把自己推得过前。"
        return private_self or "对自己并非毫无自觉，只是不愿把最真实的一层轻易交代给旁人。"


    def _infer_stress_response(
        self,
        emotion_profile: Dict[str, Any],
        decision_rules: List[str],
        speech_style: str,
        forbidden_behaviors: List[str],
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("stress_response", "")).strip()
        if configured:
            return configured
        if any("虚实" in rule or "先辨虚实" in rule for rule in decision_rules):
            return "高压下会先拆局找破口"
        if "克制" in speech_style:
            return "越到绝境越压低情绪"
        if forbidden_behaviors:
            return f"被逼急时会收紧边界，但仍守着“{forbidden_behaviors[0]}”"
        return str(emotion_profile.get("anger_style", "")).strip() or "压力上来会先绷紧再自保"

    def _infer_others_impression(
        self,
        core_identity: str,
        core_traits: List[str],
        speech_style: str,
        social_mode: str,
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("others_impression", "")).strip()
        if configured:
            return configured
        if core_identity:
            return f"外人先记住：{core_identity}"
        if "克制" in speech_style:
            return "第一印象多半是不好接近"
        if "勇敢" in core_traits:
            return "第一眼容易觉得他硬气敢顶"
        return social_mode or "旁人先从态度和边界感认识他"

    def _infer_restraint_threshold(
        self,
        values: Dict[str, int],
        speech_style: str,
        hidden_desire: str,
        forbidden_behaviors: List[str],
        archetype: str,
    ) -> str:
        configured = str(self.archetypes.get(archetype, {}).get("restraint_threshold", "")).strip()
        if configured:
            return configured
        if values.get("责任", 5) >= 7 or "克制" in speech_style:
            return "平时压得住，逼到底线才会失控"
        if values.get("自由", 5) >= 7:
            return "被彻底钳死时克制力会下降"
        if forbidden_behaviors:
            return f"多数时候会克制自己不越过“{forbidden_behaviors[0]}”"
        return hidden_desire or "平时能压住，逼急了才会翻面"
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
        cleaned = DistillationInferenceMixin._unique_texts(
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
            top.append(top[-1] if top else "责任")
        return top
