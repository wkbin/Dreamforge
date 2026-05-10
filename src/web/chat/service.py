from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.web.artifacts.ingest import load_profile_source


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class DialogueService:
    def __init__(self, runs_root: str | Path) -> None:
        self.runs_root = Path(runs_root)

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
        self_profile: dict[str, str] | None = None,
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
            "self_insert": dict(self_profile or {}) if mode == "insert" else {},
            "self_card_id": str((self_profile or {}).get("self_card_id", "")).strip() if mode == "insert" else "",
            "history": [],
            "pending_turn": {},
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "status": "ready",
        }
        self._write_json(root / "session.json", payload)
        return self._serialize_session(run_id, payload)

    def get_session(self, run_id: str, session_id: str) -> dict[str, Any]:
        payload = self._read_json(self._session_file(run_id, session_id))
        return self._serialize_session(run_id, payload)

    def delete_session(self, run_id: str, session_id: str) -> None:
        session_dir = self._session_dir(run_id, session_id)
        if not session_dir.exists():
            raise FileNotFoundError(str(session_dir))
        shutil.rmtree(session_dir)

    def prepare_turn(
        self,
        run_manifest: dict[str, Any],
        *,
        session_id: str,
        message: str,
        speaker_override: str = "",
        transcript_message: str | None = None,
    ) -> dict[str, Any]:
        run_id = str(run_manifest.get("run_id", "")).strip()
        session = self._read_json(self._session_file(run_id, session_id))
        turn_id = f"turn-{uuid4().hex[:8]}"
        payload = self._build_turn_payload(
            run_manifest,
            session,
            turn_id=turn_id,
            message=message,
            speaker_override=speaker_override,
        )
        turn_dir = self._session_dir(run_id, session_id) / "turns"
        turn_dir.mkdir(parents=True, exist_ok=True)
        turn_payload_path = turn_dir / f"{turn_id}.payload.json"
        self._write_json(turn_payload_path, payload)
        session["pending_turn"] = {
            "turn_id": turn_id,
            "user_message": message,
            "transcript_message": message if transcript_message is None else transcript_message,
            "speaker": payload["input"]["speaker"],
            "mode": payload["mode"],
            "participants": list(payload["input"]["participants"]),
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
    ) -> dict[str, Any]:
        session = self._read_json(self._session_file(run_id, session_id))
        pending = dict(session.get("pending_turn", {}) or {})
        if not pending:
            raise ValueError("No pending turn to ingest.")
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
            session.setdefault("history", []).append(
                {
                    "speaker": pending.get("speaker", "User"),
                    "message": transcript_message,
                    "target": "",
                    "ts": pending.get("created_at", _utc_now()),
                }
            )
        session["history"].extend(clean_responses)
        session["pending_turn"] = {}
        session["updated_at"] = _utc_now()
        session["status"] = "ready"
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
        speaker_override: str = "",
    ) -> dict[str, Any]:
        participants = list(session.get("participants", []))
        mode = str(session.get("mode", "observe")).strip() or "observe"
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
        relation_excerpt = self._load_text_excerpt(relation_graph.get("relations_file", ""), limit=8000)

        persona_contexts: list[dict[str, Any]] = []
        for name in participants:
            meta = persona_map.get(name, {})
            profile_path = Path(str(meta.get("profile_file", "")))
            normalized = {}
            if profile_path.exists():
                normalized = load_profile_source(profile_path)
            persona_contexts.append(
                {
                    "name": name,
                    "profile_file": str(profile_path.resolve()) if profile_path.exists() else "",
                    "persona_dir": str(meta.get("persona_dir", "")),
                    "preview": meta.get("preview", {}),
                    "profile": {
                        "core_identity": normalized.get("core_identity", ""),
                        "story_role": normalized.get("story_role", ""),
                        "soul_goal": normalized.get("soul_goal", ""),
                        "speech_style": normalized.get("speech_style", ""),
                        "temperament_type": normalized.get("temperament_type", ""),
                        "social_mode": normalized.get("social_mode", ""),
                        "reward_logic": normalized.get("reward_logic", ""),
                        "stress_response": normalized.get("stress_response", ""),
                        "key_bonds": normalized.get("key_bonds", []),
                    },
                }
            )

        latest_history = list(session.get("history", []))[-8:]
        instructions = {
            "mode": mode,
            "generation_goal": "Keep every reply faithful to the persona bundle, relationship context, and scene mode.",
            "mode_rule": self._mode_rule(mode),
            "speaker_rule": self._speaker_rule(mode, session),
            "response_style": self._response_style_rule(mode),
        }
        responder_hints = self._responder_hints(mode, participants, speaker)

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
                "participants": participants,
                "controlled_character": session.get("controlled_character", ""),
                "self_insert": dict(session.get("self_insert", {})),
            },
            "history": latest_history,
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
                "response_limit_hint": 3 if mode == "observe" else 2,
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
    def _speaker_rule(mode: str, session: dict[str, Any]) -> str:
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
    def _response_style_rule(mode: str) -> str:
        if mode == "observe":
            return "Prefer 2-3 short in-character replies that move the scene forward naturally."
        if mode == "act":
            return "Reply as the other characters addressing the controlled role directly."
        return "Reply as the cast addressing the self-insert user naturally inside the scene."

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
            }
        if mode == "insert":
            card = dict(session.get("self_insert", {}) or {})
            return {
                "mode": "insert",
                "speaker": str(card.get("display_name", "")).strip() or "你",
                "source": "self_insert_profile",
                "must_follow": "Write as the self-insert user, keeping their full role card, identity, motives, and speaking flavor consistent.",
                "profile": dict(card),
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
        return f"The user is observing. Let {', '.join(participants)} continue the scene in character."

    @staticmethod
    def _host_suggestion_prompt_brief(mode: str, speaker: str, participants: list[str]) -> str:
        if mode == "act":
            return f"Help the user speak as {speaker} with one believable next line."
        if mode == "insert":
            return f"Help the user speak as {speaker} inside the current scene with one natural next line."
        return f"Help the user guide {', '.join(participants)} with one short prompt that clearly pushes the scene into its next beat."

    @staticmethod
    def _load_text_excerpt(path_text: str, *, limit: int) -> str:
        path = Path(str(path_text or ""))
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")[:limit].strip()

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
        session["pending_turn_summary"] = self._build_pending_turn_summary(session)
        session["session_memory_summary"] = self._build_session_memory_summary(session, transcript)
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
            "self_card_id": str(session.get("self_card_id", "")).strip(),
            "self_insert": dict(session.get("self_insert", {})),
        }
        return card

    def _build_pending_turn_summary(self, session: dict[str, Any]) -> dict[str, Any]:
        pending = dict(session.get("pending_turn", {}) or {})
        if not pending:
            return {}
        return {
            "turn_id": str(pending.get("turn_id", "")).strip(),
            "speaker": str(pending.get("speaker", "")).strip(),
            "message": str(pending.get("user_message", "")).strip(),
            "mode": str(pending.get("mode", "")).strip(),
            "participants": list(pending.get("participants", [])),
            "response_limit_hint": int(pending.get("response_limit_hint", 0) or 0),
        }

    def _build_session_memory_summary(self, session: dict[str, Any], transcript: list[dict[str, Any]]) -> dict[str, str]:
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

        return {
            "mode": mode,
            "mode_display": mode_display,
            "recap": recap,
            "cast": cast,
            "perspective": perspective,
            "world": world,
            "updated_at": str(session.get("updated_at", "")).strip(),
        }

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
