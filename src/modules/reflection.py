#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.utils.file_utils import ensure_dir, load_json, save_json


@dataclass
class OOCCheckResult:
    is_ooc: bool
    score: float
    reasons: List[str]


class ReflectionEngine:
    """Reflection + correction retrieval for OOC mitigation."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.corrections_dir = ensure_dir(self.config.get_path("corrections"))

    def detect_ooc(self, profile: Dict[str, Any], message: str) -> OOCCheckResult:
        reasons: List[str] = []
        score = 0.0

        speech_style = profile.get("speech_style", "")
        if "克制" in speech_style and ("！！" in message or message.count("!") >= 2):
            reasons.append("情绪表达过激，不符合克制语气")
            score += 0.4
        if "直白" in speech_style and len(message) > 80:
            reasons.append("句子过长，不符合直白表达")
            score += 0.2

        typical = profile.get("typical_lines", [])
        if typical:
            best = max(SequenceMatcher(None, message, t).ratio() for t in typical)
            if best < 0.1:
                score += 0.2
                reasons.append("与角色常见语料相似度较低")

        values = profile.get("values", {})
        if values.get("忠诚", 5) >= 8 and any(k in message for k in ("背叛", "抛弃你们")):
            score += 0.5
            reasons.append("高忠诚角色出现背离表述")

        return OOCCheckResult(is_ooc=score >= 0.5, score=min(score, 1.0), reasons=reasons)

    def save_correction(
        self,
        session_id: str,
        character: str,
        original_message: str,
        corrected_message: str,
        target: Optional[str] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "session_id": session_id,
            "character": character,
            "target": target or "",
            "original_message": original_message,
            "corrected_message": corrected_message,
            "reason": reason,
            "timestamp": int(time.time()),
        }
        file = self.corrections_dir / f"correction_{session_id}_{payload['timestamp']}.json"
        save_json(file, payload)
        payload["file_path"] = str(file)
        return payload

    def search_similar_corrections(
        self,
        text: str,
        character: Optional[str] = None,
        target: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for file in self.corrections_dir.glob("correction_*.json"):
            item = load_json(file, default=None)
            if not item:
                continue
            if character and item.get("character") != character:
                continue
            if target is not None and item.get("target", "") not in ("", target):
                continue
            source = item.get("original_message", "")
            ratio = SequenceMatcher(None, text, source).ratio()
            if ratio < 0.2:
                continue
            item["similarity"] = round(ratio, 4)
            results.append(item)

        results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return results[:top_k]

    def relation_alignment_issues(self, message: str, relation_state: Dict[str, Any]) -> List[str]:
        """Check whether a message tone conflicts with target-specific relation state."""
        issues: List[str] = []
        affection = int(relation_state.get("affection", 5))
        trust = int(relation_state.get("trust", 5))
        hostility = int(relation_state.get("hostility", max(0, 5 - affection)))
        ambiguity = int(relation_state.get("ambiguity", 3))

        warm_markers = ("关心", "抱歉", "理解你", "别难过", "我在", "我们")
        harsh_markers = ("滚", "蠢", "闭嘴", "讨厌", "厌恶", "烦死")

        if hostility >= 7 and any(w in message for w in warm_markers):
            issues.append("高敌意关系下出现过度亲近措辞")
        if affection >= 7 and any(h in message for h in harsh_markers):
            issues.append("高好感关系下出现强攻击措辞")
        if trust <= 2 and "完全相信" in message:
            issues.append("低信任关系下出现不合理绝对信任")
        if ambiguity >= 7 and ("永远" in message or "绝不" in message):
            issues.append("高暧昧/不确定关系下出现过度绝对表态")

        return issues
