#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.core.llm_client import LLMClient
from src.modules.reflection import ReflectionEngine
from src.modules.speaker import Speaker
from src.utils.file_utils import (
    canonical_aliases,
    ensure_dir,
    load_json,
    normalize_character_name,
    normalize_relation_key,
    novel_id_from_input,
    save_json,
)


class ChatEngine:
    """Multi-character chat with novel-scoped assets."""

    SYSTEM_SPEAKERS = {"Narrator", "User", "旁白", "用户"}
    ADDRESS_SUFFIXES = ("哥哥", "姐姐", "妹妹", "弟弟", "姑娘", "公子", "爷")

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm = LLMClient(self.config)
        self.reflection = ReflectionEngine(self.config)
        self.speaker = Speaker(self.config)
        self.characters_dir = Path(self.config.get_path("characters"))
        self.sessions_dir = ensure_dir(self.config.get_path("sessions"))
        self.relations_dir = ensure_dir(self.config.get_path("relations"))

    def create_session(self, novel: str, mode: str) -> Dict[str, Any]:
        novel_id = novel_id_from_input(novel)
        profiles = self._load_character_profiles(novel_id)
        if not profiles:
            raise RuntimeError(f"No character profiles found for novel '{novel_id}'. Run distill first.")

        characters = list(profiles.keys())
        session = {
            "id": uuid.uuid4().hex[:12],
            "title": f"{novel}_{mode}_{int(time.time())}",
            "novel": novel,
            "novel_id": novel_id,
            "mode": mode,
            "created_at": int(time.time()),
            "characters": characters,
            "history": [],
            "state": {
                "emotion": {},
                "focus_targets": {},
                "relation_delta": {},
                "relation_matrix": self._build_relation_matrix(characters, novel_id),
            },
        }
        self._save_session(session)
        return session

    def restore_session(self, session_id: str) -> Dict[str, Any]:
        path = self.sessions_dir / f"{session_id}.json"
        data = load_json(path, default=None)
        if not data:
            raise FileNotFoundError(f"Session not found: {session_id}")
        data.setdefault("novel_id", novel_id_from_input(data.get("novel", session_id)))
        data.setdefault("state", {})
        data["state"].setdefault("focus_targets", {})
        return data

    def observe_mode(self, session: Dict[str, Any]) -> None:
        print("进入 observe 模式。输入 /save /reflect /correct /quit")
        while True:
            user_msg = input("\n你: ").strip()
            if not user_msg:
                continue
            if self._handle_inline_command(session, user_msg):
                if user_msg == "/quit":
                    break
                continue

            responses = self.observe_once(session, user_msg)
            self._print_responses(responses)
            self.print_turn_cost()
            self.print_correction_hint(session)

    def act_mode(self, session: Dict[str, Any], character: str) -> None:
        controlled = self._resolve_character_name(character, session["characters"])
        if controlled not in session["characters"]:
            raise ValueError(f"Character '{character}' not found in this session.")

        print(f"进入 act 模式，你扮演 {controlled}。输入 /save /reflect /correct /quit")
        while True:
            user_msg = input(f"\n{controlled}(你): ").strip()
            if not user_msg:
                continue
            if self._handle_inline_command(session, user_msg):
                if user_msg == "/quit":
                    break
                continue

            try:
                responses = self.act_once(session, controlled, user_msg)
            except ValueError as exc:
                print(exc)
                continue

            self._print_responses(responses)
            self.print_turn_cost()
            self.print_correction_hint(session)

    def observe_once(self, session: Dict[str, Any], user_msg: str) -> List[tuple[str, str]]:
        responders = self._active_characters(session, speaker="Narrator", context=user_msg)
        return self._run_turn(session, "Narrator", user_msg, responders)

    def act_once(self, session: Dict[str, Any], character: str, user_msg: str) -> List[tuple[str, str]]:
        controlled = self._resolve_character_name(character, session["characters"])
        if controlled not in session["characters"]:
            raise ValueError(f"Character '{character}' not found in this session.")

        responders = self._active_characters(session, speaker=controlled, context=user_msg)
        if not responders:
            raise ValueError("未识别到明确对话对象。请在消息里点名角色，或先补充关系数据。")
        return self._run_turn(session, controlled, user_msg, responders)

    def print_turn_cost(self) -> None:
        summary = self.llm.get_cost_summary()
        print(
            f"[累计] token={summary['total_tokens']} "
            f"session=${summary['session_cost']:.4f} daily=${summary['daily_cost']:.4f}"
        )

    @staticmethod
    def print_correction_hint(session: Dict[str, Any]) -> None:
        print(f"修正方式：/correct 角色|对象|原句|修正句|原因  或  correct --session {session['id']} ...")

    def _run_turn(
        self,
        session: Dict[str, Any],
        speaker: str,
        user_msg: str,
        responders: List[str],
    ) -> List[tuple[str, str]]:
        message = user_msg.strip()
        if not message:
            raise ValueError("消息不能为空。")

        session["history"].append({"speaker": speaker, "message": message, "ts": int(time.time())})
        self._remember_focus_targets(session, speaker, responders)
        profiles = self._load_character_profiles(session.get("novel_id"))

        responses: List[tuple[str, str]] = []
        for name in responders:
            profile = profiles.get(name, {"name": name})
            target_name = self._infer_target(name, session["history"], session["characters"])
            relation_state = self._get_relation_state(session, name, target_name)
            reply = self.speaker.generate(
                character_profile=profile,
                context=message,
                history=session["history"],
                target_name=target_name,
                relation_state=relation_state,
                relation_hint=self._relation_hint(name, session["characters"], session.get("novel_id")),
            )
            reply = self._guard_reply(profile, reply, relation_state, target_name)
            responses.append((name, reply))
            session["history"].append(
                {"speaker": name, "target": target_name, "message": reply, "ts": int(time.time())}
            )

        self._trim_history(session)
        self._update_state(session)
        self._save_session(session)
        return responses

    def _remember_focus_targets(self, session: Dict[str, Any], speaker: str, responders: List[str]) -> None:
        if speaker in self.SYSTEM_SPEAKERS or not responders:
            return
        focus_targets = session.setdefault("state", {}).setdefault("focus_targets", {})
        if len(responders) == 1:
            focus_targets[speaker] = responders[0]
        elif speaker in focus_targets:
            focus_targets.pop(speaker, None)

    @staticmethod
    def _print_responses(responses: List[tuple[str, str]]) -> None:
        for speaker, message in responses:
            print(f"{speaker}: {message}")

    def _handle_inline_command(self, session: Dict[str, Any], command: str) -> bool:
        if command == "/quit":
            self._save_session(session)
            print("会话结束。")
            return True
        if command == "/save":
            self._save_session(session)
            print(f"已保存会话: {session['id']}")
            return True
        if command == "/reflect":
            self._reflect_last_turn(session)
            return True
        if command.startswith("/correct"):
            payload = command[len("/correct") :].strip()
            parts = [p.strip() for p in payload.split("|")]
            if len(parts) not in (3, 4, 5):
                print("格式错误。用法: /correct 角色|对象|原句|修正句|原因")
                return True
            if len(parts) == 3:
                character, target, original, corrected, reason = parts[0], "", parts[1], parts[2], "inline_command"
            elif len(parts) == 4:
                character, target, original, corrected, reason = parts[0], parts[1], parts[2], parts[3], "inline_command"
            else:
                character, target, original, corrected, reason = parts[0], parts[1], parts[2], parts[3], parts[4]
            item = self.reflection.save_correction(
                session_id=session["id"],
                character=character,
                target=target or None,
                original_message=original,
                corrected_message=corrected,
                reason=reason,
            )
            print(f"纠错已记录: {item['character']} -> {item.get('target') or '任意对象'}")
            return True
        return False

    def _reflect_last_turn(self, session: Dict[str, Any]) -> None:
        if not session["history"]:
            print("暂无历史可反思。")
            return
        profiles = self._load_character_profiles(session.get("novel_id"))
        last = session["history"][-1]
        profile = profiles.get(last["speaker"])
        if not profile:
            print("最近一条不是角色发言。")
            return
        check = self.reflection.detect_ooc(profile, last["message"])
        if not check.is_ooc:
            print("反思结果：最近发言符合人设。")
            return
        print("反思结果：疑似 OOC")
        for reason in check.reasons:
            print(f"- {reason}")

    def _relation_hint(self, speaker: str, all_chars: List[str], novel_id: Optional[str]) -> str:
        hints = []
        for other in all_chars:
            if other == speaker:
                continue
            item = self._get_relation_state_from_disk(speaker, other, novel_id)
            if item:
                hints.append(
                    f"{other}(trust={item.get('trust', 5)},aff={item.get('affection', 5)},host={item.get('hostility', max(0, 5 - item.get('affection', 5)))})"
                )
        return "; ".join(hints[:3])

    def _relation_file_for_novel(self, novel_id: Optional[str]) -> Optional[Path]:
        if novel_id:
            scoped = self.relations_dir / novel_id / f"{novel_id}_relations.json"
            if scoped.exists():
                return scoped
            legacy = self.relations_dir / f"{novel_id}_relations.json"
            if legacy.exists():
                return legacy
        files = sorted(self.relations_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        return files[0] if files else None

    def _update_state(self, session: Dict[str, Any]) -> None:
        latest = session["history"][-6:]
        emotion = session["state"]["emotion"]
        relation_matrix = session["state"].setdefault("relation_matrix", {})
        for item in latest:
            speaker = item["speaker"]
            if speaker in self.SYSTEM_SPEAKERS:
                continue

            delta = 0
            msg = item["message"]
            if any(k in msg for k in ("！", "怒", "生气", "质问")):
                delta += 1
            if any(k in msg for k in ("冷静", "平静", "慢慢说", "理解")):
                delta -= 1
            emotion[speaker] = max(-5, min(5, emotion.get(speaker, 0) + delta))

            target = item.get("target") or self._infer_target(speaker, latest, session["characters"])
            if not target or target == speaker:
                continue

            key = self._pair_key(speaker, target)
            state = relation_matrix.setdefault(
                key,
                {"trust": 5, "affection": 5, "hostility": 0, "ambiguity": 3},
            )
            if any(k in msg for k in ("谢谢", "抱歉", "理解", "关心", "在意")):
                state["affection"] = min(10, state.get("affection", 5) + 1)
                state["trust"] = min(10, state.get("trust", 5) + 1)
                state["hostility"] = max(0, state.get("hostility", 0) - 1)
            if any(k in msg for k in ("滚", "讨厌", "厌恶", "闭嘴", "烦")):
                state["hostility"] = min(10, state.get("hostility", 0) + 2)
                state["affection"] = max(0, state.get("affection", 5) - 2)
                state["trust"] = max(0, state.get("trust", 5) - 1)
            if any(k in msg for k in ("也许", "或许", "未必", "以后再说")):
                state["ambiguity"] = min(10, state.get("ambiguity", 3) + 1)
            session["state"]["relation_delta"][key] = {
                "trust": state["trust"],
                "affection": state["affection"],
                "hostility": state["hostility"],
                "ambiguity": state["ambiguity"],
            }

    def _save_session(self, session: Dict[str, Any]) -> None:
        save_json(self.sessions_dir / f"{session['id']}.json", session)
        self._save_relation_snapshot(session)

    def _load_character_profiles(self, novel_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        profiles: Dict[str, Dict[str, Any]] = {}
        if not self.characters_dir.exists():
            return profiles

        if novel_id:
            scoped_dir = self.characters_dir / novel_id
            files = sorted(scoped_dir.glob("*.json"))
            if not files:
                legacy_files = sorted(self.characters_dir.glob("*.json"))
                for file in legacy_files:
                    item = load_json(file, default=None)
                    if not item or not isinstance(item, dict) or not item.get("name"):
                        continue
                    item_novel_id = item.get("novel_id")
                    if item_novel_id == novel_id or item_novel_id is None:
                        canonical_name = normalize_character_name(item["name"])
                        item["name"] = canonical_name
                        profiles[canonical_name] = self._merge_profile_item(profiles.get(canonical_name), item)
                return profiles
        else:
            files = sorted(self.characters_dir.glob("*.json"))
            files.extend(sorted(self.characters_dir.glob("*/*.json")))

        for file in files:
            item = load_json(file, default=None)
            if item and isinstance(item, dict) and item.get("name"):
                canonical_name = normalize_character_name(item["name"])
                item["name"] = canonical_name
                profiles[canonical_name] = self._merge_profile_item(profiles.get(canonical_name), item)
        return profiles

    @staticmethod
    def _merge_profile_item(existing: Optional[Dict[str, Any]], incoming: Dict[str, Any]) -> Dict[str, Any]:
        if not existing:
            return incoming
        current_score = len(existing.get("typical_lines", [])) + len(existing.get("core_traits", []))
        incoming_score = len(incoming.get("typical_lines", [])) + len(incoming.get("core_traits", []))
        if incoming_score > current_score:
            merged = incoming.copy()
            fallback = existing
        else:
            merged = existing.copy()
            fallback = incoming

        for key in ("core_traits", "typical_lines", "decision_rules"):
            merged_values = list(merged.get(key, []))
            seen = set(merged_values)
            for item in fallback.get(key, []):
                if item not in seen:
                    merged_values.append(item)
                    seen.add(item)
            merged[key] = merged_values

        if not merged.get("speech_style") and fallback.get("speech_style"):
            merged["speech_style"] = fallback["speech_style"]
        if not merged.get("values") and fallback.get("values"):
            merged["values"] = fallback["values"]
        return merged

    @staticmethod
    def _pair_key(a: str, b: str) -> str:
        return "_".join(sorted([a, b]))

    def _build_relation_matrix(self, characters: List[str], novel_id: Optional[str]) -> Dict[str, Dict[str, Any]]:
        matrix: Dict[str, Dict[str, Any]] = {}
        for speaker in characters:
            for target in characters:
                if speaker == target:
                    continue
                disk = self._get_relation_state_from_disk(speaker, target, novel_id) or {}
                state = {
                    "trust": int(disk.get("trust", 5)),
                    "affection": int(disk.get("affection", 5)),
                    "hostility": int(disk.get("hostility", max(0, 5 - int(disk.get("affection", 5))))),
                    "ambiguity": int(disk.get("ambiguity", 3)),
                }
                for key in ("conflict_point", "typical_interaction", "appellations"):
                    if key in disk:
                        state[key] = disk[key]
                matrix[self._pair_key(speaker, target)] = state
        return matrix

    def _save_relation_snapshot(self, session: Dict[str, Any]) -> None:
        payload = {
            "session_id": session.get("id"),
            "novel_id": session.get("novel_id"),
            "updated_at": int(time.time()),
            "relation_matrix": session.get("state", {}).get("relation_matrix", {}),
            "relation_delta": session.get("state", {}).get("relation_delta", {}),
        }
        save_json(self.sessions_dir / f"{session['id']}_relations.json", payload)

    def _get_relation_state_from_disk(
        self,
        speaker: str,
        target: str,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        rel_file = self._relation_file_for_novel(novel_id)
        if not rel_file:
            return {}
        rel = load_json(rel_file, default={})
        normalized = {normalize_relation_key(key): value for key, value in rel.items()}
        return normalized.get(self._pair_key(normalize_character_name(speaker), normalize_character_name(target)), {})

    def _get_relation_state(self, session: Dict[str, Any], speaker: str, target: str) -> Dict[str, Any]:
        if not target:
            return {}
        matrix = session["state"].setdefault("relation_matrix", {})
        return matrix.get(self._pair_key(speaker, target), {})

    def _active_characters(
        self,
        session: Dict[str, Any],
        speaker: Optional[str] = None,
        context: str = "",
    ) -> List[str]:
        limit = int(self.config.get("chat_engine.max_speakers_per_turn", 4))
        candidates = [name for name in session["characters"] if name != speaker]
        if not candidates:
            return []

        mentioned = self._mentioned_characters(context, candidates)
        if mentioned:
            if session.get("mode") == "act":
                return mentioned[: max(1, min(limit, len(mentioned)))]
            ranked = self._rank_characters(session, speaker, candidates, preferred=mentioned)
            ordered = []
            seen = set()
            for name in mentioned + ranked:
                if name in seen:
                    continue
                ordered.append(name)
                seen.add(name)
                if len(ordered) >= max(1, limit):
                    break
            return ordered

        remembered = self._remembered_target(session, speaker, candidates)
        if remembered:
            return [remembered]

        ranked = self._rank_characters(session, speaker, candidates)
        if session.get("mode") == "act":
            if not ranked:
                return []
            top = ranked[0]
            if self._relation_score(session, speaker, top) <= self._default_relation_score():
                return []
            return [top]
        return ranked[: max(1, limit)]

    def _remembered_target(
        self,
        session: Dict[str, Any],
        speaker: Optional[str],
        candidates: List[str],
    ) -> str:
        if not speaker or speaker in self.SYSTEM_SPEAKERS:
            return ""
        focus_targets = session.get("state", {}).get("focus_targets", {})
        target = focus_targets.get(speaker, "")
        if target in candidates:
            return target
        return ""

    def _trim_history(self, session: Dict[str, Any]) -> None:
        turns = int(self.config.get("chat_engine.max_history_turns", 10))
        keep = max(10, turns * (len(self._active_characters(session)) + 1))
        session["history"] = session["history"][-keep:]

    @staticmethod
    def _candidate_aliases(name: str) -> List[str]:
        aliases: List[str] = []
        clean = normalize_character_name(name)
        aliases.extend(canonical_aliases(clean))
        if len(clean) >= 3:
            given = clean[-2:]
            if len(given) == 2 and given != clean:
                aliases.append(given)
                for suffix in ChatEngine.ADDRESS_SUFFIXES:
                    aliases.append(f"{given[0]}{suffix}")
                    aliases.append(f"{clean[0]}{suffix}")
        elif len(clean) == 2:
            for suffix in ChatEngine.ADDRESS_SUFFIXES:
                aliases.append(f"{clean[0]}{suffix}")
        ordered = []
        seen = set()
        for alias in aliases:
            if alias and alias != clean and alias not in seen:
                ordered.append(alias)
                seen.add(alias)
        return ordered

    def _mentioned_characters(self, context: str, candidates: List[str]) -> List[str]:
        if not context:
            return []

        alias_owners: Dict[str, List[str]] = {}
        for name in candidates:
            for alias in self._candidate_aliases(name):
                alias_owners.setdefault(alias, []).append(name)

        hits: List[tuple[int, str]] = []
        for name in candidates:
            positions = []
            if name in context:
                positions.append(context.index(name))
            for alias in self._candidate_aliases(name):
                if alias_owners.get(alias) != [name]:
                    continue
                if alias in context:
                    positions.append(context.index(alias))
            if positions:
                hits.append((min(positions), name))

        hits.sort(key=lambda item: (item[0], item[1]))
        return [name for _, name in hits]

    @staticmethod
    def _default_relation_score() -> int:
        return 7

    def _relation_score(self, session: Dict[str, Any], speaker: Optional[str], candidate: str) -> int:
        if not speaker or speaker in self.SYSTEM_SPEAKERS:
            return 0
        state = self._get_relation_state(session, speaker, candidate)
        trust = int(state.get("trust", 5))
        affection = int(state.get("affection", 5))
        hostility = int(state.get("hostility", max(0, 5 - affection)))
        ambiguity = int(state.get("ambiguity", 3))
        return trust + affection - hostility - ambiguity

    def _rank_characters(
        self,
        session: Dict[str, Any],
        speaker: Optional[str],
        candidates: List[str],
        preferred: Optional[List[str]] = None,
    ) -> List[str]:
        preferred_set = set(preferred or [])
        return sorted(
            candidates,
            key=lambda name: (
                1 if name in preferred_set else 0,
                self._relation_score(session, speaker, name),
                name,
            ),
            reverse=True,
        )

    def _resolve_character_name(self, raw_name: str, candidates: List[str]) -> str:
        normalized = normalize_character_name(raw_name)
        if normalized in candidates:
            return normalized
        matched = []
        for name in candidates:
            if normalized == name or normalized in self._candidate_aliases(name):
                matched.append(name)
        if len(matched) == 1:
            return matched[0]
        return normalized

    @staticmethod
    def _infer_target(speaker: str, history: List[Dict[str, Any]], all_chars: List[str]) -> str:
        for item in reversed(history):
            prev_speaker = item.get("speaker", "")
            if prev_speaker and prev_speaker != speaker and prev_speaker in all_chars:
                return prev_speaker
        for candidate in all_chars:
            if candidate != speaker:
                return candidate
        return ""

    def _guard_reply(
        self,
        profile: Dict[str, Any],
        reply: str,
        relation_state: Dict[str, Any],
        target_name: str,
    ) -> str:
        issues = self.reflection.relation_alignment_issues(reply, relation_state)
        checked = self.reflection.detect_ooc(profile, reply)
        if not issues and not checked.is_ooc:
            return reply

        rewritten = self._rewrite_reply(reply, relation_state, target_name)
        issues_after = self.reflection.relation_alignment_issues(rewritten, relation_state)
        checked_after = self.reflection.detect_ooc(profile, rewritten)
        if issues_after or checked_after.is_ooc:
            reasons = issues_after + checked_after.reasons
            return f"{rewritten}(needs_revision: {'; '.join(reasons[:2])})"
        return rewritten

    @staticmethod
    def _rewrite_reply(reply: str, relation_state: Dict[str, Any], target_name: str) -> str:
        target = target_name or "对方"
        hostility = int(relation_state.get("hostility", 0))
        affection = int(relation_state.get("affection", 5))
        ambiguity = int(relation_state.get("ambiguity", 3))
        if hostility >= 7:
            return f"对{target}，我把话说到这里，不必更近一步。"
        if affection >= 8:
            return f"对{target}，我会把语气放缓，把话说明白。"
        if ambiguity >= 7:
            return f"对{target}，我先留一点余地，不把话说死。"
        return f"{reply}（已按对象关系收束）"
