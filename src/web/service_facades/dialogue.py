from __future__ import annotations

from typing import Any

from src.web.service_facades.scene_cards import SceneCardServiceMixin
from src.web.chat import (
    build_dialogue_llm_messages,
    build_dialogue_relation_state_messages,
    build_dialogue_scene_progress_messages,
    build_dialogue_suggestion_llm_messages,
    build_dialogue_opening_message,
    compact_dialogue_suggestion_payload,
    create_dialogue_session_payload,
    friendly_dialogue_llm_error,
    generate_dialogue_suggestion,
    generate_dialogue_responses,
    generate_dialogue_responses_for_run,
    generate_dialogue_suggestion_for_run,
    parse_dialogue_scene_progress,
    parse_dialogue_suggestion,
    parse_dialogue_responses,
    parse_dialogue_relation_state,
    reply_dialogue_turn_payload,
    should_retry_suggestion_with_compact_payload,
    suggest_dialogue_turn_payload,
)


def build_runtime_parts(config: Any) -> Any:
    from src.web.workflow import WebRunService

    return WebRunService._build_runtime_parts(config)


class DialogueServiceMixin:
    def list_dialogue_sessions(self, run_id: str) -> list[dict[str, Any]]:
        self._ensure_run_exists(run_id)
        return self.dialogue.list_sessions(run_id)

    def create_dialogue_session(
        self,
        run_id: str,
        *,
        mode: str,
        participants: list[str],
        controlled_character: str = "",
        scene_card_id: str = "",
        scene_profile: dict[str, str] | None = None,
        self_card_id: str = "",
        self_profile: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        resolved_scene_profile = dict(scene_profile or {})
        if scene_card_id:
            try:
                card = self.get_scene_card(scene_card_id)
            except FileNotFoundError as exc:
                raise ValueError("所选场景卡不存在。") from exc
            resolved_scene_profile = {
                **dict(card.get("fields", {}) or {}),
                **resolved_scene_profile,
                "scene_card_id": str(card.get("card_id", "")).strip(),
            }
        resolved_self_profile = dict(self_profile or {})
        if mode == "insert" and self_card_id:
            try:
                card = self.get_self_card(self_card_id)
            except FileNotFoundError as exc:
                raise ValueError("所选角色卡不存在。") from exc
            resolved_self_profile = {
                **dict(card.get("fields", {}) or {}),
                **resolved_self_profile,
                "self_card_id": str(card.get("card_id", "")).strip(),
            }
        return create_dialogue_session_payload(
            run_id=run_id,
            manifest=manifest,
            dialogue=self.dialogue,
            mode=mode,
            participants=participants,
            controlled_character=controlled_character,
            scene_profile=resolved_scene_profile,
            self_profile=resolved_self_profile,
            build_dialogue_opening_message=build_dialogue_opening_message,
            load_pending_turn_payload=self._load_pending_turn_payload,
            generate_dialogue_responses=self._generate_dialogue_responses,
            friendly_dialogue_llm_error=friendly_dialogue_llm_error,
            evolve_relations_from_turn=self._evolve_relations_from_turn,
            refresh_scene_progress=self._refresh_dialogue_scene_progress,
        )

    def get_dialogue_session(self, run_id: str, session_id: str) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        return self.dialogue.get_session(run_id, session_id)

    def branch_dialogue_session_from_scene(self, run_id: str, *, session_id: str, scene_index: int) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        return self.dialogue.branch_session_from_scene(
            manifest,
            session_id,
            scene_index=scene_index,
        )

    def switch_dialogue_scene_card(
        self,
        run_id: str,
        *,
        session_id: str,
        scene_card_id: str = "",
        scene_profile: dict[str, str] | None = None,
        transition_message: str = "",
    ) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        resolved_scene_profile = dict(scene_profile or {})
        if scene_card_id:
            try:
                card = self.get_scene_card(scene_card_id)
            except FileNotFoundError as exc:
                raise ValueError("所选场景卡不存在。") from exc
            resolved_scene_profile = {
                **dict(card.get("fields", {}) or {}),
                **resolved_scene_profile,
                "scene_card_id": str(card.get("card_id", "")).strip(),
            }
        return self.dialogue.update_scene_card(
            run_id,
            session_id,
            scene_profile=resolved_scene_profile,
            transition_message=transition_message,
        )

    def recommend_dialogue_scene_card(self, run_id: str, *, session_id: str) -> dict[str, Any]:
        return SceneCardServiceMixin.recommend_dialogue_scene_card(self, run_id, session_id=session_id)

    def delete_dialogue_session(self, run_id: str, session_id: str) -> None:
        self._ensure_run_exists(run_id)
        self.dialogue.delete_session(run_id, session_id)

    def prepare_dialogue_turn(
        self,
        run_id: str,
        *,
        session_id: str,
        message: str,
        message_kind: str = "dialogue",
    ) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        return self.dialogue.prepare_turn(
            manifest,
            session_id=session_id,
            message=message,
            message_kind=message_kind,
        )

    def reply_dialogue_turn(
        self,
        run_id: str,
        *,
        session_id: str,
        message: str,
        message_kind: str = "dialogue",
    ) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        return reply_dialogue_turn_payload(
            run_id=run_id,
            session_id=session_id,
            message=message,
            message_kind=message_kind,
            manifest=manifest,
            dialogue=self.dialogue,
            load_pending_turn_payload=self._load_pending_turn_payload,
            generate_dialogue_responses=self._generate_dialogue_responses,
            friendly_dialogue_llm_error=friendly_dialogue_llm_error,
            evolve_relations_from_turn=self._evolve_relations_from_turn,
            refresh_scene_progress=self._refresh_dialogue_scene_progress,
        )

    def suggest_dialogue_turn(self, run_id: str, *, session_id: str, seed_text: str = "") -> dict[str, str]:
        manifest = self._require_manifest(run_id)
        return suggest_dialogue_turn_payload(
            run_id=run_id,
            session_id=session_id,
            seed_text=seed_text,
            manifest=manifest,
            dialogue=self.dialogue,
            generate_dialogue_suggestion=self._generate_dialogue_suggestion,
            friendly_dialogue_llm_error=friendly_dialogue_llm_error,
        )

    def ingest_dialogue_turn(
        self,
        run_id: str,
        *,
        session_id: str,
        responses: list[dict[str, str]],
    ) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        session = self.dialogue.ingest_turn_responses(
            run_id,
            session_id=session_id,
            responses=responses,
            remember_turn_memory=True,
        )
        return self._refresh_dialogue_scene_progress(run_id, session)

    def _generate_dialogue_responses(self, run_id: str, payload: dict[str, Any]) -> list[dict[str, str]]:
        return generate_dialogue_responses_for_run(
            run_dir=self.runs_root / run_id,
            payload=payload,
            build_runtime_config_for_run=self._build_runtime_config_for_run,
            build_runtime_parts=build_runtime_parts,
            generate_dialogue_responses=generate_dialogue_responses,
            build_dialogue_llm_messages=lambda current_payload, retry_on_empty: self._build_dialogue_llm_messages(
                current_payload,
                retry_on_empty=retry_on_empty,
            ),
            parse_dialogue_responses=self._parse_dialogue_responses,
        )

    def _generate_dialogue_suggestion(self, run_id: str, payload: dict[str, Any]) -> str:
        try:
            return generate_dialogue_suggestion_for_run(
                run_dir=self.runs_root / run_id,
                payload=payload,
                build_runtime_config_for_run=self._build_runtime_config_for_run,
                build_runtime_parts=build_runtime_parts,
                generate_dialogue_suggestion=generate_dialogue_suggestion,
                build_dialogue_suggestion_llm_messages=lambda current_payload, retry_on_empty: self._build_dialogue_suggestion_llm_messages(
                    current_payload,
                    retry_on_empty=retry_on_empty,
                ),
                parse_dialogue_suggestion=self._parse_dialogue_suggestion,
            )
        except Exception as exc:
            if not should_retry_suggestion_with_compact_payload(exc):
                raise
            compact_payload = compact_dialogue_suggestion_payload(payload)
            return generate_dialogue_suggestion_for_run(
                run_dir=self.runs_root / run_id,
                payload=compact_payload,
                build_runtime_config_for_run=self._build_runtime_config_for_run,
                build_runtime_parts=build_runtime_parts,
                generate_dialogue_suggestion=generate_dialogue_suggestion,
                build_dialogue_suggestion_llm_messages=lambda current_payload, retry_on_empty: self._build_dialogue_suggestion_llm_messages(
                    current_payload,
                    retry_on_empty=retry_on_empty,
                ),
                parse_dialogue_suggestion=self._parse_dialogue_suggestion,
            )

    @staticmethod
    def _build_dialogue_llm_messages(payload: dict[str, Any], *, retry_on_empty: bool = False) -> list[dict[str, str]]:
        return build_dialogue_llm_messages(payload, retry_on_empty=retry_on_empty)

    @staticmethod
    def _build_dialogue_suggestion_llm_messages(
        payload: dict[str, Any],
        *,
        retry_on_empty: bool = False,
    ) -> list[dict[str, str]]:
        return build_dialogue_suggestion_llm_messages(payload, retry_on_empty=retry_on_empty)

    @staticmethod
    def _parse_dialogue_responses(content: str, allowed_speakers: list[str]) -> list[dict[str, str]]:
        return parse_dialogue_responses(content, allowed_speakers)

    @staticmethod
    def _parse_dialogue_suggestion(content: str) -> str:
        return parse_dialogue_suggestion(content)

    def _refresh_dialogue_scene_progress(self, run_id: str, session: dict[str, Any]) -> dict[str, Any]:
        session_id = str((session or {}).get("session_id", "")).strip()
        if not session_id:
            return session
        try:
            generated = self._generate_dialogue_scene_progress(run_id, session)
        except Exception:
            generated = {}
        try:
            return self.dialogue.update_scene_progress_state(
                run_id,
                session_id,
                scene_progress=dict(generated or {}),
            )
        except Exception:
            return session

    def _generate_dialogue_scene_progress(self, run_id: str, session: dict[str, Any]) -> dict[str, Any]:
        participants = [str(item).strip() for item in list((session or {}).get("participants", []) or []) if str(item).strip()]
        if not participants:
            return {}
        config = self._build_runtime_config_for_run(run_dir=self.runs_root / run_id)
        if not self._should_use_scene_progress_llm(config, session):
            return {}
        parts = build_runtime_parts(config)
        if not hasattr(parts.llm, "chat_completion"):
            return {}

        payload = dict(session or {})
        payload["scene_progress"] = dict(payload.get("scene_progress", {}) or payload.get("state", {}).get("scene_progress", {}) or {})
        attempts = (
            build_dialogue_scene_progress_messages(payload),
            [
                *build_dialogue_scene_progress_messages(payload),
                {
                    "role": "user",
                    "content": "上一次输出不够稳定。请重新只返回完整 JSON，不要解释，不要 markdown。",
                },
            ],
        )
        last_error: Exception | None = None
        for messages in attempts:
            try:
                result = parts.llm.chat_completion(
                    messages,
                    temperature=0.1,
                    max_tokens=min(int(config.get("llm.max_tokens", 240) or 240), 240),
                )
                content = str((result or {}).get("content", "")).strip()
                if not content:
                    last_error = ValueError("empty scene progress")
                    continue
                return parse_dialogue_scene_progress(content, participants)
            except Exception as exc:
                last_error = exc
                continue
        if last_error is not None:
            return {}
        return {}

    @staticmethod
    def _should_use_scene_progress_llm(config: Any, session: dict[str, Any]) -> bool:
        transcript = list((session or {}).get("transcript", []) or [])
        history = list((session or {}).get("history", []) or [])
        if len(transcript) < 4 and len(history) < 4:
            return False
        base_url = str(config.get("llm.base_url", "") or "").strip().lower()
        api_key = str(config.get("llm.api_key", "") or "").strip().lower()
        if "example.com" in base_url:
            return False
        if api_key in {"sk-test", "test", "dummy", "placeholder"}:
            return False
        return True

    def _evolve_relations_from_turn(
        self,
        run_id: str,
        pending_payload: dict[str, Any],
        responses: list[dict[str, str]],
    ) -> None:
        if not responses:
            return
        try:
            session_id = str(pending_payload.get("session_id", "")).strip()
            if not session_id:
                return
            session_path = self.dialogue._session_file(run_id, session_id)
            session = self.dialogue._read_json(session_path)
            state = dict(session.get("state", {}) or {})
            relation_delta = dict(state.get("relation_delta", {}) or {})
            character_snapshots = dict(state.get("character_snapshots", {}) or {})
            event_signals = dict(state.get("event_signals", {}) or self.dialogue._empty_event_signals_state())
            input_block = dict(pending_payload.get("input", {}) or {})
            speaker = str(input_block.get("speaker", "")).strip()
            participants = [str(item).strip() for item in input_block.get("participants", []) if str(item).strip()]
            active = [str(item).strip() for item in input_block.get("active_participants", []) if str(item).strip()]
            candidates = active or participants
            pending_message = str(input_block.get("message", "")).strip()
            pending_kind = str(input_block.get("message_kind", "")).strip() or "dialogue"
            detected_events: list[dict[str, Any]] = []
            detected_events.extend(
                self._extract_dialogue_event_signals(
                    participants=participants,
                    speaker=speaker,
                    message=pending_message,
                    source="pending_input",
                    message_kind=pending_kind,
                    target="",
                )
            )

            for reply in responses:
                responder = str(reply.get("speaker", "")).strip()
                message = str(reply.get("message", "")).strip()
                if not responder or not message:
                    continue
                target = speaker
                if not target or target in {"User", "场景提示", "旁白"}:
                    pool = [name for name in candidates if name and name != responder]
                    target = pool[0] if pool else ""
                if target and target != responder:
                    key = self.dialogue._pair_key(responder, target)
                    current = dict(relation_delta.get(key, {}) or {})
                    delta = self._infer_relation_delta_from_message(message)
                    for field, amount in delta.items():
                        if field not in {"trust", "affection", "hostility", "ambiguity"} or not amount:
                            continue
                        current[field] = int(current.get(field, 0) or 0) + int(amount)
                    current["last_event"] = message[:220]
                    evidence_lines = list(current.get("evidence_lines", []) or [])
                    evidence_lines.append(f"{responder}->{target}: {message}"[:220])
                    current["evidence_lines"] = evidence_lines[-10:]
                    current["updated_at"] = session.get("updated_at", "")
                    relation_delta[key] = current
                    if any(int(current.get(field, 0) or 0) for field in ("trust", "affection", "hostility", "ambiguity")):
                        detected_events.append(
                            {
                                "kind": "relationship_shift",
                                "scope": "relationship",
                                "actor": responder,
                                "target": target,
                                "cue": message[:160],
                                "source": "response",
                                "should_inline": False,
                                "ts": session.get("updated_at", "") or "",
                            }
                        )

                if responder in {"旁白", "场景提示"}:
                    self._update_offstage_snapshots_from_narration(
                        participants=participants,
                        message=message,
                        character_snapshots=character_snapshots,
                    )
                else:
                    snapshot = dict(character_snapshots.get(responder, {}) or {})
                    snapshot.update(self._infer_character_snapshot(responder=responder, target=target, message=message))
                    character_snapshots[responder] = snapshot

                detected_events.extend(
                    self._extract_dialogue_event_signals(
                        participants=participants,
                        speaker=responder,
                        message=message,
                        source="response",
                        message_kind="narration" if responder in {"旁白", "场景提示"} else "dialogue",
                        target=target,
                    )
                )

            refined_state = self._generate_dialogue_relation_state(
                run_id,
                session=session,
                pending_payload=pending_payload,
                responses=responses,
                relation_delta=relation_delta,
                character_snapshots=character_snapshots,
            )
            relation_delta = self._merge_relation_delta(
                relation_delta,
                dict(refined_state.get("relation_delta", {}) or {}),
            )
            character_snapshots = self._merge_character_snapshots(
                character_snapshots,
                dict(refined_state.get("character_snapshots", {}) or {}),
            )
            event_signals = self.dialogue._merge_event_signals_state(
                session,
                detected_events,
            )

            session.setdefault("state", {})["relation_delta"] = relation_delta
            session.setdefault("state", {})["character_snapshots"] = character_snapshots
            session.setdefault("state", {})["event_signals"] = event_signals
            session["updated_at"] = session.get("updated_at") or ""
            self.dialogue._write_json(session_path, session)
            store = self.dialogue._resolve_memory_store(run_id)
            if store is not None:
                try:
                    store.save_relation_snapshot(session)
                except Exception:
                    pass
        except Exception:
            return

    def _generate_dialogue_relation_state(
        self,
        run_id: str,
        *,
        session: dict[str, Any],
        pending_payload: dict[str, Any],
        responses: list[dict[str, str]],
        relation_delta: dict[str, Any],
        character_snapshots: dict[str, Any],
    ) -> dict[str, Any]:
        participants = [str(item).strip() for item in list((session or {}).get("participants", []) or []) if str(item).strip()]
        if not participants:
            return {}
        config = self._build_runtime_config_for_run(run_dir=self.runs_root / run_id)
        if not self._should_use_scene_progress_llm(config, session):
            return {}
        parts = build_runtime_parts(config)
        if not hasattr(parts.llm, "chat_completion"):
            return {}

        payload = dict(session or {})
        payload.setdefault("state", {})
        payload["state"] = dict(payload.get("state", {}) or {})
        payload["state"]["relation_delta"] = dict(relation_delta or {})
        payload["state"]["character_snapshots"] = dict(character_snapshots or {})
        attempts = (
            build_dialogue_relation_state_messages(payload, pending_payload, responses),
            [
                *build_dialogue_relation_state_messages(payload, pending_payload, responses),
                {
                    "role": "user",
                    "content": "请重新只返回完整 JSON，并且仅做轻量修正，不要重写全部状态。",
                },
            ],
        )
        for messages in attempts:
            try:
                result = parts.llm.chat_completion(
                    messages,
                    temperature=0.1,
                    max_tokens=min(int(config.get("llm.max_tokens", 320) or 320), 320),
                )
                content = str((result or {}).get("content", "")).strip()
                if not content:
                    continue
                return parse_dialogue_relation_state(content, participants)
            except Exception:
                continue
        return {}

    @staticmethod
    def _merge_relation_delta(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = {str(key).strip(): dict(value or {}) for key, value in dict(base or {}).items() if str(key).strip()}
        for key, value in dict(incoming or {}).items():
            normalized_key = str(key).strip()
            if not normalized_key:
                continue
            current = dict(merged.get(normalized_key, {}) or {})
            next_value = dict(value or {})
            for field in ("trust", "affection", "hostility", "ambiguity"):
                if field in next_value:
                    try:
                        current[field] = int(next_value.get(field, 0) or 0)
                    except Exception:
                        pass
            for field in ("last_event", "relation_change", "typical_interaction"):
                text = str(next_value.get(field, "")).strip()
                if text:
                    current[field] = text
            evidence_lines = [
                str(item).strip()
                for item in list(next_value.get("evidence_lines", []) or [])
                if str(item).strip()
            ]
            if evidence_lines:
                current["evidence_lines"] = evidence_lines[:10]
            if current:
                merged[normalized_key] = current
        return merged

    @staticmethod
    def _merge_character_snapshots(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = {str(key).strip(): dict(value or {}) for key, value in dict(base or {}).items() if str(key).strip()}
        for key, value in dict(incoming or {}).items():
            normalized_key = str(key).strip()
            if not normalized_key:
                continue
            current = dict(merged.get(normalized_key, {}) or {})
            for field, raw in dict(value or {}).items():
                text = str(raw).strip()
                if text:
                    current[field] = text
            if current:
                merged[normalized_key] = current
        return merged

    def _extract_dialogue_event_signals(
        self,
        *,
        participants: list[str],
        speaker: str,
        message: str,
        source: str,
        message_kind: str,
        target: str,
    ) -> list[dict[str, Any]]:
        text = str(message or "").strip()
        if not text:
            return []
        compact = "".join(text.split())
        is_scene_level = str(message_kind or "").strip() == "narration" or speaker in {"旁白", "场景提示"}
        events: list[dict[str, Any]] = []

        def push(
            kind: str,
            cue: str,
            *,
            scope: str,
            actor: str = "",
            target_name: str = "",
            should_inline: bool = False,
            time_hint: str = "",
            location_hint: str = "",
        ) -> None:
            normalized_cue = str(cue or "").strip()
            if not kind or not normalized_cue:
                return
            event = {
                "kind": kind,
                "scope": scope,
                "actor": actor,
                "target": target_name,
                "cue": normalized_cue[:160],
                "source": source,
                "should_inline": should_inline,
                "ts": "",
            }
            if time_hint:
                event["time_hint"] = time_hint
            if location_hint:
                event["location_hint"] = location_hint
            events.append(event)

        time_hint = self.dialogue._infer_time_hint([{"message": text}])
        if time_hint:
            push("time_change", f"时间推进到{time_hint}", scope="scene", actor=speaker if is_scene_level else "", time_hint=time_hint)

        if any(token in text for token in self.dialogue._ENVIRONMENT_TOKENS):
            push("environment_change", text, scope="scene")
        if any(token in text for token in self.dialogue._ATMOSPHERE_TOKENS):
            push("atmosphere_shift", text, scope="scene")

        if any(token in compact for token in self.dialogue._SCENE_ENTER_TOKENS + self.dialogue._SCENE_EXIT_TOKENS):
            push("scene_transition", text, scope="scene", location_hint=self._extract_location_hint(text))

        for name in participants:
            if name not in text:
                continue
            if self.dialogue._contains_leave_signal(text, name):
                push("cast_exit", f"{name}离场", scope="scene", actor=name)
            elif self.dialogue._contains_return_signal(text, name):
                push("cast_enter", f"{name}返场", scope="scene", actor=name)

        if not is_scene_level and any(token in text for token in self.dialogue._ACTION_TOKENS):
            push("micro_action", text, scope="character", actor=speaker, target_name=target, should_inline=True)

        if any(token in text for token in ("说开了", "到这里", "该换个地方", "该走下一幕", "下一幕", "先到这", "这幕先收住", "可以转到")):
            push("beat_complete", text, scope="scene")

        if not is_scene_level and target and any(token in text for token in ("只你我", "单独", "私下", "我们两个", "随我来", "跟我走", "留下")):
            push("focus_shift", text, scope="relationship", actor=speaker, target_name=target)

        return events

    @staticmethod
    def _extract_location_hint(text: str) -> str:
        value = str(text or "").strip()
        matchers = ("花厅", "回廊", "偏厅", "房中", "屋里", "门外", "院中", "亭下", "船上", "私人影院", "影院", "家里")
        for item in matchers:
            if item in value:
                return item
        return ""

    @staticmethod
    def _infer_relation_delta_from_message(message: str) -> dict[str, int]:
        text = str(message or "").strip()
        delta = {"trust": 0, "affection": 0, "hostility": 0, "ambiguity": 0}
        if any(token in text for token in ("谢谢", "抱歉", "理解", "关心", "在意", "一起", "陪你", "我陪", "别怕", "护着")):
            delta["trust"] += 1
            delta["affection"] += 1
            delta["hostility"] -= 1
        if any(token in text for token in ("滚", "讨厌", "厌恶", "闭嘴", "烦", "恨", "威胁", "不想见")):
            delta["hostility"] += 2
            delta["trust"] -= 1
            delta["affection"] -= 2
        if any(token in text for token in ("也许", "或许", "未必", "再说", "以后再议", "说不好")):
            delta["ambiguity"] += 1
        if any(token in text for token in ("算了", "就这样吧", "告辞", "先走一步", "改日")):
            delta["ambiguity"] += 1
        return delta

    def _update_offstage_snapshots_from_narration(
        self,
        *,
        participants: list[str],
        message: str,
        character_snapshots: dict[str, Any],
    ) -> None:
        for name in participants:
            if name not in message:
                continue
            snapshot = dict(character_snapshots.get(name, {}) or {})
            if self.dialogue._contains_leave_signal(message, name):
                snapshot.update(
                    {
                        "mood": str(snapshot.get("mood", "")).strip() or "收住",
                        "interaction_state": "offstage",
                        "focus": "离场",
                        "last_event": message[:220],
                    }
                )
            elif self.dialogue._contains_return_signal(message, name):
                snapshot.update(
                    {
                        "interaction_state": "re-entered",
                        "focus": "返场",
                        "last_event": message[:220],
                    }
                )
            if snapshot:
                character_snapshots[name] = snapshot

    @staticmethod
    def _infer_character_snapshot(*, responder: str, target: str, message: str) -> dict[str, str]:
        text = str(message or "").strip()
        mood = "平稳"
        if any(token in text for token in ("笑", "松了口气", "安心", "轻快", "温和")):
            mood = "放松"
        elif any(token in text for token in ("怒", "恼", "气", "烦", "冷", "厌")):
            mood = "发紧"
        elif any(token in text for token in ("愣", "怔", "沉默", "顿住", "迟疑")):
            mood = "迟疑"

        interaction_state = "engaged"
        if any(token in text for token in ("先走", "告退", "回房", "回家", "离开", "改日")):
            interaction_state = "withdrawing"
        elif any(token in text for token in ("谢谢", "抱歉", "理解", "关心", "陪你")):
            interaction_state = "softening"
        elif any(token in text for token in ("滚", "闭嘴", "讨厌", "恨")):
            interaction_state = "hostile"

        focus = target or responder
        return {
            "mood": mood,
            "interaction_state": interaction_state,
            "focus": focus,
            "last_target": target,
            "last_message": text[:180],
            "last_event": text[:220],
        }

    def _dialogue_memory_store_for_run(self, run_id: str) -> Any:
        config = self._build_runtime_config_for_run(run_dir=self.runs_root / run_id)
        parts = self._build_runtime_parts(config)
        return parts.session_store
