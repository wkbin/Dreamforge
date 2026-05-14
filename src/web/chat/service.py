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
from src.web.artifacts.ingest import load_relations_source
from src.core.config import Config
from src.core.path_provider import PathProvider
from src.core.session_store import MarkdownSessionStore


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class DialogueService:
    SESSION_STATE_VERSION = 1
    _SCENE_ENTER_TOKENS = ("进门", "入内", "走进", "转入", "移步", "到了", "回到", "落座", "入座", "上楼", "进屋", "推门而入")
    _SCENE_EXIT_TOKENS = ("出去", "离开", "退场", "回房", "回家", "出门", "走远", "散去", "下楼", "离席")
    _ACTION_TOKENS = ("抬头", "低头", "笑", "沉默", "转身", "皱眉", "顿住", "垂眼", "抿唇", "抬眼", "偏头", "停住", "看向")
    _ATMOSPHERE_TOKENS = ("暧昧", "尴尬", "紧张", "安静", "压抑", "冷场", "发僵", "僵住", "沉下来", "静了一拍", "气氛")
    _ENVIRONMENT_TOKENS = ("雨", "雪", "风", "雷", "灯", "烛", "门外", "脚步声", "敲门", "天色", "夜色", "天光", "雾", "潮气")
    _LEAVE_TOKENS = (
        "离开",
        "离席",
        "退场",
        "告退",
        "先走",
        "走吧",
        "退下",
        "走了",
        "离去",
        "回房",
        "回家",
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

    @classmethod
    def _empty_session_state(cls) -> dict[str, Any]:
        return {
            "version": cls.SESSION_STATE_VERSION,
            "scene": {
                "location": "",
                "time_hint": "",
                "atmosphere_summary": "",
                "progression_note": "",
                "updated_at": "",
            },
            "presence": {
                "present_participants": [],
                "offstage_participants": [],
                "updated_at": "",
            },
            "progression": {
                "should_offer_scene_shift": False,
                "scene_shift_reason": "",
                "turns_in_current_scene": 0,
                "beat_maturity": 0,
                "world_tension_summary": "",
                "updated_at": "",
            },
            "relations": {
                "matrix": {},
                "delta": {},
            },
            "characters": {
                "snapshots": {},
            },
            "signals": cls._empty_event_signals_state(),
            "memory": {
                "summary": {},
            },
        }

    def _ensure_session_state(self, session: dict[str, Any]) -> dict[str, Any]:
        state = dict(session.get("state", {}) or {})
        canonical = self._empty_session_state()
        canonical["version"] = int(state.get("version", self.SESSION_STATE_VERSION) or self.SESSION_STATE_VERSION)

        scene = dict(state.get("scene", {}) or {})
        scene_legacy = dict(state.get("scene_progress", {}) or {})
        canonical["scene"] = {
            **dict(canonical.get("scene", {}) or {}),
            **{key: value for key, value in scene.items() if key in {"location", "time_hint", "atmosphere_summary", "progression_note", "updated_at"}},
            **{
                key: value
                for key, value in scene_legacy.items()
                if key in {"location", "time_hint", "atmosphere_summary", "progression_note", "updated_at"}
            },
        }

        presence = dict(state.get("presence", {}) or {})
        canonical["presence"] = {
            **dict(canonical.get("presence", {}) or {}),
            **{
                "present_participants": list(presence.get("present_participants", []) or scene_legacy.get("present_participants", []) or []),
                "offstage_participants": list(presence.get("offstage_participants", []) or scene_legacy.get("offstage_participants", []) or []),
                "updated_at": str(presence.get("updated_at", "")).strip() or str(scene_legacy.get("updated_at", "")).strip(),
            },
        }

        progression = dict(state.get("progression", {}) or {})
        canonical["progression"] = {
            **dict(canonical.get("progression", {}) or {}),
            **{
                "should_offer_scene_shift": bool(
                    progression.get("should_offer_scene_shift", scene_legacy.get("should_offer_scene_shift", False))
                ),
                "scene_shift_reason": str(
                    progression.get("scene_shift_reason", scene_legacy.get("scene_shift_reason", ""))
                ).strip(),
                "turns_in_current_scene": int(
                    progression.get("turns_in_current_scene", scene_legacy.get("turns_in_current_scene", 0)) or 0
                ),
                "beat_maturity": int(
                    progression.get("beat_maturity", scene_legacy.get("beat_maturity", 0)) or 0
                ),
                "world_tension_summary": str(
                    progression.get("world_tension_summary", scene_legacy.get("world_tension_summary", ""))
                ).strip(),
                "updated_at": str(progression.get("updated_at", "")).strip() or str(scene_legacy.get("updated_at", "")).strip(),
            },
        }

        relations = dict(state.get("relations", {}) or {})
        canonical["relations"] = {
            "matrix": dict(relations.get("matrix", {}) or state.get("relation_matrix", {}) or {}),
            "delta": dict(relations.get("delta", {}) or state.get("relation_delta", {}) or {}),
        }
        characters = dict(state.get("characters", {}) or {})
        canonical["characters"] = {
            "snapshots": dict(characters.get("snapshots", {}) or state.get("character_snapshots", {}) or {}),
        }
        canonical["signals"] = dict(state.get("signals", {}) or state.get("event_signals", {}) or self._empty_event_signals_state())
        memory = dict(state.get("memory", {}) or {})
        canonical["memory"] = {
            "summary": dict(memory.get("summary", {}) or state.get("memory_summary", {}) or {}),
        }
        session["state"] = canonical
        return canonical

    def _session_scene_progress(self, session: dict[str, Any]) -> dict[str, Any]:
        state = self._ensure_session_state(session)
        scene = dict(state.get("scene", {}) or {})
        presence = dict(state.get("presence", {}) or {})
        progression = dict(state.get("progression", {}) or {})
        return {
            "present_participants": list(presence.get("present_participants", []) or []),
            "offstage_participants": list(presence.get("offstage_participants", []) or []),
            "time_hint": str(scene.get("time_hint", "")).strip(),
            "location": str(scene.get("location", "")).strip(),
            "atmosphere_summary": str(scene.get("atmosphere_summary", "")).strip(),
            "progression_note": str(scene.get("progression_note", "")).strip(),
            "should_offer_scene_shift": bool(progression.get("should_offer_scene_shift", False)),
            "scene_shift_reason": str(progression.get("scene_shift_reason", "")).strip(),
            "turns_in_current_scene": int(progression.get("turns_in_current_scene", 0) or 0),
            "beat_maturity": int(progression.get("beat_maturity", 0) or 0),
            "world_tension_summary": str(progression.get("world_tension_summary", "")).strip(),
            "updated_at": (
                str(progression.get("updated_at", "")).strip()
                or str(presence.get("updated_at", "")).strip()
                or str(scene.get("updated_at", "")).strip()
            ),
        }

    def _set_session_scene_progress(self, session: dict[str, Any], scene_progress: dict[str, Any] | None) -> None:
        state = self._ensure_session_state(session)
        payload = dict(scene_progress or {})
        updated_at = str(payload.get("updated_at", "")).strip() or _utc_now()
        state["scene"] = {
            "location": str(payload.get("location", "")).strip(),
            "time_hint": str(payload.get("time_hint", "")).strip(),
            "atmosphere_summary": str(payload.get("atmosphere_summary", "")).strip(),
            "progression_note": str(payload.get("progression_note", "")).strip(),
            "updated_at": updated_at,
        }
        state["presence"] = {
            "present_participants": [str(item).strip() for item in list(payload.get("present_participants", []) or []) if str(item).strip()],
            "offstage_participants": [str(item).strip() for item in list(payload.get("offstage_participants", []) or []) if str(item).strip()],
            "updated_at": updated_at,
        }
        state["progression"] = {
            "should_offer_scene_shift": bool(payload.get("should_offer_scene_shift", False)),
            "scene_shift_reason": str(payload.get("scene_shift_reason", "")).strip(),
            "turns_in_current_scene": int(payload.get("turns_in_current_scene", 0) or 0),
            "beat_maturity": int(payload.get("beat_maturity", 0) or 0),
            "world_tension_summary": str(payload.get("world_tension_summary", "")).strip(),
            "updated_at": updated_at,
        }
        self._sync_character_runtime_cards(session, payload, updated_at=updated_at)

    def _session_relation_matrix(self, session: dict[str, Any]) -> dict[str, Any]:
        state = self._ensure_session_state(session)
        return dict(state.get("relations", {}).get("matrix", {}) or {})

    def _set_session_relation_matrix(self, session: dict[str, Any], payload: dict[str, Any] | None) -> None:
        state = self._ensure_session_state(session)
        state.setdefault("relations", {})["matrix"] = dict(payload or {})

    def _session_relation_delta(self, session: dict[str, Any]) -> dict[str, Any]:
        state = self._ensure_session_state(session)
        return dict(state.get("relations", {}).get("delta", {}) or {})

    def _set_session_relation_delta(self, session: dict[str, Any], payload: dict[str, Any] | None) -> None:
        state = self._ensure_session_state(session)
        state.setdefault("relations", {})["delta"] = dict(payload or {})

    def _session_character_snapshots(self, session: dict[str, Any]) -> dict[str, Any]:
        state = self._ensure_session_state(session)
        return dict(state.get("characters", {}).get("snapshots", {}) or {})

    def _set_session_character_snapshots(self, session: dict[str, Any], payload: dict[str, Any] | None) -> None:
        state = self._ensure_session_state(session)
        state.setdefault("characters", {})["snapshots"] = dict(payload or {})

    def _sync_character_runtime_cards(
        self,
        session: dict[str, Any],
        scene_progress: dict[str, Any] | None,
        *,
        updated_at: str,
    ) -> None:
        state = self._ensure_session_state(session)
        snapshots = dict(state.get("characters", {}).get("snapshots", {}) or {})
        progress = dict(scene_progress or {})
        participants = [str(item).strip() for item in list(session.get("participants", []) or []) if str(item).strip()]
        present = {
            str(item).strip()
            for item in list(progress.get("present_participants", []) or [])
            if str(item).strip()
        }
        location = str(progress.get("location", "")).strip()
        time_hint = str(progress.get("time_hint", "")).strip()
        for name in participants:
            current = dict(snapshots.get(name, {}) or {})
            current["present_state"] = "onstage" if name in present else "offstage"
            if location:
                current["scene_location"] = location
            if time_hint:
                current["time_hint"] = time_hint
            current["updated_at"] = updated_at
            snapshots[name] = current
        state.setdefault("characters", {})["snapshots"] = snapshots

    def _session_event_signals(self, session: dict[str, Any]) -> dict[str, Any]:
        state = self._ensure_session_state(session)
        return dict(state.get("signals", {}) or {})

    def _set_session_event_signals(self, session: dict[str, Any], payload: dict[str, Any] | None) -> None:
        state = self._ensure_session_state(session)
        state["signals"] = dict(payload or self._empty_event_signals_state())

    def _session_memory_summary_state(self, session: dict[str, Any]) -> dict[str, Any]:
        state = self._ensure_session_state(session)
        return dict(state.get("memory", {}).get("summary", {}) or {})

    def _set_session_memory_summary_state(self, session: dict[str, Any], payload: dict[str, Any] | None) -> None:
        state = self._ensure_session_state(session)
        state.setdefault("memory", {})["summary"] = dict(payload or {})

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
            "state": self._empty_session_state(),
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "status": "ready",
        }
        self._set_session_relation_matrix(payload, self._seed_relation_matrix(run_manifest, selected))
        if dict(scene_profile or {}):
            initial_summary = self._build_session_memory_summary(run_id, payload, [])
            payload["scene_history"] = [
                self._build_scene_history_entry(
                    scene_profile or {},
                    transition_message="",
                    memory_summary=initial_summary,
                )
            ]
        self._set_session_scene_progress(payload, self._derive_scene_progress_state(payload, []))
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
        self._set_session_scene_progress(session, self._derive_scene_progress_state(session, self._serialize_transcript(session)))
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

    def update_scene_progress_state(
        self,
        run_id: str,
        session_id: str,
        scene_progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self._read_json(self._session_file(run_id, session_id))
        self._set_session_scene_progress(
            session,
            self._merge_scene_progress_state(
                session,
                dict(scene_progress or {}),
            ),
        )
        session["updated_at"] = _utc_now()
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
        scene_progress = self._session_scene_progress(session)
        character_snapshots = self._session_character_snapshots(session)
        active_participants = self._resolve_active_participants(participants, full_history, mode, speaker, scene_progress)
        scene_card = dict(session.get("scene_card", {}) or {})
        transcript = self._serialize_transcript(session)

        persona_contexts = self._build_persona_contexts(
            participants=participants,
            active_participants=active_participants,
            persona_map=persona_map,
            mode=mode,
            controlled_character=str(session.get("controlled_character", "")).strip(),
            character_snapshots=character_snapshots,
        )

        latest_history = full_history[-8:]
        relation_excerpt = self._build_relation_excerpt(
            relation_graph.get("relations_file", ""),
            participants=participants,
            active_participants=active_participants,
            message=message,
            scene_card=scene_card,
        )
        session_relation_excerpt = self._build_session_relation_excerpt(
            session,
            participants=participants,
            active_participants=active_participants,
        )
        if session_relation_excerpt:
            relation_excerpt = (
                f"{relation_excerpt}\n\n# SESSION_RELATION_STATE\n{session_relation_excerpt}".strip()
                if relation_excerpt
                else f"# SESSION_RELATION_STATE\n{session_relation_excerpt}"
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
            scene_progress=scene_progress,
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
            "progression_rule": self._scene_progress_rule(scene_progress),
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
                "scene_progress": scene_progress,
                "character_snapshots": character_snapshots,
                "self_insert": dict(session.get("self_insert", {})),
            },
            "history": latest_history,
            "scene_card": scene_card,
            "memory_context": memory_context,
            "scene_progress": scene_progress,
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
                "output_rule": (
                    "Return only in-world character replies. Do not explain the workflow or mention prompts. "
                    "Do not split obvious small actions into standalone narration; keep them inside the speaking character's line with brief parenthetical action."
                ),
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
                "use 场景提示 or 旁白 only for true scene beats such as entrances, exits, environment changes, or transitions; "
                "for small gestures like raising eyes, lowering the head, smiling, pausing, or turning around, fold them into the character's spoken line with short parenthetical action instead of a separate narration line."
            )
        if mode == "observe":
            return (
                "Prefer 2-4 short in-character replies when the scene is busy, and fewer when it is quiet. "
                "Small visible actions should stay inside the character line as short parenthetical beats, for example （她低头笑了笑）..., rather than becoming standalone narration."
            )
        if mode == "act":
            return (
                "Reply as the other characters addressing the controlled role directly. "
                "If a character动作 is obvious but small, embed it in parentheses inside that character's line instead of emitting a separate narration line."
            )
        return (
            "Reply as the cast addressing the self-insert user naturally inside the scene. "
            "Keep obvious small actions inside the speaking character's line with short parentheses, not as separate narration."
        )

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
    def _scene_progress_rule(scene_progress: dict[str, Any]) -> str:
        state = dict(scene_progress or {})
        present = [str(item).strip() for item in list(state.get("present_participants", []) or []) if str(item).strip()]
        offstage = [str(item).strip() for item in list(state.get("offstage_participants", []) or []) if str(item).strip()]
        time_hint = str(state.get("time_hint", "")).strip()
        location = str(state.get("location", "")).strip()
        atmosphere = str(state.get("atmosphere_summary", "")).strip()
        note = str(state.get("progression_note", "")).strip()
        shift = bool(state.get("should_offer_scene_shift", False))
        reason = str(state.get("scene_shift_reason", "")).strip()
        beat_maturity = int(state.get("beat_maturity", 0) or 0)

        bits = [
            "Respect scene continuity: keep who is present, who already left, and what time/location the scene has drifted to internally consistent.",
        ]
        if time_hint or location:
            details = []
            if time_hint:
                details.append(f"time={time_hint}")
            if location:
                details.append(f"location={location}")
            if atmosphere:
                details.append(f"atmosphere={atmosphere}")
            bits.append(f"Current scene state: {', '.join(details)}.")
        if present:
            bits.append(f"Characters currently in-scene: {', '.join(present)}.")
        if offstage:
            bits.append(
                f"Characters currently offstage: {', '.join(offstage)}. Offstage characters must not speak or act until the text explicitly brings them back."
            )
        bits.append(
            "Let farewells, departures, going home, changing rooms, or entering a more private location naturally change who can reply next."
        )
        bits.append(
            "Allow time to move forward when the conversation cues it, instead of freezing the whole scene in one unchanged moment."
        )
        if note:
            bits.append(f"Latest progression note: {note}.")
        if beat_maturity:
            bits.append(f"Current beat maturity is {beat_maturity}/100; let replies feel appropriately early, settled, or ready to turn.")
        tension = str(state.get("world_tension_summary", "")).strip()
        if tension:
            bits.append(f"Current world tension to carry forward: {tension}.")
        if shift:
            bits.append(
                f"This beat is mature enough to hint a next scene or transition if it helps momentum. Reason: {reason or 'the current beat already feels complete'}."
            )
        return " ".join(bits)

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
        scene_progress: dict[str, Any] | None = None,
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

        state_present = [
            str(item).strip()
            for item in list(dict(scene_progress or {}).get("present_participants", []) or [])
            if str(item).strip() in deduped
        ]
        state_offstage = {
            str(item).strip()
            for item in list(dict(scene_progress or {}).get("offstage_participants", []) or [])
            if str(item).strip() in deduped
        }
        departed = cls._infer_departed_participants(deduped, history)
        if state_present:
            active = [name for name in state_present if name not in state_offstage and name not in departed]
            if mode == "act":
                active = [name for name in active if name != speaker]
            if active:
                return active

        active = [name for name in deduped if name not in departed]
        if mode == "act":
            active = [name for name in active if name != speaker]
        if active:
            return active
        # Never end up with an empty speaker pool.
        fallback = [name for name in deduped if not (mode == "act" and name == speaker)]
        return fallback or deduped[:1]

    def _merge_scene_progress_state(self, session: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        base = self._derive_scene_progress_state(session, self._serialize_transcript(session))
        participants = [str(item).strip() for item in list(session.get("participants", []) or []) if str(item).strip()]
        allowed = set(participants)

        def clean_names(values: Any) -> list[str]:
            names: list[str] = []
            for item in list(values or []):
                name = str(item or "").strip()
                if not name or name not in allowed or name in names:
                    continue
                names.append(name)
            return names

        present = clean_names(incoming.get("present_participants", [])) or list(base.get("present_participants", []) or [])
        offstage = [name for name in clean_names(incoming.get("offstage_participants", [])) if name not in present]
        merged = {
            "present_participants": present,
            "offstage_participants": offstage or [name for name in list(base.get("offstage_participants", []) or []) if name not in present],
            "time_hint": str(incoming.get("time_hint", "")).strip() or str(base.get("time_hint", "")).strip(),
            "location": str(incoming.get("location", "")).strip() or str(base.get("location", "")).strip(),
            "atmosphere_summary": str(incoming.get("atmosphere_summary", "")).strip() or str(base.get("atmosphere_summary", "")).strip(),
            "progression_note": str(incoming.get("progression_note", "")).strip() or str(base.get("progression_note", "")).strip(),
            "should_offer_scene_shift": bool(incoming.get("should_offer_scene_shift", base.get("should_offer_scene_shift", False))),
            "scene_shift_reason": str(incoming.get("scene_shift_reason", "")).strip() or str(base.get("scene_shift_reason", "")).strip(),
            "turns_in_current_scene": int(base.get("turns_in_current_scene", 0) or 0),
            "beat_maturity": int(incoming.get("beat_maturity", base.get("beat_maturity", 0)) or 0),
            "world_tension_summary": str(incoming.get("world_tension_summary", "")).strip() or str(base.get("world_tension_summary", "")).strip(),
            "updated_at": _utc_now(),
        }
        if merged["should_offer_scene_shift"]:
            merged["beat_maturity"] = max(75, int(merged.get("beat_maturity", 0) or 0))
        return merged

    def _derive_scene_progress_state(self, session: dict[str, Any], transcript: list[dict[str, Any]]) -> dict[str, Any]:
        participants = [str(item).strip() for item in list(session.get("participants", []) or []) if str(item).strip()]
        scene_card = dict(session.get("scene_card", {}) or {})
        prior = self._session_scene_progress(session)
        history = list(session.get("history", []) or [])
        presence_state = self._derive_presence_state(session, participants=participants, history=history)
        scene_frame = self._derive_scene_frame_state(session, transcript=transcript, scene_card=scene_card, prior=prior)
        progression_state = self._derive_progression_state(
            session,
            transcript=transcript,
            scene_card=scene_card,
            prior=prior,
            presence_state=presence_state,
            scene_frame=scene_frame,
        )
        progression_bits = []
        if scene_frame.get("location"):
            progression_bits.append(f"地点：{scene_frame['location']}")
        if scene_frame.get("time_hint"):
            progression_bits.append(f"时间：{scene_frame['time_hint']}")
        if scene_frame.get("atmosphere_summary"):
            progression_bits.append(f"氛围：{scene_frame['atmosphere_summary']}")
        if presence_state.get("present_participants"):
            progression_bits.append(f"在场：{'、'.join(list(presence_state.get('present_participants', []))[:4])}")
        if presence_state.get("offstage_participants"):
            progression_bits.append(f"离场：{'、'.join(list(presence_state.get('offstage_participants', []))[:3])}")
        progression_bits.append(f"成熟度：{int(progression_state.get('beat_maturity', 0) or 0)}")
        progression_note = "；".join(bit for bit in progression_bits if bit)
        return {
            **presence_state,
            **scene_frame,
            **progression_state,
            "progression_note": progression_note,
            "updated_at": _utc_now(),
        }

    def _derive_presence_state(
        self,
        session: dict[str, Any],
        *,
        participants: list[str],
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        departed = self._infer_departed_participants(participants, history)
        latest_exit = self._latest_event_signal(session, "cast_exit")
        latest_enter = self._latest_event_signal(session, "cast_enter")
        if latest_exit:
            actor = str(latest_exit.get("actor", "")).strip()
            if actor in participants:
                departed.add(actor)
        if latest_enter:
            actor = str(latest_enter.get("actor", "")).strip()
            if actor in participants:
                departed.discard(actor)
        present = [name for name in participants if name not in departed]
        if not present and participants:
            present = participants[:1]
        return {
            "present_participants": present,
            "offstage_participants": [name for name in participants if name not in present],
        }

    def _derive_scene_frame_state(
        self,
        session: dict[str, Any],
        *,
        transcript: list[dict[str, Any]],
        scene_card: dict[str, Any],
        prior: dict[str, Any],
    ) -> dict[str, Any]:
        latest_time_event = self._latest_event_signal(session, "time_change")
        latest_scene_event = self._latest_event_signal(session, "scene_transition")
        time_hint = (
            str(latest_time_event.get("time_hint", "")).strip()
            or self._infer_time_hint(transcript)
            or str(prior.get("time_hint", "")).strip()
            or str(scene_card.get("time_hint", "")).strip()
        )
        location = (
            str(latest_scene_event.get("location_hint", "")).strip()
            or str(prior.get("location", "")).strip()
            or str(scene_card.get("location", "")).strip()
        )
        latest_atmosphere_event = self._latest_event_signal(session, "atmosphere_shift")
        atmosphere_summary = (
            self._trim_summary_text(str(latest_atmosphere_event.get("cue", "")).strip(), 80)
            or self._infer_atmosphere_summary(transcript)
            or self._trim_summary_text(str(prior.get("atmosphere_summary", "")).strip(), 80)
            or self._trim_summary_text(str(scene_card.get("atmosphere", "")).strip(), 80)
        )
        return {
            "time_hint": time_hint,
            "location": location,
            "atmosphere_summary": atmosphere_summary,
        }

    def _derive_progression_state(
        self,
        session: dict[str, Any],
        *,
        transcript: list[dict[str, Any]],
        scene_card: dict[str, Any],
        prior: dict[str, Any],
        presence_state: dict[str, Any],
        scene_frame: dict[str, Any],
    ) -> dict[str, Any]:
        latest_beat_event = self._latest_event_signal(session, "beat_complete")
        turns_in_current_scene = self._count_current_scene_turns(session)
        beat_maturity = self._estimate_scene_maturity(
            turns_in_current_scene=turns_in_current_scene,
            transcript=transcript,
            scene_card=scene_card,
            presence_state=presence_state,
            scene_frame=scene_frame,
            latest_beat_event=latest_beat_event,
            prior=prior,
        )
        scene_shift_reason = ""
        should_offer_scene_shift = False
        if scene_card and beat_maturity >= 72:
            should_offer_scene_shift = True
            scene_shift_reason = "这一幕已经接了好几拍，可以顺势换到下一幕。"
        if latest_beat_event:
            should_offer_scene_shift = True
            scene_shift_reason = str(latest_beat_event.get("cue", "")).strip() or scene_shift_reason
        initial_time = str(scene_card.get("time_hint", "")).strip()
        time_hint = str(scene_frame.get("time_hint", "")).strip()
        if time_hint and initial_time and time_hint != initial_time and beat_maturity >= 55:
            should_offer_scene_shift = True
            scene_shift_reason = scene_shift_reason or f"时间已经自然推到{time_hint}，适合顺势转下一拍。"
        return {
            "should_offer_scene_shift": should_offer_scene_shift,
            "scene_shift_reason": scene_shift_reason,
            "turns_in_current_scene": turns_in_current_scene,
            "beat_maturity": beat_maturity,
            "world_tension_summary": self._derive_world_tension_summary(session, transcript=transcript, scene_frame=scene_frame),
        }

    def _estimate_scene_maturity(
        self,
        *,
        turns_in_current_scene: int,
        transcript: list[dict[str, Any]],
        scene_card: dict[str, Any],
        presence_state: dict[str, Any],
        scene_frame: dict[str, Any],
        latest_beat_event: dict[str, Any],
        prior: dict[str, Any],
    ) -> int:
        score = min(60, max(0, turns_in_current_scene * 10))
        if latest_beat_event:
            score += 25
        if str(scene_frame.get("time_hint", "")).strip() and str(scene_frame.get("time_hint", "")).strip() != str(scene_card.get("time_hint", "")).strip():
            score += 10
        if str(scene_frame.get("location", "")).strip() and str(scene_frame.get("location", "")).strip() != str(scene_card.get("location", "")).strip():
            score += 10
        if list(presence_state.get("offstage_participants", []) or []):
            score += 6
        if str(scene_frame.get("atmosphere_summary", "")).strip():
            score += 4
        previous_maturity = int(prior.get("beat_maturity", 0) or 0)
        if previous_maturity:
            score = max(score, min(100, previous_maturity - 8))
        if len(transcript) >= 6:
            score += 6
        return max(0, min(100, score))

    def _infer_atmosphere_summary(self, transcript: list[dict[str, Any]]) -> str:
        recent_messages = [
            str(item.get("message", "")).strip()
            for item in list(transcript or [])[-8:]
            if str(item.get("message", "")).strip()
        ]
        if not recent_messages:
            return ""
        joined = " ".join(recent_messages)
        for token in self._ATMOSPHERE_TOKENS:
            if token in joined:
                return self._trim_summary_text(token, 40)
        for message in reversed(recent_messages):
            trimmed = self._trim_summary_text(message, 40)
            if trimmed:
                return trimmed
        return ""

    def _derive_world_tension_summary(
        self,
        session: dict[str, Any],
        *,
        transcript: list[dict[str, Any]],
        scene_frame: dict[str, Any],
    ) -> str:
        latest_atmosphere_event = self._latest_event_signal(session, "atmosphere_shift")
        latest_relation_event = self._latest_event_signal(session, "relationship_shift")
        latest_scene_event = self._latest_event_signal(session, "scene_transition", "environment_change", "time_change")
        for candidate in (latest_atmosphere_event, latest_relation_event, latest_scene_event):
            cue = self._trim_summary_text(str((candidate or {}).get("cue", "")).strip(), 88)
            if cue:
                return cue
        relation_delta = self._session_relation_delta(session)
        if relation_delta:
            pair_key, delta = next(iter(relation_delta.items()))
            metrics: list[str] = []
            for field, label in (("trust", "信任"), ("affection", "好感"), ("hostility", "敌意"), ("ambiguity", "摇摆")):
                amount = int(dict(delta or {}).get(field, 0) or 0)
                if amount:
                    metrics.append(f"{label}{amount:+d}")
            if metrics:
                return self._trim_summary_text(f"{pair_key} 当前仍在变化：{'、'.join(metrics)}", 88)
        atmosphere = str(scene_frame.get("atmosphere_summary", "")).strip()
        if atmosphere:
            return self._trim_summary_text(f"这一拍的气氛是：{atmosphere}", 88)
        for item in reversed(list(transcript or [])[-8:]):
            role = str(item.get("role", "")).strip()
            message = self._trim_summary_text(str(item.get("message", "")).strip(), 88)
            if role in {"scene", "director"} and message:
                return message
        return ""

    @staticmethod
    def _infer_time_hint(transcript: list[dict[str, Any]]) -> str:
        tokens = (
            "拂晓", "清晨", "早晨", "早上", "上午", "晌午", "中午", "午后", "下午",
            "傍晚", "黄昏", "晚上", "今晚", "入夜", "夜里", "夜间", "夜深", "深夜",
            "半夜", "凌晨", "三更", "四更", "五更", "天亮",
        )
        for item in reversed(list(transcript or [])[-14:]):
            message = str(item.get("message", "")).strip()
            if not message:
                continue
            for token in tokens:
                if token in message:
                    return token
        return ""

    @staticmethod
    def _count_current_scene_turns(session: dict[str, Any]) -> int:
        history = list(session.get("history", []) or [])
        scene_history = list(session.get("scene_history", []) or [])
        if not history:
            return 0
        latest_scene_ts = str((scene_history[-1] or {}).get("ts", "")).strip() if scene_history else ""
        if latest_scene_ts:
            return sum(1 for item in history if str(item.get("ts", "")).strip() >= latest_scene_ts and str(item.get("message", "")).strip())
        return len([item for item in history[-12:] if str(item.get("message", "")).strip()])

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
            if (
                f"{name}{token}" in compact
                or f"{token}{name}" in compact
                or re.search(re.escape(name) + r".{0,4}" + re.escape(token), compact)
                or re.search(re.escape(token) + r".{0,4}" + re.escape(name), compact)
            ):
                return True
        return False

    @classmethod
    def _contains_return_signal(cls, text: str, name: str) -> bool:
        compact = re.sub(r"\s+", "", str(text or ""))
        for token in cls._RETURN_TOKENS:
            if (
                f"{name}{token}" in compact
                or f"{token}{name}" in compact
                or re.search(re.escape(name) + r".{0,4}" + re.escape(token), compact)
                or re.search(re.escape(token) + r".{0,4}" + re.escape(name), compact)
            ):
                return True
        return False

    @classmethod
    def _self_exit_signal(cls, text: str) -> bool:
        compact = re.sub(r"\s+", "", str(text or ""))
        return any(
            token in compact
            for token in ("我先走", "我先告退", "我先退下", "我先回房", "我先回家", "我先离开", "我先撤了", "容我告退")
        )

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

    @staticmethod
    def _pair_key(left: str, right: str) -> str:
        first = str(left or "").strip()
        second = str(right or "").strip()
        return "_".join(sorted([first, second])) if first and second else ""

    @staticmethod
    def _default_relation_entry() -> dict[str, Any]:
        return {
            "trust": 5,
            "affection": 5,
            "hostility": 0,
            "ambiguity": 3,
            "evidence_lines": [],
        }

    @classmethod
    def _normalize_relation_entry(cls, raw: dict[str, Any] | None) -> dict[str, Any]:
        source = dict(raw or {})
        normalized = cls._default_relation_entry()
        for field in ("trust", "affection", "hostility", "ambiguity"):
            try:
                normalized[field] = int(source.get(field, normalized[field]) or normalized[field])
            except Exception:
                continue
        for field in ("conflict_point", "typical_interaction", "hidden_attitude", "relation_change", "appellation_to_target", "last_event"):
            value = str(source.get(field, "")).strip()
            if value:
                normalized[field] = value
        evidence_lines = source.get("evidence_lines", [])
        if isinstance(evidence_lines, list):
            normalized["evidence_lines"] = [str(item).strip() for item in evidence_lines if str(item).strip()][:10]
        return normalized

    def _seed_relation_matrix(self, run_manifest: dict[str, Any], participants: list[str]) -> dict[str, Any]:
        relation_graph = dict(run_manifest.get("artifact_index", {}).get("relation_graph", {}) or {})
        relation_path = Path(str(relation_graph.get("relations_file", "")).strip())
        if not relation_path.exists():
            return {}
        try:
            payload = load_relations_source(relation_path)
        except Exception:
            return {}
        relations = dict(payload.get("relations", {}) or {})
        selected = [str(item).strip() for item in list(participants or []) if str(item).strip()]
        if len(selected) < 2:
            return {}
        keys: dict[str, Any] = {}
        for index, left in enumerate(selected):
            for right in selected[index + 1 :]:
                pair_key = self._pair_key(left, right)
                if not pair_key:
                    continue
                keys[pair_key] = self._normalize_relation_entry(dict(relations.get(pair_key, {}) or {}))
        return keys

    def _merged_relation_matrix(self, session: dict[str, Any], participants: list[str]) -> dict[str, Any]:
        base = {
            str(key).strip(): self._normalize_relation_entry(dict(value or {}))
            for key, value in self._session_relation_matrix(session).items()
            if str(key).strip()
        }
        deltas = self._session_relation_delta(session)
        selected = [str(item).strip() for item in list(participants or []) if str(item).strip()]
        for index, left in enumerate(selected):
            for right in selected[index + 1 :]:
                pair_key = self._pair_key(left, right)
                if pair_key and pair_key not in base:
                    base[pair_key] = self._default_relation_entry()
        for pair_key, delta in deltas.items():
            normalized_key = str(pair_key).strip()
            if not normalized_key:
                continue
            merged = dict(base.get(normalized_key, self._default_relation_entry()))
            delta_payload = dict(delta or {})
            for field in ("trust", "affection", "hostility", "ambiguity"):
                try:
                    step = int(delta_payload.get(field, 0) or 0)
                except Exception:
                    step = 0
                baseline = int(merged.get(field, self._default_relation_entry()[field]) or self._default_relation_entry()[field])
                merged[field] = max(0, min(10, baseline + step))
            for field in ("last_event", "relation_change", "typical_interaction", "last_actor", "last_target", "updated_at"):
                value = str(delta_payload.get(field, "")).strip()
                if value:
                    merged[field] = value
            if "momentum" in delta_payload:
                try:
                    merged["momentum"] = int(delta_payload.get("momentum", 0) or 0)
                except Exception:
                    pass
            evidence_lines = list(merged.get("evidence_lines", []) or [])
            for item in list(delta_payload.get("evidence_lines", []) or []):
                text = str(item).strip()
                if text:
                    evidence_lines.append(text)
            if evidence_lines:
                merged["evidence_lines"] = evidence_lines[-10:]
            base[normalized_key] = merged
        return base

    @staticmethod
    def _empty_event_signals_state() -> dict[str, Any]:
        return {
            "recent": [],
            "by_type": {},
            "updated_at": "",
        }

    def _merge_event_signals_state(self, session: dict[str, Any], incoming: list[dict[str, Any]]) -> dict[str, Any]:
        current = self._session_event_signals(session)
        recent = [
            dict(item or {})
            for item in list(current.get("recent", []) or [])
            if isinstance(item, dict)
        ]
        allowed_participants = {
            str(item).strip()
            for item in list(session.get("participants", []) or [])
            if str(item).strip()
        }

        def normalize_event(item: dict[str, Any]) -> dict[str, Any]:
            event = dict(item or {})
            kind = str(event.get("kind", "")).strip()
            scope = str(event.get("scope", "")).strip() or ("character" if bool(event.get("should_inline", False)) else "scene")
            actor = str(event.get("actor", "")).strip()
            target = str(event.get("target", "")).strip()
            cue = self._trim_summary_text(str(event.get("cue", "")).strip(), 160)
            source = str(event.get("source", "")).strip() or "runtime"
            time_hint = self._trim_summary_text(str(event.get("time_hint", "")).strip(), 40)
            location_hint = self._trim_summary_text(str(event.get("location_hint", "")).strip(), 60)
            ts = str(event.get("ts", "")).strip() or _utc_now()
            if actor and allowed_participants and actor not in allowed_participants and actor not in {"场景提示", "旁白", "User"}:
                actor = ""
            if target and allowed_participants and target not in allowed_participants:
                target = ""
            normalized = {
                "kind": kind,
                "scope": scope,
                "actor": actor,
                "target": target,
                "cue": cue,
                "source": source,
                "should_inline": bool(event.get("should_inline", False)),
                "ts": ts,
            }
            if time_hint:
                normalized["time_hint"] = time_hint
            if location_hint:
                normalized["location_hint"] = location_hint
            return normalized

        event_map: dict[str, dict[str, Any]] = {}
        for item in recent:
            normalized = normalize_event(item)
            if not normalized.get("kind") or not normalized.get("cue"):
                continue
            key = "|".join(
                [
                    normalized["kind"],
                    normalized.get("actor", ""),
                    normalized.get("target", ""),
                    normalized.get("cue", ""),
                ]
            )
            event_map[key] = normalized
        for item in incoming:
            normalized = normalize_event(item)
            if not normalized.get("kind") or not normalized.get("cue"):
                continue
            key = "|".join(
                [
                    normalized["kind"],
                    normalized.get("actor", ""),
                    normalized.get("target", ""),
                    normalized.get("cue", ""),
                ]
            )
            event_map[key] = normalized

        merged_recent = sorted(
            event_map.values(),
            key=lambda item: str(item.get("ts", "")).strip(),
        )[-40:]
        by_type: dict[str, list[dict[str, Any]]] = {}
        for item in merged_recent:
            kind = str(item.get("kind", "")).strip()
            if not kind:
                continue
            bucket = by_type.setdefault(kind, [])
            bucket.append(item)
            if len(bucket) > 8:
                by_type[kind] = bucket[-8:]
        return {
            "recent": merged_recent,
            "by_type": by_type,
            "updated_at": _utc_now(),
        }

    def _latest_event_signal(self, session: dict[str, Any], *kinds: str) -> dict[str, Any]:
        wanted = {str(item).strip() for item in kinds if str(item).strip()}
        if not wanted:
            return {}
        recent = list(self._session_event_signals(session).get("recent", []) or [])
        for item in reversed(recent):
            event = dict(item or {})
            if str(event.get("kind", "")).strip() in wanted:
                return event
        return {}

    def _build_session_relation_excerpt(
        self,
        session: dict[str, Any],
        *,
        participants: list[str],
        active_participants: list[str],
    ) -> str:
        deltas = self._session_relation_delta(session)
        if not deltas:
            return ""
        merged = self._merged_relation_matrix(session, participants)
        focus_keys: list[str] = []
        focus_names = [str(item).strip() for item in [*active_participants, *participants] if str(item).strip()]
        for index, left in enumerate(focus_names):
            for right in focus_names[index + 1 :]:
                pair_key = self._pair_key(left, right)
                if pair_key and pair_key not in focus_keys:
                    focus_keys.append(pair_key)
        lines: list[str] = []
        for pair_key in focus_keys:
            delta = dict(deltas.get(pair_key, {}) or {})
            if not delta:
                continue
            relation = dict(merged.get(pair_key, {}) or {})
            metric_bits: list[str] = []
            for field, label in (("trust", "信任"), ("affection", "好感"), ("hostility", "敌意"), ("ambiguity", "暧昧/摇摆")):
                change = int(delta.get(field, 0) or 0)
                if change:
                    metric_bits.append(f"{label}{change:+d}")
            if not metric_bits:
                continue
            status_bits = [
                f"trust={int(relation.get('trust', 5) or 5)}",
                f"affection={int(relation.get('affection', 5) or 5)}",
                f"hostility={int(relation.get('hostility', 0) or 0)}",
                f"ambiguity={int(relation.get('ambiguity', 3) or 3)}",
            ]
            line = f"## {pair_key}\n- session_delta: {', '.join(metric_bits)}\n- merged_state: {', '.join(status_bits)}"
            last_event = str(delta.get("last_event", "")).strip()
            if last_event:
                line = f"{line}\n- last_event: {self._trim_summary_text(last_event, 120)}"
            last_actor = str(delta.get("last_actor", "")).strip()
            last_target = str(delta.get("last_target", "")).strip()
            if last_actor or last_target:
                line = f"{line}\n- drift: {self._trim_summary_text(' -> '.join([item for item in (last_actor, last_target) if item]), 80)}"
            lines.append(line)
            if len("\n".join(lines)) >= 1200:
                break
        return "\n".join(lines).strip()

    def _build_session_event_excerpt(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        event_signals = self._session_event_signals(session)
        recent = list(event_signals.get("recent", []) or [])
        normalized: list[dict[str, Any]] = []
        for item in recent[-8:]:
            event = dict(item or {})
            kind = str(event.get("kind", "")).strip()
            cue = self._trim_summary_text(str(event.get("cue", "")).strip(), 120)
            if not kind or not cue:
                continue
            normalized_event = {
                "kind": kind,
                "scope": str(event.get("scope", "")).strip(),
                "actor": str(event.get("actor", "")).strip(),
                "target": str(event.get("target", "")).strip(),
                "cue": cue,
                "should_inline": bool(event.get("should_inline", False)),
            }
            time_hint = str(event.get("time_hint", "")).strip()
            location_hint = str(event.get("location_hint", "")).strip()
            if time_hint:
                normalized_event["time_hint"] = time_hint
            if location_hint:
                normalized_event["location_hint"] = location_hint
            normalized.append(
                {
                    key: value
                    for key, value in normalized_event.items()
                    if value not in ("", [], False)
                }
            )
        return normalized

    def _build_persona_contexts(
        self,
        *,
        participants: list[str],
        active_participants: list[str],
        persona_map: dict[str, dict[str, Any]],
        mode: str,
        controlled_character: str,
        character_snapshots: dict[str, Any] | None = None,
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
                    "session_snapshot": self._persona_snapshot_payload(
                        dict((character_snapshots or {}).get(normalized_name, {}) or {}),
                        detailed=is_detailed,
                    ),
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
            "appearance_feature": str(preview.get("appearance_feature", "")).strip() or str(normalized_profile.get("appearance_feature", "")).strip(),
        }

    @staticmethod
    def _persona_profile_payload(normalized_profile: dict[str, Any], *, detailed: bool) -> dict[str, Any]:
        base = {
            "core_identity": normalized_profile.get("core_identity", ""),
            "story_role": normalized_profile.get("story_role", ""),
            "gender": normalized_profile.get("gender", ""),
            "age_stage": normalized_profile.get("age_stage", ""),
            "appearance_feature": normalized_profile.get("appearance_feature", ""),
            "habit_action": normalized_profile.get("habit_action", ""),
            "speech_style": normalized_profile.get("speech_style", ""),
            "temperament_type": normalized_profile.get("temperament_type", ""),
            "stress_response": normalized_profile.get("stress_response", ""),
            "key_bonds": normalized_profile.get("key_bonds", []),
        }
        if detailed:
            base.update(
                {
                    "soul_goal": normalized_profile.get("soul_goal", ""),
                    "worldview": normalized_profile.get("worldview", ""),
                    "social_mode": normalized_profile.get("social_mode", ""),
                    "preference_like": normalized_profile.get("preference_like", []),
                    "dislike_hate": normalized_profile.get("dislike_hate", []),
                    "reward_logic": normalized_profile.get("reward_logic", ""),
                }
            )
        return base

    @staticmethod
    def _persona_snapshot_payload(snapshot: dict[str, Any], *, detailed: bool) -> dict[str, Any]:
        if not snapshot:
            return {}
        fields = {
            "mood": str(snapshot.get("mood", "")).strip(),
            "interaction_state": str(snapshot.get("interaction_state", "")).strip(),
            "focus": str(snapshot.get("focus", "")).strip(),
            "last_target": str(snapshot.get("last_target", "")).strip(),
            "last_message": str(snapshot.get("last_message", "")).strip(),
            "present_state": str(snapshot.get("present_state", "")).strip(),
            "scene_location": str(snapshot.get("scene_location", "")).strip(),
            "time_hint": str(snapshot.get("time_hint", "")).strip(),
        }
        if detailed:
            fields["last_event"] = str(snapshot.get("last_event", "")).strip()
            fields["updated_at"] = str(snapshot.get("updated_at", "")).strip()
        return {key: value for key, value in fields.items() if value}

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
        scene_progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state_summary = self._session_memory_summary_state(session)
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
        normalized_progress = dict(scene_progress or {})
        progress_snapshot = {
            "time_hint": self._trim_summary_text(str(normalized_progress.get("time_hint", "")).strip(), 32),
            "location": self._trim_summary_text(str(normalized_progress.get("location", "")).strip(), 48),
            "progression_note": self._trim_summary_text(str(normalized_progress.get("progression_note", "")).strip(), 120),
            "present_participants": [
                str(item).strip()
                for item in list(normalized_progress.get("present_participants", []) or [])[:6]
                if str(item).strip()
            ],
            "offstage_participants": [
                str(item).strip()
                for item in list(normalized_progress.get("offstage_participants", []) or [])[:6]
                if str(item).strip()
            ],
            "should_offer_scene_shift": bool(normalized_progress.get("should_offer_scene_shift", False)),
            "scene_shift_reason": self._trim_summary_text(str(normalized_progress.get("scene_shift_reason", "")).strip(), 120),
            "world_tension_summary": self._trim_summary_text(str(normalized_progress.get("world_tension_summary", "")).strip(), 120),
        }
        progress_snapshot = {
            key: value
            for key, value in progress_snapshot.items()
            if value not in ("", [], False)
        }
        character_snapshots = {
            str(name).strip(): self._persona_snapshot_payload(dict(snapshot or {}), detailed=True)
            for name, snapshot in self._session_character_snapshots(session).items()
            if str(name).strip() and self._persona_snapshot_payload(dict(snapshot or {}), detailed=True)
        }
        relation_delta = {
            str(pair_key).strip(): {
                key: value
                for key, value in dict(delta or {}).items()
                if value not in ("", [], 0, None)
            }
            for pair_key, delta in self._session_relation_delta(session).items()
            if str(pair_key).strip()
        }
        relation_delta = {key: value for key, value in relation_delta.items() if value}
        event_signals = self._build_session_event_excerpt(session)
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
            "scene_progress": progress_snapshot,
            "character_snapshots": character_snapshots,
            "relation_delta": relation_delta,
            "event_signals": event_signals,
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
        session["scene_progress"] = self._session_scene_progress(session)
        session["relation_delta"] = self._session_relation_delta(session)
        session["character_snapshots"] = self._session_character_snapshots(session)
        session["event_signals"] = self._session_event_signals(session)
        session["relation_matrix"] = self._merged_relation_matrix(session, list(session.get("participants", []) or []))
        session["last_entry_preview"] = self._build_last_entry_preview(session)
        session["session_card"] = self._build_session_card(session)
        session["scene_history"] = self._serialize_scene_history(session)
        session["branch_origin"] = dict(session.get("branch_origin", {}) or {})
        session["pending_turn_summary"] = self._build_pending_turn_summary(session)
        session["session_memory_summary"] = self._build_session_memory_summary(run_id, session, transcript)
        session["runtime_state_overview"] = self._build_runtime_state_overview(session)
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

    def _build_runtime_state_overview(self, session: dict[str, Any]) -> dict[str, Any]:
        scene_progress = self._session_scene_progress(session)
        present = [
            str(item).strip()
            for item in list(scene_progress.get("present_participants", []) or [])
            if str(item).strip()
        ]
        offstage = [
            str(item).strip()
            for item in list(scene_progress.get("offstage_participants", []) or [])
            if str(item).strip()
        ]
        location = str(scene_progress.get("location", "")).strip()
        time_hint = str(scene_progress.get("time_hint", "")).strip()
        atmosphere = self._trim_summary_text(str(scene_progress.get("atmosphere_summary", "")).strip(), 80)
        beat_maturity = max(0, min(100, int(scene_progress.get("beat_maturity", 0) or 0)))
        should_offer_scene_shift = bool(scene_progress.get("should_offer_scene_shift", False))
        shift_reason = self._trim_summary_text(str(scene_progress.get("scene_shift_reason", "")).strip(), 120)
        tension = self._trim_summary_text(str(scene_progress.get("world_tension_summary", "")).strip(), 120)

        pills: list[dict[str, Any]] = []
        if location:
            pills.append({"text": f"地点 · {location}"})
        if time_hint:
            pills.append({"text": f"时间 · {time_hint}"})
        if atmosphere:
            pills.append({"text": f"氛围 · {atmosphere}"})
        if beat_maturity > 0:
            pills.append({"text": f"推进 {beat_maturity}/100"})
        if should_offer_scene_shift:
            pills.append({"text": f"可转场 · {shift_reason or '这一拍已经可以顺势转场'}"})

        character_rows: list[dict[str, Any]] = []
        for name, snapshot in self._session_character_snapshots(session).items():
            normalized_name = str(name).strip()
            if not normalized_name:
                continue
            current = dict(snapshot or {})
            parts: list[str] = []
            present_state = str(current.get("present_state", "")).strip()
            if present_state == "onstage":
                parts.append("在场")
            elif present_state == "offstage":
                parts.append("离场")
            for key in ("mood", "interaction_state"):
                value = str(current.get(key, "")).strip()
                if value:
                    parts.append(value)
            focus = str(current.get("focus", "")).strip()
            if focus:
                parts.append(f"看向 {focus}")
            character_rows.append(
                {
                    "title": normalized_name,
                    "copy": self._trim_summary_text(" · ".join(parts) or "这一拍还没有额外漂移。", 120),
                    "rank": 0 if present_state == "onstage" else 1,
                }
            )
        character_rows.sort(key=lambda item: (int(item.get("rank", 9) or 9), str(item.get("title", ""))))
        character_rows = [{"title": item["title"], "copy": item["copy"]} for item in character_rows[:4]]

        relation_rows: list[dict[str, Any]] = []
        for pair_key, delta in self._session_relation_delta(session).items():
            normalized_key = str(pair_key).strip()
            if not normalized_key:
                continue
            payload = dict(delta or {})
            metrics: list[str] = []
            momentum = int(payload.get("momentum", 0) or 0)
            for field, label in (("trust", "信任"), ("affection", "好感"), ("hostility", "敌意"), ("ambiguity", "摇摆")):
                amount = int(payload.get(field, 0) or 0)
                if amount:
                    metrics.append(f"{label}{amount:+d}")
            last_event = self._trim_summary_text(str(payload.get("last_event", "")).strip(), 72)
            relation_rows.append(
                {
                    "title": normalized_key.replace("_", " · "),
                    "copy": self._trim_summary_text(
                        f"{' / '.join(metrics)}{' · ' if metrics and last_event else ''}{last_event}".strip() or "这组关系本局有变化。",
                        120,
                    ),
                    "rank": max(momentum, len(metrics)),
                }
            )
        relation_rows.sort(key=lambda item: (-int(item.get("rank", 0) or 0), str(item.get("title", ""))))
        relation_rows = [{"title": item["title"], "copy": item["copy"]} for item in relation_rows[:3]]

        event_rows: list[dict[str, str]] = []
        for event in list(self._session_event_signals(session).get("recent", []) or [])[-4:]:
            payload = dict(event or {})
            kind = str(payload.get("kind", "")).strip()
            cue = self._trim_summary_text(str(payload.get("cue", "")).strip(), 88)
            if not kind or not cue:
                continue
            actor = str(payload.get("actor", "")).strip()
            target = str(payload.get("target", "")).strip()
            scope = str(payload.get("scope", "")).strip()
            title_bits = [self._event_kind_label(kind)]
            if actor:
                title_bits.append(actor)
            if target:
                title_bits.append(target)
            event_rows.append(
                {
                    "title": " · ".join(title_bits) if title_bits else (scope or "event"),
                    "copy": cue,
                }
            )

        status_bits: list[str] = []
        pill_texts = [str(item.get("text", "")).strip() for item in pills if str(item.get("text", "")).strip()]
        if pill_texts:
            status_bits.append(" · ".join(pill_texts[:3]))
        if present:
            status_bits.append(f"在场：{'、'.join(present[:3])}")
        if offstage:
            status_bits.append(f"离场：{'、'.join(offstage[:2])}")
        if tension:
            status_bits.append(f"张力：{self._trim_summary_text(tension, 56)}")
        status_line = " ｜ ".join(status_bits)

        next_hint = ""
        if should_offer_scene_shift:
            next_hint = shift_reason or "这一拍已经可以顺势转场。"
        elif tension:
            next_hint = self._trim_summary_text(tension, 72)
        elif event_rows:
            next_hint = self._trim_summary_text(str(event_rows[-1].get("copy", "")).strip(), 72)

        return {
            "present": present,
            "offstage": offstage,
            "location": location,
            "time_hint": time_hint,
            "atmosphere": atmosphere,
            "beat_maturity": beat_maturity,
            "should_offer_scene_shift": should_offer_scene_shift,
            "scene_shift_reason": shift_reason,
            "tension": tension,
            "pills": pills,
            "character_rows": character_rows,
            "relation_rows": relation_rows,
            "event_rows": event_rows,
            "status_line": status_line,
            "next_hint": next_hint,
        }

    @staticmethod
    def _event_kind_label(kind: str) -> str:
        mapping = {
            "scene_transition": "转场",
            "cast_enter": "入场",
            "cast_exit": "离场",
            "atmosphere_shift": "气氛变化",
            "time_change": "时间推进",
            "environment_change": "环境变化",
            "beat_complete": "一拍收束",
            "relationship_shift": "关系变化",
            "micro_action": "细微动作",
        }
        normalized = str(kind or "").strip()
        return mapping.get(normalized, normalized or "事件")

    def _build_session_memory_summary(self, run_id: str, session: dict[str, Any], transcript: list[dict[str, Any]]) -> dict[str, str]:
        mode = str(session.get("mode", "observe")).strip() or "observe"
        mode_display = self._mode_display(mode)
        participants = [str(item).strip() for item in session.get("participants", []) if str(item).strip()]
        history = list(session.get("history", []) or [])
        scene_progress = self._session_scene_progress(session)
        present_participants = [
            str(item).strip()
            for item in list(scene_progress.get("present_participants", []) or [])
            if str(item).strip()
        ]
        offstage_participants = [
            str(item).strip()
            for item in list(scene_progress.get("offstage_participants", []) or [])
            if str(item).strip()
        ]
        time_hint = str(scene_progress.get("time_hint", "")).strip()
        progress_location = str(scene_progress.get("location", "")).strip()
        progression_note = str(scene_progress.get("progression_note", "")).strip()
        shift_reason = str(scene_progress.get("scene_shift_reason", "")).strip()

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
        if present_participants:
            cast = f"当前主要在场：{'、'.join(present_participants[:5])}{'...' if len(present_participants) > 5 else ''}"
            if offstage_participants:
                cast = f"{cast}；暂时离场：{'、'.join(offstage_participants[:3])}"
        elif cast_speakers:
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
        if time_hint:
            perspective = f"{perspective} 当前时间已经推进到「{time_hint}」。"

        world = "当前局势里的动作与情绪线会在这里提醒你。"
        world_tension_summary = str(scene_progress.get("world_tension_summary", "")).strip()
        if world_tension_summary:
            world = self._trim_summary_text(world_tension_summary, 88)
        elif progression_note:
            world = self._trim_summary_text(progression_note, 88)
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
        relation_delta = self._session_relation_delta(session)
        if relation_delta:
            delta_bits: list[str] = []
            for pair_key, delta in list(relation_delta.items())[:3]:
                metric_bits = []
                for field, label in (("trust", "信任"), ("affection", "好感"), ("hostility", "敌意"), ("ambiguity", "摇摆")):
                    change = int(dict(delta or {}).get(field, 0) or 0)
                    if change:
                        metric_bits.append(f"{label}{change:+d}")
                if metric_bits:
                    delta_bits.append(f"{pair_key}({','.join(metric_bits)})")
            if delta_bits:
                relation = f"{relation} · 本局变化：{'；'.join(delta_bits)}"

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
                progress_location or str(scene_card.get("location", "")).strip(),
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
        if time_hint:
            scene_frame = f"{scene_frame} · 当前时间：{time_hint}"
        if shift_reason:
            scene_frame = f"{scene_frame} · 转场提示：{self._trim_summary_text(shift_reason, 48)}"

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
