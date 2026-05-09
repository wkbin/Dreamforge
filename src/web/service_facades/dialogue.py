from __future__ import annotations

from typing import Any

from src.core.runtime_factory import build_runtime_parts
from src.web.chat import (
    build_dialogue_llm_messages,
    build_dialogue_suggestion_llm_messages,
    build_dialogue_opening_message,
    create_dialogue_session_payload,
    friendly_dialogue_llm_error,
    generate_dialogue_suggestion,
    generate_dialogue_responses,
    generate_dialogue_responses_for_run,
    generate_dialogue_suggestion_for_run,
    parse_dialogue_suggestion,
    parse_dialogue_responses,
    reply_dialogue_turn_payload,
    suggest_dialogue_turn_payload,
)


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
        self_card_id: str = "",
        self_profile: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
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
            self_profile=resolved_self_profile,
            build_dialogue_opening_message=build_dialogue_opening_message,
            load_pending_turn_payload=self._load_pending_turn_payload,
            generate_dialogue_responses=self._generate_dialogue_responses,
            friendly_dialogue_llm_error=friendly_dialogue_llm_error,
        )

    def get_dialogue_session(self, run_id: str, session_id: str) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        return self.dialogue.get_session(run_id, session_id)

    def delete_dialogue_session(self, run_id: str, session_id: str) -> None:
        self._ensure_run_exists(run_id)
        self.dialogue.delete_session(run_id, session_id)

    def prepare_dialogue_turn(self, run_id: str, *, session_id: str, message: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        return self.dialogue.prepare_turn(manifest, session_id=session_id, message=message)

    def reply_dialogue_turn(self, run_id: str, *, session_id: str, message: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        return reply_dialogue_turn_payload(
            run_id=run_id,
            session_id=session_id,
            message=message,
            manifest=manifest,
            dialogue=self.dialogue,
            load_pending_turn_payload=self._load_pending_turn_payload,
            generate_dialogue_responses=self._generate_dialogue_responses,
            friendly_dialogue_llm_error=friendly_dialogue_llm_error,
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
        return self.dialogue.ingest_turn_responses(run_id, session_id=session_id, responses=responses)

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
