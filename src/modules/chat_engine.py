#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.core.path_provider import PathProvider
from src.core.rulebook import RuleBook
from src.core.llm_client import LLMClient
from src.modules.distillation import NovelDistiller
from src.modules.reflection import ReflectionEngine
from src.modules.speaker import Speaker
from src.utils.file_utils import (
    canonical_aliases,
    ensure_dir,
    load_markdown_data,
    normalize_character_name,
    normalize_relation_key,
    novel_id_from_input,
    safe_filename,
    save_markdown_data,
)


class ChatEngine:
    """Multi-character chat with novel-scoped assets."""

    SYSTEM_SPEAKERS = {"Narrator", "User", "旁白", "用户"}
    ADDRESS_SUFFIXES = ("哥哥", "姐姐", "妹妹", "弟弟", "姑娘", "公子", "爷")

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        llm: Optional[LLMClient] = None,
        reflection: Optional[ReflectionEngine] = None,
        speaker: Optional[Speaker] = None,
        distiller: Optional[NovelDistiller] = None,
        rulebook: Optional[RuleBook] = None,
        path_provider: Optional[PathProvider] = None,
    ):
        self.config = config or Config()
        if (
            llm is None
            or reflection is None
            or speaker is None
            or distiller is None
            or rulebook is None
            or path_provider is None
        ):
            raise ValueError(
                "ChatEngine requires injected llm, reflection, speaker, distiller, rulebook, and path_provider"
            )
        self.path_provider = path_provider
        self.rulebook = rulebook
        self.llm = llm
        self.reflection = reflection
        self.distiller = distiller
        self.speaker = speaker
        self.characters_dir = self.path_provider.characters_root()
        self.sessions_dir = self.path_provider.sessions_dir()
        self.relations_dir = self.path_provider.relations_root()
        self.generation_mode = str(self.config.get("chat_engine.generation_mode", "auto")).strip().lower()
        self.enable_turn_interactions = bool(self.config.get("chat_engine.enable_turn_interactions", True))
        self.allow_character_silence = bool(self.config.get("chat_engine.allow_character_silence", True))
        self.min_reply_relevance = int(self.config.get("chat_engine.min_reply_relevance", 4))
        self.llm_history_messages = int(self.config.get("chat_engine.llm_history_messages", 8))
        self.address_suffixes = tuple(
            getattr(self.distiller, "address_suffixes", ())
            or self.rulebook.get("distillation", "address_suffixes", list(self.ADDRESS_SUFFIXES))
        )

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
                "controlled_character": "",
                "selected_characters": list(characters),
                "relation_delta": {},
                "relation_matrix": self._build_relation_matrix(characters, novel_id),
            },
        }
        self._save_session(session)
        return session

    def restore_session(self, session_id: str) -> Dict[str, Any]:
        path = self.sessions_dir / f"{session_id}.md"
        data = load_markdown_data(path, default=None)
        if not data:
            raise FileNotFoundError(f"Session not found: {session_id}")
        data.setdefault("novel_id", novel_id_from_input(data.get("novel", session_id)))
        data.setdefault("state", {})
        data["state"].setdefault("focus_targets", {})
        data["state"].setdefault("controlled_character", "")
        data["state"].setdefault("selected_characters", list(data.get("characters", [])))
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
        speaker, normalized_msg = self._resolve_observe_turn(session, user_msg)
        responders = self._active_characters(session, speaker=speaker, context=normalized_msg)
        return self._run_turn(session, speaker, normalized_msg, responders)

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
            f"[累计] provider={summary.get('provider', 'unknown')} token={summary['total_tokens']} "
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
        self._persist_runtime_guidance(session, speaker, message)
        self._remember_focus_targets(session, speaker, responders)
        profiles = self._load_character_profiles(session.get("novel_id"))
        ordered_responders = self._plan_turn_sequence(session, speaker, message, responders)

        responses: List[tuple[str, str]] = []
        for name in ordered_responders:
            if self._should_skip_reply(session, speaker, name, message, responses):
                continue
            profile = profiles.get(name, {"name": name})
            target_name = self._resolve_turn_target(session, speaker, name, message, responses)
            relation_state = self._get_relation_state(session, name, target_name)
            reply = self._generate_reply(
                session=session,
                speaker=speaker,
                responder=name,
                profile=profile,
                message=message,
                target_name=target_name,
                relation_state=relation_state,
                prior_responses=responses,
            )
            if not reply:
                continue
            responses.append((name, reply))
            session["history"].append(
                {"speaker": name, "target": target_name, "message": reply, "ts": int(time.time())}
            )

        self._trim_history(session)
        self._update_state(session)
        self._save_session(session)
        return responses

    def _generate_reply(
        self,
        *,
        session: Dict[str, Any],
        speaker: str,
        responder: str,
        profile: Dict[str, Any],
        message: str,
        target_name: str,
        relation_state: Dict[str, Any],
        prior_responses: List[tuple[str, str]],
    ) -> str:
        relation_hint = self._relation_hint(responder, session["characters"], session.get("novel_id"))
        guidance = self.speaker.build_generation_guidance(
            character_profile=profile,
            context=message,
            history=session["history"],
            target_name=target_name,
            relation_state=relation_state,
            relation_hint=relation_hint,
        )
        fallback_reply = str(guidance.get("fallback_reply", "")).strip()

        if not self._should_use_llm_generation():
            return self._finalize_reply(profile, fallback_reply, relation_state, target_name)

        try:
            llm_messages = self._build_llm_messages(
                session=session,
                speaker=speaker,
                responder=responder,
                message=message,
                target_name=target_name,
                guidance=guidance,
                prior_responses=prior_responses,
            )
            llm_output = self.llm.chat_completion(
                llm_messages,
                temperature=float(self.config.get("llm.temperature", 0.2) or 0.2),
                max_tokens=int(self.config.get("llm.max_tokens", 0) or 0) or None,
            )
            candidate = self._sanitize_generated_reply(
                responder,
                str(llm_output.get("content", "")),
                fallback_reply=fallback_reply,
            )
        except Exception:
            candidate = fallback_reply

        final_reply = self._finalize_reply(profile, candidate, relation_state, target_name)
        if final_reply:
            return final_reply
        return self._finalize_reply(profile, fallback_reply, relation_state, target_name)

    def _should_use_llm_generation(self) -> bool:
        if self.generation_mode == "rule-only":
            return False
        if self.generation_mode == "llm-only":
            return True
        return self.llm.is_generation_enabled()

    def _finalize_reply(
        self,
        profile: Dict[str, Any],
        reply: str,
        relation_state: Dict[str, Any],
        target_name: str,
    ) -> str:
        cleaned = self._strip_revision_tag(reply.strip())
        if not cleaned:
            return ""
        guarded = self._guard_reply(profile, cleaned, relation_state, target_name)
        return self._strip_revision_tag(guarded).strip()

    def _plan_turn_sequence(
        self,
        session: Dict[str, Any],
        speaker: str,
        message: str,
        responders: List[str],
    ) -> List[str]:
        if not responders:
            return []
        mentioned = self._mentioned_characters(message, responders)
        ranked = self._rank_characters(session, speaker, responders, preferred=mentioned)
        ordered: List[str] = []
        seen = set()
        for name in mentioned + ranked:
            if name in seen:
                continue
            ordered.append(name)
            seen.add(name)
        return ordered or list(responders)

    def _should_skip_reply(
        self,
        session: Dict[str, Any],
        speaker: str,
        responder: str,
        message: str,
        prior_responses: List[tuple[str, str]],
    ) -> bool:
        if not self.allow_character_silence:
            return False
        if session.get("mode") == "act":
            return False
        if not prior_responses:
            return False
        if responder in self._mentioned_characters(message, [responder]):
            return False
        speaker_score = self._relation_score(session, responder, speaker)
        latest_score = 0
        if prior_responses:
            latest_speaker = prior_responses[-1][0]
            if latest_speaker != responder:
                latest_score = self._relation_score(session, responder, latest_speaker)
        return max(speaker_score, latest_score) < self.min_reply_relevance

    def _resolve_turn_target(
        self,
        session: Dict[str, Any],
        speaker: str,
        responder: str,
        message: str,
        prior_responses: List[tuple[str, str]],
    ) -> str:
        candidates = [name for name in session["characters"] if name != responder]
        mentioned = self._mentioned_characters(message, candidates)
        if mentioned:
            return mentioned[0]
        if self.enable_turn_interactions and prior_responses:
            latest = prior_responses[-1][0]
            if latest != responder:
                return latest
        remembered = self._remembered_target(session, responder, candidates)
        if remembered:
            return remembered
        return self._infer_target(responder, session["history"], session["characters"])

    def _build_llm_messages(
        self,
        *,
        session: Dict[str, Any],
        speaker: str,
        responder: str,
        message: str,
        target_name: str,
        guidance: Dict[str, Any],
        prior_responses: List[tuple[str, str]],
    ) -> List[Dict[str, str]]:
        style_rules = guidance.get("style_rules", [])
        behavior_rules = guidance.get("behavior_rules", [])
        relation_rules = guidance.get("relation_rules", [])
        memory_cues = guidance.get("memory_cues", [])
        corrections = guidance.get("similar_corrections", [])

        system_lines = [
            f"你现在只扮演 {responder}。",
            "你的任务是生成自然、流畅、去模板化的中文角色回应。",
            "只输出该角色此刻会说出的内容，不要解释规则，不要输出字段名。",
            "允许极少量动作或神态描写，但不能抢成旁白大段叙述。",
            "优先遵守人物档案、关系约束、用户纠正、记忆约束。",
            "严禁复读通用 AI 套话、总结腔、万能过渡句。",
            "不要照抄约束草案，要把它转成自然说话。",
        ]
        for section_title, items in (
            ("风格约束", style_rules),
            ("行为约束", behavior_rules),
            ("关系约束", relation_rules),
            ("记忆约束", memory_cues),
        ):
            if not items:
                continue
            system_lines.append(f"{section_title}:")
            system_lines.extend(f"- {item}" for item in items[:8])
        if corrections:
            system_lines.append("历史纠错参考:")
            for item in corrections[:2]:
                corrected = str(item.get("corrected_message", "")).strip()
                reason = str(item.get("reason", "")).strip()
                if corrected:
                    suffix = f" | 原因: {reason}" if reason else ""
                    system_lines.append(f"- 更接近人物的表达: {corrected}{suffix}")
        fallback_reply = str(guidance.get("fallback_reply", "")).strip()
        if fallback_reply:
            system_lines.append(f"约束草案（不要照抄）: {fallback_reply}")

        recent_window = session["history"][-self.llm_history_messages :]
        history_lines = [f"{item.get('speaker', '')}: {item.get('message', '')}" for item in recent_window]
        turn_lines = [f"{speaker}: {message}"]
        if prior_responses:
            turn_lines.extend(f"{name}: {reply}" for name, reply in prior_responses)

        user_lines = [
            f"会话模式: {session.get('mode', 'observe')}",
            f"当前轮发起者: {speaker}",
            f"当前回应角色: {responder}",
            f"当前主要回应对象: {target_name or '未指定'}",
        ]
        if history_lines:
            user_lines.append("最近对话:")
            user_lines.extend(f"- {line}" for line in history_lines)
        user_lines.append("本轮已发生:")
        user_lines.extend(f"- {line}" for line in turn_lines)
        user_lines.append("请输出 1 到 3 句符合人物个性、关系与场景推进的自然回应。")

        return [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": "\n".join(user_lines)},
        ]

    @staticmethod
    def _sanitize_generated_reply(responder: str, content: str, fallback_reply: str = "") -> str:
        text = str(content or "").strip()
        if not text:
            return fallback_reply
        patterns = (
            rf"^\s*{re.escape(responder)}\s*[：:]\s*",
            r"^\s*assistant\s*[：:]\s*",
        )
        for pattern in patterns:
            text = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return fallback_reply
        return "\n".join(lines[:3]).strip()

    @staticmethod
    def _strip_revision_tag(reply: str) -> str:
        return re.sub(r"\s*\(needs_revision:.*?\)\s*$", "", str(reply or "").strip())

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
            self._persist_correction_memory(session, character, target, original, corrected, reason)
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
            scoped = self.path_provider.relations_file(novel_id)
            if scoped.exists():
                return scoped
            legacy = self.relations_dir / f"{novel_id}_relations.md"
            if legacy.exists():
                return legacy
        files = sorted(self.relations_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
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
        save_markdown_data(
            self.sessions_dir / f"{session['id']}.md",
            session,
            title="SESSION",
            summary=[
                f"- id: {session.get('id', '')}",
                f"- novel_id: {session.get('novel_id', '')}",
                f"- mode: {session.get('mode', '')}",
            ],
        )
        self._save_relation_snapshot(session)

    def _persist_runtime_guidance(self, session: Dict[str, Any], speaker: str, message: str) -> None:
        if speaker not in self.SYSTEM_SPEAKERS:
            return
        if not self._looks_like_persistent_guidance(message):
            return
        for character in session.get("characters", []):
            if not self._message_mentions_character(message, character):
                continue
            note = f"用户提示：{message.strip()}"
            self._append_memory_entry(session.get("novel_id"), character, "user_edits", note)

    def _looks_like_persistent_guidance(self, message: str) -> bool:
        durable_tokens = tuple(
            self.rulebook.get(
                "speaker",
                "durable_guidance_tokens",
                ["记住", "设定", "人设", "以后", "别再", "不要再", "改成", "纠正", "必须", "不要", "应该"],
            )
        )
        return any(token in message for token in durable_tokens) and "？" not in message and "?" not in message

    def _message_mentions_character(self, message: str, character: str) -> bool:
        aliases = [character] + self._candidate_aliases(character)
        return any(alias and alias in message for alias in aliases)

    def _persist_correction_memory(
        self,
        session: Dict[str, Any],
        character: str,
        target: str,
        original: str,
        corrected: str,
        reason: str,
    ) -> None:
        note = f"纠正：原句={original}；修正={corrected}；原因={reason or 'inline_command'}"
        self._append_memory_entry(session.get("novel_id"), character, "user_edits", note)
        self._append_memory_entry(session.get("novel_id"), character, "notable_interactions", note)
        if target:
            target_note = f"与{target}相关的纠正：{corrected}"
            self._append_memory_entry(session.get("novel_id"), character, "relationship_updates", target_note)

    def _append_memory_entry(self, novel_id: Optional[str], character: str, field: str, note: str) -> None:
        if not novel_id or not character or not note.strip():
            return
        normalized_name = normalize_character_name(character)
        persona_dir = self.path_provider.character_dir(novel_id, normalized_name)
        memory_file = persona_dir / "MEMORY.md"
        if not memory_file.exists():
            memory_file.write_text(
                "# MEMORY\n\n## Stable Memory\n\n## Mutable Notes\n",
                encoding="utf-8",
            )
        self.distiller.refresh_navigation(persona_dir, normalized_name)
        with memory_file.open("a", encoding="utf-8") as handle:
            handle.write(f"- {field}: {note.strip()}\n")

    def _load_character_profiles(self, novel_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        profiles: Dict[str, Dict[str, Any]] = {}
        if not self.characters_dir.exists():
            return profiles

        if novel_id:
            scoped_dir = self.path_provider.characters_root(novel_id)
            sources = self._collect_profile_sources(scoped_dir)
            if not sources:
                return profiles
        else:
            sources = self._collect_profile_sources(self.characters_dir)
            for novel_dir in sorted(path for path in self.characters_dir.iterdir() if path.is_dir()):
                sources.extend(self._collect_profile_sources(novel_dir))

        for file in sources:
            item = self._load_profile_source(file)
            if item and isinstance(item, dict) and item.get("name"):
                canonical_name = normalize_character_name(item["name"])
                item["name"] = canonical_name
                if file.is_dir():
                    base_dir = file.parent
                elif file.name.startswith("PROFILE"):
                    base_dir = file.parent.parent
                else:
                    base_dir = file.parent
                item = self._merge_persona_bundle(item, base_dir)
                profiles[canonical_name] = self._merge_profile_item(profiles.get(canonical_name), item)
        return profiles

    def _collect_profile_sources(self, root: Path) -> List[Path]:
        if not root.exists():
            return []
        sources: List[Path] = []
        seen = set()
        for persona_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            if any((persona_dir / filename).exists() for filename in ("PROFILE.md", "PROFILE.generated.md")):
                resolved = persona_dir.resolve()
                if resolved not in seen:
                    sources.append(persona_dir)
                    seen.add(resolved)
        return sources

    def _load_profile_source(self, path: Path) -> Optional[Dict[str, Any]]:
        if path.is_dir():
            return self._load_profile_bundle(path)
        if path.name.startswith("PROFILE"):
            return self._load_profile_markdown(path)
        return None

    def _load_profile_bundle(self, persona_dir: Path) -> Optional[Dict[str, Any]]:
        merged: Dict[str, Any] = {}
        loaded = False
        for filename in ("PROFILE.generated.md", "PROFILE.md"):
            path = persona_dir / filename
            if not path.exists():
                continue
            current = self._load_profile_markdown(path)
            if not current:
                continue
            merged = self._merge_profile_markdown_data(merged, current) if loaded else current
            loaded = True
        return merged if loaded else None

    def _load_profile_markdown(self, path: Path) -> Dict[str, Any]:
        parsed = self._parse_persona_markdown(path)
        profile: Dict[str, Any] = {
            "name": parsed.get("name", path.parent.name),
            "novel_id": parsed.get("novel_id", path.parent.parent.name),
            "source_path": parsed.get("source_path", ""),
            "core_traits": self._split_persona_value(parsed.get("core_traits", "")),
            "values": self._split_metric_map(parsed.get("values", "")),
            "speech_style": parsed.get("speech_style", ""),
            "typical_lines": self._split_persona_value(parsed.get("typical_lines", "")),
            "decision_rules": self._split_persona_value(parsed.get("decision_rules", "")),
            "identity_anchor": parsed.get("identity_anchor", ""),
            "soul_goal": parsed.get("soul_goal", ""),
            "life_experience": self._split_persona_value(parsed.get("life_experience", "")),
            "worldview": parsed.get("worldview", ""),
            "thinking_style": parsed.get("thinking_style", ""),
            "core_identity": parsed.get("core_identity", ""),
            "faction_position": parsed.get("faction_position", ""),
            "background_imprint": parsed.get("background_imprint", ""),
            "world_rule_fit": parsed.get("world_rule_fit", ""),
            "social_mode": parsed.get("social_mode", ""),
            "hidden_desire": parsed.get("hidden_desire", ""),
            "inner_conflict": parsed.get("inner_conflict", ""),
            "story_role": parsed.get("story_role", ""),
            "belief_anchor": parsed.get("belief_anchor", ""),
            "private_self": parsed.get("private_self", ""),
            "stance_stability": parsed.get("stance_stability", ""),
            "reward_logic": parsed.get("reward_logic", ""),
            "strengths": self._split_persona_value(parsed.get("strengths", "")),
            "weaknesses": self._split_persona_value(parsed.get("weaknesses", "")),
            "cognitive_limits": self._split_persona_value(parsed.get("cognitive_limits", "")),
            "fear_triggers": self._split_persona_value(parsed.get("fear_triggers", "")),
            "key_bonds": self._split_persona_value(parsed.get("key_bonds", "")),
            "action_style": parsed.get("action_style", ""),
            "speech_habits": {
                "cadence": parsed.get("cadence", ""),
                "signature_phrases": self._split_persona_value(parsed.get("signature_phrases", "")),
                "sentence_openers": self._split_persona_value(parsed.get("sentence_openers", "")),
                "connective_tokens": self._split_persona_value(parsed.get("connective_tokens", "")),
                "sentence_endings": self._split_persona_value(parsed.get("sentence_endings", "")),
                "forbidden_fillers": self._split_persona_value(parsed.get("forbidden_fillers", "")),
            },
            "emotion_profile": {
                "anger_style": parsed.get("anger_style", ""),
                "joy_style": parsed.get("joy_style", ""),
                "grievance_style": parsed.get("grievance_style", ""),
            },
            "taboo_topics": self._split_persona_value(parsed.get("taboo_topics", "")),
            "forbidden_behaviors": self._split_persona_value(parsed.get("forbidden_behaviors", "")),
            "arc": {
                "start": self._split_metric_map(parsed.get("arc_start", "")),
                "mid": self._split_metric_map(parsed.get("arc_mid", "")),
                "end": self._split_metric_map(parsed.get("arc_end", "")),
            },
            "evidence": {
                "description_count": self._safe_int(parsed.get("description_count", 0)),
                "dialogue_count": self._safe_int(parsed.get("dialogue_count", 0)),
                "thought_count": self._safe_int(parsed.get("thought_count", 0)),
                "chunk_count": self._safe_int(parsed.get("chunk_count", 0)),
            },
        }
        return profile

    def _merge_profile_markdown_data(
        self,
        base: Dict[str, Any],
        overlay: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in overlay.items():
            if value in ("", [], {}, None):
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                bucket = dict(merged.get(key, {}))
                for child_key, child_value in value.items():
                    if child_value in ("", [], {}, None):
                        continue
                    bucket[child_key] = child_value
                merged[key] = bucket
                continue
            merged[key] = value
        return merged

    def _merge_persona_bundle(self, profile: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
        merged = dict(profile)
        persona_dir = base_dir / safe_filename(merged.get("name", ""))
        if not persona_dir.exists():
            return merged

        for base_name, source in self._resolve_persona_sources(persona_dir):
            if base_name == "RELATIONS":
                continue
            parsed = self._parse_persona_markdown(source)
            merged = self._apply_persona_overrides(merged, parsed)
        return merged

    def _resolve_persona_sources(self, persona_dir: Path) -> List[tuple[str, Path]]:
        descriptor = self._load_navigation_descriptor(persona_dir)
        order = descriptor.get("runtime", {}).get("load_order", []) or list(NovelDistiller.DEFAULT_NAV_LOAD_ORDER)
        sources: List[tuple[str, Path]] = []
        seen = set()

        for base_name in order:
            normalized = str(base_name or "").strip().upper()
            if not normalized or normalized in seen:
                continue
            meta = descriptor.get("files", {}).get(normalized, {})
            if str(meta.get("status", "")).strip().lower() == "inactive":
                continue
            source = self._resolve_persona_file_path(persona_dir, normalized, meta)
            if not source:
                continue
            sources.append((normalized, source))
            seen.add(normalized)

        for base_name in NovelDistiller.DEFAULT_NAV_LOAD_ORDER:
            if base_name in seen:
                continue
            meta = descriptor.get("files", {}).get(base_name, {})
            if str(meta.get("status", "")).strip().lower() == "inactive":
                continue
            source = self._resolve_persona_file_path(persona_dir, base_name, meta)
            if not source:
                continue
            sources.append((base_name, source))
            seen.add(base_name)

        return sources

    def _resolve_persona_file_path(self, persona_dir: Path, base_name: str, meta: Dict[str, Any]) -> Optional[Path]:
        editable_name = str(meta.get("file", f"{base_name}.md")).strip() or f"{base_name}.md"
        fallback_name = str(meta.get("fallback", f"{base_name}.generated.md")).strip() or f"{base_name}.generated.md"
        editable = persona_dir / editable_name
        if editable.exists():
            return editable
        fallback = persona_dir / fallback_name
        if fallback.exists():
            return fallback
        return None

    def _load_navigation_descriptor(self, persona_dir: Path) -> Dict[str, Any]:
        descriptor = self._default_navigation_descriptor()
        generated = persona_dir / "NAVIGATION.generated.md"
        editable = persona_dir / "NAVIGATION.md"
        for source in (generated, editable):
            if not source.exists():
                continue
            parsed = self._parse_navigation_markdown(source)
            descriptor = self._merge_navigation_descriptor(descriptor, parsed)
        return descriptor

    @staticmethod
    def _default_navigation_descriptor() -> Dict[str, Any]:
        files = {
            base_name: {
                "file": f"{base_name}.md",
                "fallback": f"{base_name}.generated.md",
            }
            for base_name in NovelDistiller.DEFAULT_NAV_LOAD_ORDER
        }
        return {
            "runtime": {"load_order": list(NovelDistiller.DEFAULT_NAV_LOAD_ORDER)},
            "files": files,
        }

    def _merge_navigation_descriptor(
        self,
        base: Dict[str, Any],
        overlay: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = {
            "runtime": dict(base.get("runtime", {})),
            "files": {
                key: dict(value) if isinstance(value, dict) else {}
                for key, value in base.get("files", {}).items()
            },
        }
        runtime_overlay = overlay.get("runtime", {}) if isinstance(overlay.get("runtime", {}), dict) else {}
        if runtime_overlay.get("load_order"):
            merged["runtime"]["load_order"] = self._parse_navigation_order(runtime_overlay["load_order"])
        for key, value in runtime_overlay.items():
            if key == "load_order":
                continue
            merged["runtime"][key] = value
        files_overlay = overlay.get("files", {}) if isinstance(overlay.get("files", {}), dict) else {}
        for base_name, payload in files_overlay.items():
            entry = dict(merged["files"].get(base_name, {}))
            if isinstance(payload, dict):
                entry.update(payload)
            merged["files"][base_name] = entry
        return merged

    @staticmethod
    def _parse_navigation_markdown(path: Path) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {"runtime": {}, "files": {}}
        current_section = ""
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                current_section = line[3:].strip().upper()
                if current_section and current_section != "RUNTIME":
                    parsed["files"].setdefault(current_section, {})
                continue
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip()
            value = value.strip()
            if not value:
                continue
            if current_section == "RUNTIME":
                parsed["runtime"][key] = value
            elif current_section:
                parsed["files"].setdefault(current_section, {})[key] = value
        return parsed

    @staticmethod
    def _parse_navigation_order(value: Any) -> List[str]:
        text = str(value or "").strip()
        if not text:
            return list(NovelDistiller.DEFAULT_NAV_LOAD_ORDER)
        parts = [item.strip().upper() for item in re.split(r"->|,|\|", text) if item.strip()]
        return parts or list(NovelDistiller.DEFAULT_NAV_LOAD_ORDER)

    @staticmethod
    def _parse_persona_markdown(path: Path) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip()
            value = value.strip()
            if not value:
                continue
            if key in parsed and parsed[key]:
                parsed[key] = f"{parsed[key]}；{value}"
            else:
                parsed[key] = value
        return parsed

    def _apply_persona_overrides(self, profile: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(profile)
        list_fields = {
            "core_traits",
            "typical_lines",
            "decision_rules",
            "signature_phrases",
            "sentence_openers",
            "connective_tokens",
            "sentence_endings",
            "forbidden_fillers",
            "taboo_topics",
            "forbidden_behaviors",
            "strengths",
            "weaknesses",
            "cognitive_limits",
            "fear_triggers",
            "key_bonds",
            "user_edits",
            "notable_interactions",
            "relationship_updates",
            "canon_memory",
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
            "identity_anchor",
            "soul_goal",
            "speech_style",
            "thinking_style",
            "worldview",
            "life_experience",
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
        }

        for key, value in parsed.items():
            if not value:
                continue
            if key == "canon_memory":
                merged["life_experience"] = self._split_persona_value(value)
                continue
            if key in dict_targets:
                parent, child = dict_targets[key]
                bucket = dict(merged.get(parent, {})) if isinstance(merged.get(parent, {}), dict) else {}
                bucket[child] = self._split_persona_value(value) if key in list_fields else value
                merged[parent] = bucket
                continue
            if key in direct_fields:
                if key == "life_experience":
                    merged[key] = self._split_persona_value(value)
                else:
                    merged[key] = value
                continue
            if key in list_fields:
                merged[key] = self._split_persona_value(value)
        return merged

    @staticmethod
    def _split_persona_value(value: str) -> List[str]:
        return [item.strip() for item in re.split(r"[；;]\s*", value) if item.strip()]

    @staticmethod
    def _split_metric_map(value: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for item in re.split(r"[；;]\s*", str(value or "").strip()):
            if not item or "=" not in item:
                continue
            key, raw = item.split("=", 1)
            key = key.strip()
            raw = raw.strip()
            if not key:
                continue
            if re.fullmatch(r"-?\d+", raw):
                result[key] = int(raw)
            else:
                result[key] = raw
        return result

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

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
        save_markdown_data(
            self.sessions_dir / f"{session['id']}_relations.md",
            payload,
            title="SESSION_RELATIONS",
            summary=[
                f"- session_id: {session.get('id', '')}",
                f"- novel_id: {session.get('novel_id', '')}",
            ],
        )

    def _get_relation_state_from_disk(
        self,
        speaker: str,
        target: str,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        rel_file = self._relation_file_for_novel(novel_id)
        if not rel_file:
            base = {}
        else:
            payload = load_markdown_data(rel_file, default={}) or {}
            rel = payload.get("relations", {}) if isinstance(payload, dict) else {}
            normalized = {normalize_relation_key(key): value for key, value in rel.items()}
            base = normalized.get(self._pair_key(normalize_character_name(speaker), normalize_character_name(target)), {})
        return self._merge_relation_overlay(base, speaker, target, novel_id)

    def _merge_relation_overlay(
        self,
        relation_state: Dict[str, Any],
        speaker: str,
        target: str,
        novel_id: Optional[str],
    ) -> Dict[str, Any]:
        merged = dict(relation_state or {})
        overlay = self._load_relation_markdown_overlay(speaker, target, novel_id)
        if not overlay:
            return merged
        for key in ("trust", "affection", "power_gap"):
            if key in overlay:
                try:
                    merged[key] = int(overlay[key])
                except (TypeError, ValueError):
                    pass
        for key in ("conflict_point", "typical_interaction"):
            if overlay.get(key):
                merged[key] = overlay[key]
        appellation = overlay.get("appellation_to_target", "")
        if appellation:
            appellations = dict(merged.get("appellations", {})) if isinstance(merged.get("appellations", {}), dict) else {}
            appellations[f"{speaker}->{target}"] = appellation
            merged["appellations"] = appellations
        return merged

    def _load_relation_markdown_overlay(self, speaker: str, target: str, novel_id: Optional[str]) -> Dict[str, str]:
        if not novel_id:
            return {}
        persona_dir = self.path_provider.character_dir(novel_id, normalize_character_name(speaker))
        descriptor = self._load_navigation_descriptor(persona_dir) if persona_dir.exists() else self._default_navigation_descriptor()
        meta = descriptor.get("files", {}).get("RELATIONS", {})
        if str(meta.get("status", "")).strip().lower() == "inactive":
            return {}
        path = self._resolve_persona_file_path(persona_dir, "RELATIONS", meta) if persona_dir.exists() else None
        if not path:
            return {}
        parsed = self._parse_relation_markdown(path)
        target_key = normalize_character_name(target)
        if target_key in parsed:
            return parsed[target_key]
        return {}

    def _parse_relation_markdown(self, path: Path) -> Dict[str, Dict[str, str]]:
        result: Dict[str, Dict[str, str]] = {}
        current_target = ""
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                current_target = normalize_character_name(line[3:].strip())
                result.setdefault(current_target, {})
                continue
            if not current_target or not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            result[current_target][key.strip()] = value.strip()
        return result

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

    def _resolve_observe_turn(self, session: Dict[str, Any], user_msg: str) -> tuple[str, str]:
        message = user_msg.strip()
        if not message:
            return "Narrator", user_msg

        if len(session.get("characters", [])) == 1:
            only_name = session["characters"][0]
            aliases = [only_name] + self._candidate_aliases(only_name)
            for alias in aliases:
                stripped = self._strip_explicit_speaker_prefix(message, alias)
                if stripped != message:
                    return "Narrator", stripped.strip() or message
            return "Narrator", user_msg

        for name in session["characters"]:
            aliases = [name] + self._candidate_aliases(name)
            for alias in aliases:
                stripped = self._strip_explicit_speaker_prefix(message, alias)
                if stripped == message:
                    continue
                normalized = stripped.strip() or message
                return name, normalized
        return "Narrator", user_msg

    @staticmethod
    def _strip_explicit_speaker_prefix(message: str, alias: str) -> str:
        escaped = re.escape(alias)
        patterns = (
            rf"^\s*[“\"'「『]?\s*{escaped}\s*[：:，,]\s*",
            rf"^\s*[“\"'「『]?\s*{escaped}\s*(?:说道|说|道|问道|问|答道|答|曰|开口道|笑道|沉声道|朗声道|轻声道)\s*[：:，,]?\s*",
        )
        for pattern in patterns:
            updated = re.sub(pattern, "", message, count=1)
            if updated != message:
                return updated
        return message

    def _candidate_aliases(self, name: str) -> List[str]:
        clean = normalize_character_name(name)
        if hasattr(self.distiller, "candidate_aliases"):
            return list(self.distiller.candidate_aliases(clean))

        aliases: List[str] = []
        aliases.extend(canonical_aliases(clean))
        if len(clean) >= 3:
            given = clean[-2:]
            if len(given) == 2 and given != clean:
                aliases.append(given)
                for suffix in self.address_suffixes:
                    aliases.append(f"{given[0]}{suffix}")
                    aliases.append(f"{clean[0]}{suffix}")
        elif len(clean) == 2:
            for suffix in self.address_suffixes:
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
