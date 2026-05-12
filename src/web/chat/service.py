from __future__ import annotations

import json
import os
import random
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from src.web.artifacts.ingest import load_profile_source
from src.core.config import Config
from src.core.path_provider import PathProvider
from src.core.session_store import MarkdownSessionStore


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class DialogueService:
    _LEAVE_TOKENS = (
        "离开",
        "离席",
        "退场",
        "告退",
        "先走",
        "退下",
        "走了",
        "离去",
        "回房",
        "回去了",
        "退出",
    )
    _RETURN_TOKENS = (
        "回来",
        "回来了",
        "折返",
        "再入",
        "再至",
        "现身",
        "又到了",
        "入场",
        "进门",
        "重回",
    )

    def __init__(
        self,
        runs_root: str | Path,
        *,
        memory_store_resolver: Callable[[str], MarkdownSessionStore] | None = None,
    ) -> None:
        self.runs_root = Path(runs_root)
        self._memory_store_resolver = memory_store_resolver
        self._memory_stores: dict[str, MarkdownSessionStore] = {}

    def list_sessions(self, run_id: str) -> list[dict[str, Any]]:
        root = self._sessions_root(run_id)
        items: list[dict[str, Any]] = []
        if not root.exists():
            return items
        for path in sorted(root.glob("*/session.json"), reverse=True):
            payload = self._read_json(path)
            items.append(self._serialize_session(run_id, payload))
        items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return items

    def create_session(
        self,
        run_manifest: dict[str, Any],
        *,
        mode: str,
        participants: list[str],
        controlled_character: str = "",
        scene_profile: dict[str, str] | None = None,
        self_profile: dict[str, str] | None = None,
        carried_memory_summary: dict[str, str] | None = None,
        branch_origin: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = str(run_manifest.get("run_id", "")).strip()
        novel_id = str(run_manifest.get("novel_id", "")).strip()
        available = self._character_index(run_manifest)
        available_names = [item["name"] for item in available]
        selected = [name for name in participants if name in available_names]
        if not selected:
            selected = available_names
        if not selected:
            raise ValueError("No persona bundles available for dialogue.")
        if mode not in {"act", "insert", "observe"}:
            raise ValueError("Unsupported dialogue mode.")
        if mode == "act" and controlled_character not in selected:
            raise ValueError("Controlled character must be one of the selected participants.")

        session_id = f"dlg-{uuid4().hex[:10]}"
        root = self._session_dir(run_id, session_id)
        root.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": "zaomeng_dialogue_session",
            "session_id": session_id,
            "run_id": run_id,
            "novel_id": novel_id,
            "mode": mode,
            "participants": selected,
            "controlled_character": controlled_character if mode == "act" else "",
            "scene_card": dict(scene_profile or {}),
            "scene_card_id": str((scene_profile or {}).get("scene_card_id", "")).strip(),
            "scene_history": [],
            "self_insert": dict(self_profile or {}) if mode == "insert" else {},
            "self_card_id": str((self_profile or {}).get("self_card_id", "")).strip() if mode == "insert" else "",
            "carried_memory_summary": dict(carried_memory_summary or {}),
            "branch_origin": dict(branch_origin or {}),
            "history": [],
            "pending_turn": {},
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "status": "ready",
        }
        if dict(scene_profile or {}):
            initial_summary = self._build_session_memory_summary(run_id, payload, [])
            payload["scene_history"] = [
                self._build_scene_history_entry(
                    scene_profile or {},
                    transition_message="",
                    memory_summary=initial_summary,
                )
            ]
        self._write_json(root / "session.json", payload)
        if carried_memory_summary:
            session_store = self._resolve_memory_store(run_id)
            if session_store is not None:
                session_store.append_long_term_memory(
                    session_id,
                    self._branch_memory_seed_text(carried_memory_summary),
                    metadata={
                        "run_id": run_id,
                        "kind": "branch_summary",
                        "speaker": "分支摘要",
                        "target": "",
                        "ts": _utc_now(),
                    },
                )
        return self._serialize_session(run_id, payload)

    def get_session(self, run_id: str, session_id: str) -> dict[str, Any]:
        payload = self._read_json(self._session_file(run_id, session_id))
        return self._serialize_session(run_id, payload)

    def delete_session(self, run_id: str, session_id: str) -> None:
        session_dir = self._session_dir(run_id, session_id)
        if not session_dir.exists():
            raise FileNotFoundError(str(session_dir))
        shutil.rmtree(session_dir)

    def update_scene_card(
        self,
        run_id: str,
        session_id: str,
        *,
        scene_profile: dict[str, str] | None = None,
        transition_message: str = "",
    ) -> dict[str, Any]:
        session = self._read_json(self._session_file(run_id, session_id))
        if session.get("pending_turn"):
            raise ValueError("当前还有一轮待收口，请先等这拍结束再转场。")
        normalized_scene = dict(scene_profile or {})
        session["scene_card"] = normalized_scene
        session["scene_card_id"] = str(normalized_scene.get("scene_card_id", "")).strip()
        scene_note = self._build_scene_switch_note(normalized_scene, transition_message)
        if scene_note:
            session.setdefault("history", []).append(
                {
                    "speaker": "场景提示",
                    "message": scene_note,
                    "target": "",
                    "ts": _utc_now(),
                }
            )
        transcript = self._serialize_transcript(session)
        memory_summary = self._build_session_memory_summary(run_id, session, transcript)
        scene_history = list(session.get("scene_history", []) or [])
        scene_history.append(
            self._build_scene_history_entry(
                normalized_scene,
                transition_message=transition_message,
                memory_summary=memory_summary,
            )
        )
        session["scene_history"] = scene_history
        session["updated_at"] = _utc_now()
        session["status"] = "ready"
        self._write_json(self._session_file(run_id, session_id), session)
        return self._serialize_session(run_id, session)

    def branch_session_from_scene(
        self,
        run_manifest: dict[str, Any],
        session_id: str,
        *,
        scene_index: int,
    ) -> dict[str, Any]:
        run_id = str(run_manifest.get("run_id", "")).strip()
        session = self._read_json(self._session_file(run_id, session_id))
        scene_history = list(session.get("scene_history", []) or [])
        if scene_index < 0 or scene_index >= len(scene_history):
            raise ValueError("指定的场景时间线节点不存在。")
        target = dict(scene_history[scene_index] or {})
        scene_profile = dict(target.get("scene_card", {}) or {})
        if not scene_profile:
            scene_profile = {
                "scene_card_id": str(target.get("scene_card_id", "")).strip(),
                "title": str(target.get("title", "")).strip(),
                "location": str(target.get("location", "")).strip(),
                "atmosphere": str(target.get("atmosphere", "")).strip(),
            }
        memory_summary = dict(target.get("memory_summary", {}) or {})
        return self.create_session(
            run_manifest,
            mode=str(session.get("mode", "observe")).strip() or "observe",
            participants=list(session.get("participants", []) or []),
            controlled_character=str(session.get("controlled_character", "")).strip(),
            scene_profile=scene_profile,
            self_profile=dict(session.get("self_insert", {}) or {}),
            carried_memory_summary=memory_summary,
            branch_origin={
                "session_id": str(session.get("session_id", "")).strip(),
                "scene_index": scene_index,
                "scene_title": str(target.get("title", "")).strip(),
            },
        )

    def prepare_turn(
        self,
        run_manifest: dict[str, Any],
        *,
        session_id: str,
        message: str,
        message_kind: str = "dialogue",
        speaker_override: str = "",
        transcript_message: str | None = None,
    ) -> dict[str, Any]:
        run_id = str(run_manifest.get("run_id", "")).strip()
        session = self._read_json(self._session_file(run_id, session_id))
        normalized_message_kind = self._normalize_message_kind(message_kind)
        effective_speaker_override = str(speaker_override or "").strip()
        if normalized_message_kind == "narration" and not effective_speaker_override:
            effective_speaker_override = "场景提示"
        turn_id = f"turn-{uuid4().hex[:8]}"
        payload = self._build_turn_payload(
            run_manifest,
            session,
            turn_id=turn_id,
            message=message,
            speaker_override=effective_speaker_override,
            message_kind=normalized_message_kind,
        )
        turn_dir = self._session_dir(run_id, session_id) / "turns"
        turn_dir.mkdir(parents=True, exist_ok=True)
        turn_payload_path = turn_dir / f"{turn_id}.payload.json"
        self._write_json(turn_payload_path, payload)
        session["pending_turn"] = {
            "turn_id": turn_id,
            "user_message": message,
            "transcript_message": message if transcript_message is None else transcript_message,
            "message_kind": normalized_message_kind,
            "speaker": payload["input"]["speaker"],
            "mode": payload["mode"],
            "participants": list(payload["input"]["participants"]),
            "active_participants": list(payload["input"].get("active_participants", [])),
            "response_limit_hint": payload["host_action"]["response_limit_hint"],
            "payload_path": str(turn_payload_path.resolve()),
            "created_at": _utc_now(),
        }
        session["updated_at"] = _utc_now()
        session["status"] = "waiting_for_host_reply"
        self._write_json(self._session_file(run_id, session_id), session)
        return self._serialize_session(run_id, session)

    def build_suggestion_payload(
        self,
        run_manifest: dict[str, Any],
        *,
        session_id: str,
        seed_text: str = "",
    ) -> dict[str, Any]:
        run_id = str(run_manifest.get("run_id", "")).strip()
        session = self._read_json(self._session_file(run_id, session_id))
        payload = self._build_turn_payload(
            run_manifest,
            session,
            turn_id=f"suggest-{uuid4().hex[:8]}",
            message=seed_text,
        )
        mode = str(payload.get("mode", "observe")).strip() or "observe"
        speaker = str(payload.get("input", {}).get("speaker", "")).strip()
        participants = list(payload.get("input", {}).get("participants", []))
        payload["kind"] = "zaomeng_dialogue_suggestion"
        payload["user_persona"] = self._build_user_suggestion_persona(mode, session, payload.get("persona_contexts", []))
        payload["instructions"] = {
            "mode": mode,
            "generation_goal": "Draft one short, natural, directly sendable next user line that fits the current scene, relationships, and persona voices.",
            "mode_rule": self._suggestion_mode_rule(mode),
            "speaker_rule": self._speaker_rule(mode, session),
            "response_style": self._suggestion_style_rule(mode),
        }
        payload["host_action"] = {
            "expected_output": {"suggestion": "一句可直接发送的话"},
            "output_rule": "Keep it short, in-scene, directly sendable, and never explanatory.",
        }
        payload["host_prompt_brief"] = self._host_suggestion_prompt_brief(mode, speaker, participants)
        payload["updated_at"] = _utc_now()
        return payload

    def ingest_turn_responses(
        self,
        run_id: str,
        *,
        session_id: str,
        responses: list[dict[str, str]],
        remember_turn_memory: bool = False,
    ) -> dict[str, Any]:
        session = self._read_json(self._session_file(run_id, session_id))
        pending = dict(session.get("pending_turn", {}) or {})
        if not pending:
            raise ValueError("No pending turn to ingest.")
        session_store = self._resolve_memory_store(run_id) if remember_turn_memory else None
        clean_responses = []
        for item in responses:
            speaker = str(item.get("speaker", "")).strip()
            message = str(item.get("message", "")).strip()
            if not speaker or not message:
                continue
            clean_responses.append({"speaker": speaker, "message": message, "ts": _utc_now()})
        if not clean_responses:
            raise ValueError("No valid responses provided.")
        transcript_message = str(pending.get("transcript_message", pending.get("user_message", ""))).strip()
        if transcript_message:
            user_entry = {
                "speaker": pending.get("speaker", "User"),
                "message": transcript_message,
                "target": "",
                "ts": pending.get("created_at", _utc_now()),
            }
            if session_store is not None:
                session_store.append_long_term_memory(
                    session_id,
                    self._entry_to_memory_text(user_entry),
                    metadata={
                        "run_id": run_id,
                        "kind": self._normalize_message_kind(str(pending.get("message_kind", "")).strip()),
                        "speaker": str(user_entry.get("speaker", "")).strip(),
                        "target": "",
                        "ts": user_entry.get("ts", ""),
                    },
                )
                user_entry["memory_archived"] = True
            session.setdefault("history", []).append(user_entry)
        remembered_responses = []
        pending_speaker = str(pending.get("speaker", "")).strip()
        active_participants = [str(item).strip() for item in pending.get("active_participants", []) if str(item).strip()]
        session["history"].extend(clean_responses)
        for item in clean_responses:
            response_entry = item
            if session_store is not None:
                target = pending_speaker if pending_speaker not in {"", "User", "场景提示", "旁白"} else ""
                if not target:
                    pool = [name for name in active_participants if name and name != str(response_entry.get("speaker", "")).strip()]
                    target = pool[0] if pool else ""
                session_store.append_long_term_memory(
                    session_id,
                    self._entry_to_memory_text(response_entry),
                    metadata={
                        "run_id": run_id,
                        "kind": "dialogue",
                        "speaker": str(response_entry.get("speaker", "")).strip(),
                        "target": target,
                        "ts": response_entry.get("ts", ""),
                    },
                )
                response_entry["memory_archived"] = True
            remembered_responses.append(response_entry)
        if remembered_responses:
            session["history"][-len(remembered_responses) :] = remembered_responses
        session["pending_turn"] = {}
        session["updated_at"] = _utc_now()
        session["status"] = "ready"
        if session_store is not None:
            session_store.compress_context(session)
        result_path = self._session_dir(run_id, session_id) / "turns" / f"{pending.get('turn_id', 'turn')}.result.json"
        self._write_json(
            result_path,
            {
                "kind": "zaomeng_dialogue_result",
                "session_id": session_id,
                "turn_id": pending.get("turn_id", ""),
                "responses": clean_responses,
                "updated_at": _utc_now(),
            },
        )
        self._write_json(self._session_file(run_id, session_id), session)
        return self._serialize_session(run_id, session)

    def _build_turn_payload(
        self,
        run_manifest: dict[str, Any],
        session: dict[str, Any],
        *,
        turn_id: str,
        message: str,
        message_kind: str = "dialogue",
        speaker_override: str = "",
    ) -> dict[str, Any]:
        participants = list(session.get("participants", []))
        mode = str(session.get("mode", "observe")).strip() or "observe"
        normalized_message_kind = self._normalize_message_kind(message_kind)
        speaker = str(speaker_override or "").strip() or (
            session.get("controlled_character", "")
            if mode == "act"
            else session.get("self_insert", {}).get("display_name", "你")
            if mode == "insert"
            else "User"
        )
        character_index = self._character_index(run_manifest)
        persona_map = {item["name"]: item for item in character_index}
        relation_graph = dict(run_manifest.get("artifact_index", {}).get("relation_graph", {}) or {})
        full_history = list(session.get("history", []))
        active_participants = self._resolve_active_participants(participants, full_history, mode, speaker)
        scene_card = dict(session.get("scene_card", {}) or {})
        transcript = self._serialize_transcript(session)

        persona_contexts = self._build_persona_contexts(
            participants=participants,
            active_participants=active_participants,
            persona_map=persona_map,
            mode=mode,
            controlled_character=str(session.get("controlled_character", "")).strip(),
        )

        latest_history = full_history[-8:]
        relation_excerpt = self._build_relation_excerpt(
            relation_graph.get("relations_file", ""),
            participants=participants,
            active_participants=active_participants,
            message=message,
            scene_card=scene_card,
        )
        memory_context = self._build_turn_memory_context(
            run_id=str(run_manifest.get("run_id", "")).strip(),
            session=session,
            transcript=transcript,
            speaker=speaker,
            message=message,
            participants=participants,
            active_participants=active_participants,
            scene_card=scene_card,
        )
        response_limit_hint = self._choose_response_limit_hint(
            mode=mode,
            active_count=len(active_participants),
            turn_id=turn_id,
            message_kind=normalized_message_kind,
        )
        instructions = {
            "mode": mode,
            "generation_goal": "Keep every reply faithful to the persona bundle, relationship context, and scene mode.",
            "mode_rule": self._mode_rule(mode),
            "speaker_rule": self._speaker_rule(mode, session, normalized_message_kind),
            "response_style": self._response_style_rule(mode, normalized_message_kind),
            "scene_rule": self._scene_rule(scene_card),
            "response_count_rule": (
                f"Return 1-{response_limit_hint} in-world replies. "
                "Let only characters who are currently present respond; do not force every participant to speak each turn."
            ),
        }
        responder_hints = self._responder_hints(mode, active_participants, speaker)

        return {
            "kind": "zaomeng_dialogue_turn",
            "run_id": run_manifest.get("run_id", ""),
            "session_id": session.get("session_id", ""),
            "turn_id": turn_id,
            "novel_id": run_manifest.get("novel_id", ""),
            "mode": mode,
            "input": {
                "speaker": speaker,
                "message": message,
                "message_kind": normalized_message_kind,
                "participants": participants,
                "active_participants": active_participants,
                "controlled_character": session.get("controlled_character", ""),
                "scene_card": scene_card,
                "self_insert": dict(session.get("self_insert", {})),
            },
            "history": latest_history,
            "scene_card": scene_card,
            "memory_context": memory_context,
            "persona_contexts": persona_contexts,
            "relation_context": {
                "graph": relation_graph,
                "relations_excerpt": relation_excerpt,
            },
            "instructions": instructions,
            "responder_hints": responder_hints,
            "host_action": {
                "expected_output": [
                    {"speaker": "CharacterName", "message": "..."}
                ],
                "response_limit_hint": response_limit_hint,
                "output_rule": "Return only in-world character replies. Do not explain the workflow or mention prompts.",
            },
            "host_prompt_brief": self._host_prompt_brief(mode, speaker, participants),
            "updated_at": _utc_now(),
        }

    @staticmethod
    def _mode_rule(mode: str) -> str:
        if mode == "act":
            return "The user is speaking as one existing character. Other characters should reply to that role naturally."
        if mode == "insert":
            return "The user enters the scene as themselves. Characters should react to the self-insert identity consistently."
        return "The user is observing. Characters should continue the scene among themselves."

    @staticmethod
    def _speaker_rule(mode: str, session: dict[str, Any], message_kind: str = "dialogue") -> str:
        if message_kind == "narration":
            return "Treat the user message as an in-world scene cue or director beat, not as a cast member's spoken line."
        if mode == "act":
            return f"Treat the user message as spoken by {session.get('controlled_character', '')}."
        if mode == "insert":
            card = session.get("self_insert", {})
            return (
                f"Treat the user message as spoken by {card.get('display_name', '你')} "
                f"who enters the scene as {card.get('scene_identity', card.get('core_identity', '访客'))}."
            )
        return "Treat the user message as a scene steering hint. Characters reply in-world."

    @staticmethod
    def _response_style_rule(mode: str, message_kind: str = "dialogue") -> str:
        if message_kind == "narration":
            return (
                "The cue is scene-driving. Let the cast react with concrete action/emotion changes; "
                "you may include one short 场景提示 or 旁白 line when needed."
            )
        if mode == "observe":
            return "Prefer 2-4 short in-character replies when the scene is busy, and fewer when it is quiet."
        if mode == "act":
            return "Reply as the other characters addressing the controlled role directly."
        return "Reply as the cast addressing the self-insert user naturally inside the scene."

    @staticmethod
    def _scene_rule(scene_card: dict[str, Any]) -> str:
        if not scene_card:
            return "If no explicit scene card is provided, infer a natural continuation from the recent transcript and relation context."
        details = [
            f"location={str(scene_card.get('location', '')).strip()}",
            f"atmosphere={str(scene_card.get('atmosphere', '')).strip()}",
            f"opening_situation={str(scene_card.get('opening_situation', '')).strip()}",
            f"public_goal={str(scene_card.get('public_goal', '')).strip()}",
            f"hidden_tension={str(scene_card.get('hidden_tension', '')).strip()}",
            f"scene_drive={str(scene_card.get('scene_drive', '')).strip()}",
            f"expected_rhythm={str(scene_card.get('expected_rhythm', '')).strip()}",
        ]
        compact = " | ".join(part for part in details if not part.endswith("="))
        if not compact:
            compact = "keep replies anchored in the chosen scene framing"
        return f"Keep the scene anchored to the selected scene card: {compact}."

    @staticmethod
    def _suggestion_mode_rule(mode: str) -> str:
        if mode == "act":
            return "Draft the user's next line as the controlled character, fully in character."
        if mode == "insert":
            return "Draft the user's next line as the self-insert identity inside the scene."
        return "Draft the user's next line as a short scene-steering utterance that introduces movement, tension, reaction, interruption, or new information; not a character reply."

    @staticmethod
    def _suggestion_style_rule(mode: str) -> str:
        if mode == "observe":
            return "Prefer one short scene-driving prompt that pushes the plot forward immediately, such as a new beat, interruption, reveal, gesture, or emotional turn, with no explanation attached."
        if mode == "act":
            return "Prefer one concise in-character line that another participant can answer naturally, as final sendable wording."
        return "Prefer one concise line that sounds like the self-insert user speaking naturally in the scene, as final sendable wording."

    @staticmethod
    def _build_user_suggestion_persona(
        mode: str,
        session: dict[str, Any],
        persona_contexts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        scene_card = dict(session.get("scene_card", {}) or {})
        if mode == "act":
            controlled = str(session.get("controlled_character", "")).strip()
            matched = next(
                (item for item in persona_contexts if str(item.get("name", "")).strip() == controlled),
                {},
            )
            return {
                "mode": "act",
                "speaker": controlled,
                "source": "controlled_character_persona",
                "must_follow": "Write exactly as this controlled character would speak in the current scene.",
                "profile": dict(matched.get("profile", {}) or {}),
                "preview": dict(matched.get("preview", {}) or {}),
                "scene_card": scene_card,
            }
        if mode == "insert":
            card = dict(session.get("self_insert", {}) or {})
            return {
                "mode": "insert",
                "speaker": str(card.get("display_name", "")).strip() or "你",
                "source": "self_insert_profile",
                "must_follow": "Write as the self-insert user, keeping their full role card, identity, motives, and speaking flavor consistent.",
                "profile": dict(card),
                "scene_card": scene_card,
            }
        return {
            "mode": "observe",
            "speaker": "User",
            "source": "observer_hint",
            "must_follow": "Write as a scene observer giving a short in-world nudge that actively moves the scene, rather than speaking as a cast member.",
            "profile": {
                "goal": "push_plot_forward",
                "preferred_moves": [
                    "introduce a new action",
                    "add a small interruption",
                    "surface a hidden tension",
                    "shift the emotional temperature",
                    "make someone notice something important",
                ],
            },
            "scene_card": scene_card,
        }

    @staticmethod
    def _responder_hints(mode: str, participants: list[str], speaker: str) -> list[dict[str, str]]:
        hints: list[dict[str, str]] = []
        for name in participants:
            if mode == "act" and name == speaker:
                continue
            hints.append(
                {
                    "name": name,
                    "should_reply": "yes",
                    "priority": "high" if len(hints) == 0 else "normal",
                }
            )
        return hints

    @staticmethod
    def _host_prompt_brief(mode: str, speaker: str, participants: list[str]) -> str:
        if mode == "act":
            return f"The user speaks as {speaker}. Let the other participants answer in character."
        if mode == "insert":
            return f"The user enters the scene as {speaker}. Let the cast react in character."
        return f"The user is observing. Let {', '.join(participants)} continue the scene in character and keep the chosen scene moving."

    @staticmethod
    def _host_suggestion_prompt_brief(mode: str, speaker: str, participants: list[str]) -> str:
        if mode == "act":
            return f"Help the user speak as {speaker} with one believable next line."
        if mode == "insert":
            return f"Help the user speak as {speaker} inside the current scene with one natural next line."
        return f"Help the user guide {', '.join(participants)} with one short prompt that clearly pushes the scene into its next beat."

    @staticmethod
    def _normalize_message_kind(message_kind: str) -> str:
        kind = str(message_kind or "").strip().lower()
        if kind in {"narration", "scene", "scene_prompt", "director"}:
            return "narration"
        return "dialogue"

    @classmethod
    def _resolve_active_participants(
        cls,
        participants: list[str],
        history: list[dict[str, Any]],
        mode: str,
        speaker: str,
    ) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for name in participants:
            normalized = str(name or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        if not deduped:
            return []

        departed = cls._infer_departed_participants(deduped, history)
        active = [name for name in deduped if name not in departed]
        if mode == "act":
            active = [name for name in active if name != speaker]
        if active:
            return active
        # Never end up with an empty speaker pool.
        fallback = [name for name in deduped if not (mode == "act" and name == speaker)]
        return fallback or deduped[:1]

    @classmethod
    def _infer_departed_participants(cls, participants: list[str], history: list[dict[str, Any]]) -> set[str]:
        departed: set[str] = set()
        recent = list(history or [])[-16:]
        for entry in recent:
            speaker = str(entry.get("speaker", "")).strip()
            message = str(entry.get("message", "")).strip()
            if not message:
                continue
            for name in participants:
                if name not in message:
                    continue
                if cls._contains_return_signal(message, name):
                    departed.discard(name)
                    continue
                if cls._contains_leave_signal(message, name):
                    departed.add(name)
            # If the character themselves says they are leaving, treat as departed.
            if speaker in participants and cls._self_exit_signal(message):
                departed.add(speaker)
        return departed

    @classmethod
    def _contains_leave_signal(cls, text: str, name: str) -> bool:
        compact = re.sub(r"\s+", "", str(text or ""))
        for token in cls._LEAVE_TOKENS:
            if f"{name}{token}" in compact or f"{token}{name}" in compact:
                return True
        return False

    @classmethod
    def _contains_return_signal(cls, text: str, name: str) -> bool:
        compact = re.sub(r"\s+", "", str(text or ""))
        for token in cls._RETURN_TOKENS:
            if f"{name}{token}" in compact or f"{token}{name}" in compact:
                return True
        return False

    @classmethod
    def _self_exit_signal(cls, text: str) -> bool:
        compact = re.sub(r"\s+", "", str(text or ""))
        return any(token in compact for token in ("我先走", "我先告退", "我先退下", "我先回房", "我先离开", "容我告退"))

    @staticmethod
    def _choose_response_limit_hint(*, mode: str, active_count: int, turn_id: str, message_kind: str) -> int:
        if active_count <= 0:
            return 1
        seed = sum(ord(ch) for ch in str(turn_id or ""))
        rng = random.Random(seed)
        if mode == "observe":
            upper = min(4, max(2, active_count))
            lower = 3 if active_count >= 4 else 2
            if message_kind == "narration":
                upper = min(5, max(upper, 3))
                lower = min(upper, 2 if active_count <= 2 else 3)
            return rng.randint(lower, upper)
        upper = min(3, max(1, active_count))
        lower = 1 if active_count <= 1 else 2
        return rng.randint(lower, upper)

    @staticmethod
    def _load_text_excerpt(path_text: str, *, limit: int) -> str:
        path = Path(str(path_text or ""))
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")[:limit].strip()

    def _build_persona_contexts(
        self,
        *,
        participants: list[str],
        active_participants: list[str],
        persona_map: dict[str, dict[str, Any]],
        mode: str,
        controlled_character: str,
    ) -> list[dict[str, Any]]:
        detailed_names: list[str] = []
        for name in active_participants:
            normalized = str(name).strip()
            if normalized and normalized not in detailed_names:
                detailed_names.append(normalized)
        if mode == "act" and controlled_character and controlled_character not in detailed_names:
            detailed_names.append(controlled_character)
        detailed_budget = 4 if mode == "observe" else 3
        detailed_set = set(detailed_names[:detailed_budget])

        ordered_names = [name for name in participants if name in detailed_set] + [
            name for name in participants if name not in detailed_set
        ]
        contexts: list[dict[str, Any]] = []
        for name in ordered_names:
            normalized_name = str(name).strip()
            if not normalized_name:
                continue
            meta = persona_map.get(normalized_name, {})
            normalized_profile, profile_path = self._load_persona_profile(meta)
            is_detailed = normalized_name in detailed_set
            contexts.append(
                {
                    "name": normalized_name,
                    "profile_file": str(profile_path.resolve()) if profile_path.exists() else "",
                    "persona_dir": str(meta.get("persona_dir", "")),
                    "preview": self._persona_preview_payload(meta, normalized_profile),
                    "profile": self._persona_profile_payload(normalized_profile, detailed=is_detailed),
                    "detail_level": "full" if is_detailed else "compact",
                    "is_active": normalized_name in set(active_participants),
                }
            )
        return contexts

    @staticmethod
    def _load_persona_profile(meta: dict[str, Any]) -> tuple[dict[str, Any], Path]:
        profile_path = Path(str(meta.get("profile_file", "")))
        normalized: dict[str, Any] = {}
        if profile_path.exists():
            normalized = load_profile_source(profile_path)
        return normalized, profile_path

    @staticmethod
    def _persona_preview_payload(meta: dict[str, Any], normalized_profile: dict[str, Any]) -> dict[str, Any]:
        preview = dict(meta.get("preview", {}) or {})
        return {
            "display_name": str(preview.get("display_name", "")).strip() or str(normalized_profile.get("display_name", "")).strip(),
            "core_identity": str(preview.get("core_identity", "")).strip() or str(normalized_profile.get("core_identity", "")).strip(),
            "speech_style": str(preview.get("speech_style", "")).strip() or str(normalized_profile.get("speech_style", "")).strip(),
        }

    @staticmethod
    def _persona_profile_payload(normalized_profile: dict[str, Any], *, detailed: bool) -> dict[str, Any]:
        base = {
            "core_identity": normalized_profile.get("core_identity", ""),
            "story_role": normalized_profile.get("story_role", ""),
            "speech_style": normalized_profile.get("speech_style", ""),
            "temperament_type": normalized_profile.get("temperament_type", ""),
            "stress_response": normalized_profile.get("stress_response", ""),
            "key_bonds": normalized_profile.get("key_bonds", []),
        }
        if detailed:
            base.update(
                {
                    "soul_goal": normalized_profile.get("soul_goal", ""),
                    "social_mode": normalized_profile.get("social_mode", ""),
                    "reward_logic": normalized_profile.get("reward_logic", ""),
                }
            )
        return base

    def _build_relation_excerpt(
        self,
        path_text: str,
        *,
        participants: list[str],
        active_participants: list[str],
        message: str,
        scene_card: dict[str, Any],
    ) -> str:
        raw_excerpt = self._load_text_excerpt(
            path_text,
            limit=self._choose_relation_excerpt_scan_limit(participants=participants, active_participants=active_participants),
        )
        if not raw_excerpt:
            return ""
        excerpt_limit = self._choose_relation_excerpt_limit(participants=participants, active_participants=active_participants)
        if len(raw_excerpt) <= excerpt_limit:
            return raw_excerpt

        focus_terms: list[str] = []
        for item in [*active_participants, *participants]:
            normalized = str(item).strip()
            if normalized and normalized not in focus_terms:
                focus_terms.append(normalized)
        for item in (
            str(scene_card.get("title", "")).strip(),
            str(scene_card.get("location", "")).strip(),
            str(scene_card.get("scene_drive", "")).strip(),
        ):
            if item and item not in focus_terms:
                focus_terms.append(item)
        trimmed_message = self._trim_summary_text(message, 48)
        if trimmed_message:
            focus_terms.append(trimmed_message)

        relevant = self._extract_relevant_relation_excerpt(raw_excerpt, focus_terms, excerpt_limit)
        if relevant:
            return relevant
        return self._trim_summary_text(raw_excerpt, excerpt_limit)

    @staticmethod
    def _choose_relation_excerpt_limit(*, participants: list[str], active_participants: list[str]) -> int:
        active_count = max(1, len([item for item in active_participants if str(item).strip()]))
        participant_count = max(active_count, len([item for item in participants if str(item).strip()]))
        return min(3200, 1200 + active_count * 500 + max(0, participant_count - active_count) * 180)

    @staticmethod
    def _choose_relation_excerpt_scan_limit(*, participants: list[str], active_participants: list[str]) -> int:
        return min(8000, DialogueService._choose_relation_excerpt_limit(participants=participants, active_participants=active_participants) * 2)

    def _extract_relevant_relation_excerpt(self, text: str, focus_terms: list[str], limit: int) -> str:
        cleaned_terms = [term for term in (str(item).strip() for item in focus_terms) if len(term) >= 2]
        if not cleaned_terms:
            return ""

        lines = [line.strip() for line in str(text or "").splitlines()]
        kept: list[str] = []
        seen: set[str] = set()
        for index, line in enumerate(lines):
            if not line:
                continue
            if not any(term in line for term in cleaned_terms):
                continue
            for neighbor in range(max(0, index - 1), min(len(lines), index + 2)):
                candidate = lines[neighbor].strip()
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                kept.append(candidate)
                joined = "\n".join(kept)
                if len(joined) >= limit:
                    return self._trim_summary_text(joined, limit)
        if kept:
            return self._trim_summary_text("\n".join(kept), limit)
        return ""

    def _build_turn_memory_context(
        self,
        *,
        run_id: str,
        session: dict[str, Any],
        transcript: list[dict[str, Any]],
        speaker: str,
        message: str,
        participants: list[str],
        active_participants: list[str],
        scene_card: dict[str, Any],
    ) -> dict[str, Any]:
        state_summary = dict(session.get("state", {}).get("memory_summary", {}) or {})
        archived_summary = {
            "summary": self._trim_summary_text(str(state_summary.get("summary", "")).strip(), 360),
            "key_points": [
                self._trim_summary_text(str(item).strip(), 120)
                for item in list(state_summary.get("key_points", []) or [])[:5]
                if str(item).strip()
            ],
            "compressed_turns": int(state_summary.get("compressed_turns", 0) or 0),
            "recent_turns_kept": int(state_summary.get("recent_turns_kept", 0) or 0),
        }
        archived_summary = {
            key: value
            for key, value in archived_summary.items()
            if value not in ("", [], 0)
        }
        memory_hits = self._search_turn_memory_hits(
            run_id=run_id,
            session_id=str(session.get("session_id", "")).strip(),
            speaker=speaker,
            message=message,
            participants=participants,
            active_participants=active_participants,
            scene_card=scene_card,
        )
        return {
            "session_summary": self._build_session_memory_summary(run_id, session, transcript),
            "archived_summary": archived_summary,
            "retrieved_memories": memory_hits,
        }

    def _search_turn_memory_hits(
        self,
        *,
        run_id: str,
        session_id: str,
        speaker: str,
        message: str,
        participants: list[str],
        active_participants: list[str],
        scene_card: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not session_id:
            return []
        store = self._resolve_memory_store(run_id)
        if store is None:
            return []
        query_parts: list[str] = []
        for item in [speaker, *active_participants[:3], *participants[:2]]:
            normalized = str(item).strip()
            if normalized and normalized not in query_parts:
                query_parts.append(normalized)
        for item in (
            str(scene_card.get("title", "")).strip(),
            str(scene_card.get("location", "")).strip(),
            str(scene_card.get("scene_drive", "")).strip(),
        ):
            if item and item not in query_parts:
                query_parts.append(item)
        trimmed_message = self._trim_summary_text(message, 80)
        if trimmed_message:
            query_parts.append(trimmed_message)
        if not query_parts:
            return []
        try:
            hits = store.search_long_term_memory(session_id, " ".join(query_parts), top_k=3)
        except Exception:
            return []
        normalized_hits: list[dict[str, Any]] = []
        for item in hits:
            text = self._trim_summary_text(str((item or {}).get("text", "")).strip(), 140)
            if not text:
                continue
            normalized_hit = {
                "text": text,
                "score": round(float(item.get("score", 0.0) or 0.0), 4),
                "speaker": str(item.get("speaker", "")).strip(),
                "target": str(item.get("target", "")).strip(),
                "kind": str(item.get("kind", "")).strip(),
            }
            normalized_hits.append(
                {
                    key: value
                    for key, value in normalized_hit.items()
                    if value not in ("", 0.0)
                }
            )
        return normalized_hits

    @staticmethod
    def _character_index(run_manifest: dict[str, Any]) -> list[dict[str, Any]]:
        return list(run_manifest.get("artifact_index", {}).get("characters", []) or [])

    def _serialize_session(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = dict(payload)
        session["file_urls"] = self._build_file_urls(run_id, session)
        session["mode_display"] = self._mode_display(str(session.get("mode", "")).strip())
        transcript = self._serialize_transcript(session)
        session["transcript"] = transcript
        session["last_entry_preview"] = self._build_last_entry_preview(session)
        session["session_card"] = self._build_session_card(session)
        session["scene_history"] = self._serialize_scene_history(session)
        session["branch_origin"] = dict(session.get("branch_origin", {}) or {})
        session["pending_turn_summary"] = self._build_pending_turn_summary(session)
        session["session_memory_summary"] = self._build_session_memory_summary(run_id, session, transcript)
        return session

    def _serialize_transcript(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        controlled = str(session.get("controlled_character", "")).strip()
        self_insert_name = str(session.get("self_insert", {}).get("display_name", "")).strip()
        mode = str(session.get("mode", "observe")).strip() or "observe"
        items: list[dict[str, Any]] = []
        for entry in session.get("history", []):
            speaker = str(entry.get("speaker", "")).strip()
            role = "character"
            if speaker in {"旁白", "场景提示"}:
                role = "director" if mode == "observe" else "scene"
            elif mode == "act" and speaker == controlled:
                role = "user"
            elif mode == "insert" and speaker == self_insert_name:
                role = "user"
            elif mode == "observe" and speaker == "User":
                role = "director"
            items.append(
                {
                    "speaker": speaker,
                    "message": str(entry.get("message", "")).strip(),
                    "role": role,
                }
            )
        return items

    @staticmethod
    def _mode_display(mode: str) -> str:
        mapping = {
            "act": "act · 代入角色",
            "insert": "insert · 你进入场景",
            "observe": "observe · 旁观群聊",
        }
        return mapping.get(mode, mode)

    def _build_session_card(self, session: dict[str, Any]) -> dict[str, Any]:
        mode = str(session.get("mode", "observe")).strip() or "observe"
        card = {
            "mode": mode,
            "mode_display": self._mode_display(mode),
            "participants": list(session.get("participants", [])),
            "controlled_character": str(session.get("controlled_character", "")).strip(),
            "scene_card_id": str(session.get("scene_card_id", "")).strip(),
            "scene_card": dict(session.get("scene_card", {})),
            "self_card_id": str(session.get("self_card_id", "")).strip(),
            "self_insert": dict(session.get("self_insert", {})),
        }
        return card

    def _serialize_scene_history(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        current_scene_id = str(session.get("scene_card_id", "")).strip()
        for entry in list(session.get("scene_history", []) or []):
            title = str(entry.get("title", "")).strip()
            location = str(entry.get("location", "")).strip()
            atmosphere = str(entry.get("atmosphere", "")).strip()
            transition_message = str(entry.get("transition_message", "")).strip()
            scene_card_id = str(entry.get("scene_card_id", "")).strip()
            items.append(
                {
                    "scene_card_id": scene_card_id,
                    "title": title,
                    "location": location,
                    "atmosphere": atmosphere,
                    "transition_message": transition_message,
                    "scene_card": dict(entry.get("scene_card", {}) or {}),
                    "memory_summary": dict(entry.get("memory_summary", {}) or {}),
                    "ts": str(entry.get("ts", "")).strip(),
                    "is_current": "true" if current_scene_id and scene_card_id == current_scene_id else "",
                }
            )
        return items

    @staticmethod
    def _build_scene_history_entry(
        scene_profile: dict[str, Any],
        *,
        transition_message: str = "",
        memory_summary: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        scene = dict(scene_profile or {})
        return {
            "scene_card_id": str(scene.get("scene_card_id", "")).strip(),
            "title": str(scene.get("title", "")).strip(),
            "location": str(scene.get("location", "")).strip(),
            "atmosphere": str(scene.get("atmosphere", "")).strip(),
            "transition_message": str(transition_message or "").strip(),
            "scene_card": dict(scene),
            "memory_summary": dict(memory_summary or {}),
            "ts": _utc_now(),
        }

    def _build_pending_turn_summary(self, session: dict[str, Any]) -> dict[str, Any]:
        pending = dict(session.get("pending_turn", {}) or {})
        if not pending:
            return {}
        return {
            "turn_id": str(pending.get("turn_id", "")).strip(),
            "speaker": str(pending.get("speaker", "")).strip(),
            "message": str(pending.get("user_message", "")).strip(),
            "message_kind": self._normalize_message_kind(str(pending.get("message_kind", "")).strip()),
            "mode": str(pending.get("mode", "")).strip(),
            "participants": list(pending.get("participants", [])),
            "active_participants": list(pending.get("active_participants", [])),
            "response_limit_hint": int(pending.get("response_limit_hint", 0) or 0),
        }

    def _build_session_memory_summary(self, run_id: str, session: dict[str, Any], transcript: list[dict[str, Any]]) -> dict[str, str]:
        mode = str(session.get("mode", "observe")).strip() or "observe"
        mode_display = self._mode_display(mode)
        participants = [str(item).strip() for item in session.get("participants", []) if str(item).strip()]
        history = list(session.get("history", []) or [])

        cast_speakers: list[str] = []
        seen: set[str] = set()
        for item in transcript:
            if str(item.get("role", "")).strip() != "character":
                continue
            speaker = str(item.get("speaker", "")).strip()
            if not speaker or speaker in seen:
                continue
            seen.add(speaker)
            cast_speakers.append(speaker)

        last_messages: list[str] = []
        for item in history[-6:]:
            text = str(item.get("message", "")).strip()
            if not text:
                continue
            last_messages.append(self._trim_summary_text(text, 88))
        last_messages = last_messages[-3:]

        recap = "这局刚开场，回顾会在这里滚动更新。"
        if last_messages:
            recap = f"最近一拍：{' / '.join(last_messages)}"

        cast = "人物发言次序会在这里收住。"
        if cast_speakers:
            suffix = "..." if len(cast_speakers) > 5 else ""
            cast = f"当前主要在场：{'、'.join(cast_speakers[:5])}{suffix}"
        elif participants:
            cast = f"本局参与角色：{'、'.join(participants[:5])}{'...' if len(participants) > 5 else ''}"

        if mode == "act":
            controlled = str(session.get("controlled_character", "")).strip() or "该角色"
            perspective = f"你正以「{controlled}」发言，其他人会按角色关系回应。"
        elif mode == "insert":
            self_insert = dict(session.get("self_insert", {}) or {})
            self_name = str(self_insert.get("display_name", "")).strip() or "你"
            identity = str(self_insert.get("scene_identity", "")).strip()
            perspective = f"你以「{self_name}」入场（{identity}）。" if identity else f"你以「{self_name}」入场，直接参与这幕。"
        else:
            perspective = "你在旁观推进模式里，主要作用是推动局势进入下一拍。"
        scene_card = dict(session.get("scene_card", {}) or {})
        if scene_card:
            location = str(scene_card.get("location", "")).strip()
            atmosphere = str(scene_card.get("atmosphere", "")).strip()
            title = str(scene_card.get("title", "")).strip()
            scene_bits = [bit for bit in (title, location, atmosphere) if bit]
            if scene_bits:
                perspective = f"{perspective} 当前挂载场景：{' / '.join(scene_bits)}。"

        world = "当前局势里的动作与情绪线会在这里提醒你。"
        for item in reversed(transcript):
            role = str(item.get("role", "")).strip()
            text = str(item.get("message", "")).strip()
            if not text:
                continue
            if role in {"scene", "director"}:
                world = self._trim_summary_text(text, 88)
                break
        if world == "当前局势里的动作与情绪线会在这里提醒你。":
            for item in reversed(transcript):
                role = str(item.get("role", "")).strip()
                text = str(item.get("message", "")).strip()
                if role == "character" and text:
                    world = f"人物最新情绪线：{self._trim_summary_text(text, 78)}"
                    break

        relation = "关系线还在铺，先让人物多接几拍。"
        recent_character_speakers: list[str] = []
        for item in transcript[-10:]:
            if str(item.get("role", "")).strip() != "character":
                continue
            speaker = str(item.get("speaker", "")).strip()
            if speaker:
                recent_character_speakers.append(speaker)
        if len(recent_character_speakers) >= 2:
            chain = " → ".join(recent_character_speakers[-4:])
            relation = f"最近接话链：{chain}"
        elif cast_speakers:
            relation = f"本局关键人物：{'、'.join(cast_speakers[:4])}"

        session_id = str(session.get("session_id", "")).strip()
        semantic_hint = ""
        if session_id and self._ensure_memory_store(run_id):
            try:
                hits = self._memory_stores[run_id].search_long_term_memory(session_id, "关系 冲突 目标", top_k=1)
            except Exception:
                hits = []
            if hits:
                semantic_hint = str((hits[0] or {}).get("text", "")).strip()
        if semantic_hint:
            relation = f"{relation} · 长期记忆：{self._trim_summary_text(semantic_hint, 68)}"

        carried_summary = dict(session.get("carried_memory_summary", {}) or {})
        if carried_summary and not history:
            carried_recap = str(carried_summary.get("recap", "")).strip()
            carried_cast = str(carried_summary.get("cast", "")).strip()
            carried_relation = str(carried_summary.get("relation_drift", "") or carried_summary.get("relation", "")).strip()
            carried_world = str(carried_summary.get("world", "")).strip()
            if carried_recap:
                recap = f"承接旧线：{self._trim_summary_text(carried_recap, 88)}"
            if carried_cast:
                cast = self._trim_summary_text(carried_cast, 88)
            if carried_relation:
                relation = self._trim_summary_text(carried_relation, 88)
            if carried_world:
                world = self._trim_summary_text(carried_world, 88)

        scene_frame = "当前这幕的地点、气氛与推进方向会在这里提醒你。"
        scene_card = dict(session.get("scene_card", {}) or {})
        if scene_card:
            scene_bits = [
                str(scene_card.get("title", "")).strip(),
                str(scene_card.get("location", "")).strip(),
                str(scene_card.get("atmosphere", "")).strip(),
            ]
            scene_bits = [bit for bit in scene_bits if bit]
            drive = self._trim_summary_text(
                str(scene_card.get("scene_drive", "")).strip() or str(scene_card.get("opening_situation", "")).strip(),
                72,
            )
            if scene_bits:
                scene_frame = f"挂载场景：{' / '.join(scene_bits)}"
                if drive:
                    scene_frame = f"{scene_frame} · {drive}"
            elif drive:
                scene_frame = drive

        return {
            "mode": mode,
            "mode_display": mode_display,
            "recap": recap,
            "cast": cast,
            "relation_drift": relation,
            "perspective": perspective,
            "scene_frame": scene_frame,
            "world": world,
            "updated_at": str(session.get("updated_at", "")).strip(),
        }

    @staticmethod
    def _branch_memory_seed_text(summary: dict[str, Any]) -> str:
        recap = str(summary.get("recap", "")).strip()
        cast = str(summary.get("cast", "")).strip()
        relation = str(summary.get("relation_drift", "") or summary.get("relation", "")).strip()
        scene = str(summary.get("scene_frame", "") or summary.get("scene", "")).strip()
        world = str(summary.get("world", "")).strip()
        parts = [part for part in (recap, cast, relation, scene, world) if part]
        return " / ".join(parts[:5])

    def _ensure_memory_store(self, run_id: str) -> bool:
        return self._resolve_memory_store(run_id) is not None

    def _resolve_memory_store(self, run_id: str) -> MarkdownSessionStore | None:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            return None
        cached = self._memory_stores.get(normalized_run_id)
        if cached is not None:
            return cached
        try:
            if callable(self._memory_store_resolver):
                resolved = self._memory_store_resolver(normalized_run_id)
                if resolved is not None:
                    self._memory_stores[normalized_run_id] = resolved
                    return resolved
            config = Config()
            config.update({"paths": {"sessions": str(self.runs_root / normalized_run_id / "__session_memory_cache")}})
            resolved = MarkdownSessionStore(PathProvider(config))
            self._memory_stores[normalized_run_id] = resolved
            return resolved
        except Exception:
            return None

    @staticmethod
    def _trim_summary_text(value: str, limit: int) -> str:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."

    @staticmethod
    def _build_last_entry_preview(session: dict[str, Any]) -> str:
        history = list(session.get("history", []) or [])
        for entry in reversed(history):
            message = str(entry.get("message", "")).strip()
            if not message:
                continue
            normalized = " ".join(message.split())
            return normalized[:180]
        pending = dict(session.get("pending_turn", {}) or {})
        pending_message = str(pending.get("transcript_message", "")).strip()
        if pending_message:
            return " ".join(pending_message.split())[:180]
        return ""

    def _build_file_urls(self, run_id: str, session: dict[str, Any]) -> dict[str, str]:
        session_id = str(session.get("session_id", "")).strip()
        urls: dict[str, str] = {}
        run_dir = self.runs_root / run_id
        session_relative = self._relative_to_run_dir(self._session_file(run_id, session_id), run_dir)
        if session_relative is not None:
            urls["session"] = self._file_url(run_id, session_relative)
        pending_path_text = str(session.get("pending_turn", {}).get("payload_path", "")).strip()
        if pending_path_text:
            pending_path = Path(pending_path_text)
        else:
            pending_path = None
        if pending_path and pending_path.exists():
            pending_relative = self._relative_to_run_dir(pending_path, run_dir)
            if pending_relative is not None:
                urls["pending_turn_payload"] = self._file_url(run_id, pending_relative)
        return urls

    @staticmethod
    def _build_scene_switch_note(scene_card: dict[str, Any], transition_message: str) -> str:
        transition = str(transition_message or "").strip()
        if transition:
            return transition
        if not scene_card:
            return ""
        title = str(scene_card.get("title", "")).strip()
        location = str(scene_card.get("location", "")).strip()
        atmosphere = str(scene_card.get("atmosphere", "")).strip()
        opening = str(scene_card.get("opening_situation", "")).strip()
        scene_bits = [bit for bit in (title, location, atmosphere) if bit]
        prefix = f"场景转到：{' / '.join(scene_bits)}。" if scene_bits else "场景发生了变化。"
        if opening:
            return f"{prefix}{opening}"
        return prefix

    @staticmethod
    def _entry_to_memory_text(entry: dict[str, Any]) -> str:
        speaker = str(entry.get("speaker", "")).strip()
        message = " ".join(str(entry.get("message", "")).split()).strip()
        target = str(entry.get("target", "")).strip()
        if not message:
            return ""
        if speaker and target:
            return f"{speaker} -> {target}: {message}"
        if speaker:
            return f"{speaker}: {message}"
        return message

    def _sessions_root(self, run_id: str) -> Path:
        return self.runs_root / run_id / "dialogue"

    def _session_dir(self, run_id: str, session_id: str) -> Path:
        return self._sessions_root(run_id) / session_id

    def _session_file(self, run_id: str, session_id: str) -> Path:
        return self._session_dir(run_id, session_id) / "session.json"

    def _file_url(self, run_id: str, relative_path: Path) -> str:
        return f"/api/web/runs/{run_id}/files/{relative_path.as_posix()}"

    @staticmethod
    def _relative_to_run_dir(path: Path, run_dir: Path) -> Path | None:
        for candidate_path, candidate_run_dir in DialogueService._relative_candidates(path, run_dir):
            try:
                return candidate_path.relative_to(candidate_run_dir)
            except ValueError:
                continue

        path_parts = DialogueService._normalized_parts(path)
        run_parts = DialogueService._normalized_parts(run_dir)
        if len(path_parts) < len(run_parts) or path_parts[: len(run_parts)] != run_parts:
            return None

        actual_path = Path(path).resolve(strict=False)
        actual_parts = actual_path.parts
        if len(actual_parts) < len(run_parts):
            return None
        relative_parts = actual_parts[len(run_parts) :]
        return Path(*relative_parts) if relative_parts else Path()

    @staticmethod
    def _relative_candidates(path: Path, run_dir: Path) -> list[tuple[Path, Path]]:
        path_obj = Path(path)
        run_dir_obj = Path(run_dir)
        pairs = [
            (path_obj, run_dir_obj),
            (path_obj.resolve(strict=False), run_dir_obj.resolve(strict=False)),
            (Path(os.path.realpath(os.fspath(path_obj))), Path(os.path.realpath(os.fspath(run_dir_obj)))),
        ]
        ordered: list[tuple[Path, Path]] = []
        seen: set[tuple[str, str]] = set()
        for candidate_path, candidate_run_dir in pairs:
            key = (os.fspath(candidate_path), os.fspath(candidate_run_dir))
            if key in seen:
                continue
            seen.add(key)
            ordered.append((candidate_path, candidate_run_dir))
        return ordered

    @staticmethod
    def _normalized_parts(path: Path) -> tuple[str, ...]:
        resolved = Path(path).resolve(strict=False)
        return tuple(part.casefold() for part in resolved.parts)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(str(path))
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
