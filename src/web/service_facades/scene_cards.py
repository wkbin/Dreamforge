from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.skill_support.scene_recommendations import build_scene_recommendation_bundle
from src.web.artifacts import load_profile_source, render_profile_md
from src.web.review import (
    build_random_scene_card_messages,
    delete_scene_card_payload,
    list_scene_cards_payload,
    load_scene_card_payload,
    parse_random_scene_card_response,
    recommend_scene_cards,
    save_scene_card_payload,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class SceneCardServiceMixin:
    def list_scene_cards(self) -> list[dict[str, Any]]:
        return list_scene_cards_payload(
            self.scene_cards_root,
            load_profile_source=load_profile_source,
        )

    def get_scene_card(self, card_id: str) -> dict[str, Any]:
        return load_scene_card_payload(
            self.scene_cards_root,
            card_id,
            load_profile_source=load_profile_source,
        )

    def save_scene_card(self, *, card_id: str = "", fields: dict[str, Any]) -> dict[str, Any]:
        payload = save_scene_card_payload(
            self.scene_cards_root,
            card_id=card_id,
            fields=fields,
            render_profile_md=render_profile_md,
            utc_now=_utc_now,
        )
        return self.get_scene_card(payload["card_id"])

    def delete_scene_card(self, card_id: str) -> dict[str, str]:
        return delete_scene_card_payload(self.scene_cards_root, card_id)

    def generate_scene_card(self) -> dict[str, Any]:
        if not self.model_is_configured():
            raise ValueError("Model is not configured yet.")
        config = self._build_runtime_config_for_run(run_dir=self.storage_root)
        parts = self._build_runtime_parts(config)
        llm_result = parts.llm.chat_completion(
            build_random_scene_card_messages(),
            temperature=0.95,
            max_tokens=1600,
        )
        fields = parse_random_scene_card_response(str(llm_result.get("content", "")))
        return {
            "fields": fields,
            "preview": {
                "title": fields["title"],
                "time_hint": fields["time_hint"],
                "location": fields["location"],
                "atmosphere": fields["atmosphere"],
                "opening_situation": fields["opening_situation"],
                "scene_drive": fields["scene_drive"],
                "expected_rhythm": fields["expected_rhythm"],
            },
        }

    def recommend_scene_cards(self, *, mode: str, participants: list[str] | None = None) -> dict[str, Any]:
        cards = self.list_scene_cards()
        return recommend_scene_cards(cards, mode=mode, participants=participants or [])

    def recommend_dialogue_scene_card(self, run_id: str, *, session_id: str) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        session = self.dialogue.get_session(run_id, session_id)
        cards = self.list_scene_cards()
        mode = str(session.get("mode", "") or session.get("session_card", {}).get("mode", "observe")).strip() or "observe"
        participants = list(session.get("session_card", {}).get("participants", []) or [])
        current_scene = dict(session.get("session_card", {}).get("scene_card", {}) or {})
        runtime_overview = dict(session.get("runtime_state_overview", {}) or {})
        current_scene_id = str(session.get("session_card", {}).get("scene_card_id", "")).strip()
        recent_text = "\n".join(
            str(item.get("message", "")).strip()
            for item in list(session.get("transcript", []) or [])[-6:]
            if str(item.get("message", "")).strip()
        )
        bundle = build_scene_recommendation_bundle(
            {
                "mode": mode,
                "participants": participants,
                "scene_cards": cards,
                "current_scene": current_scene,
                "current_scene_card_id": current_scene_id,
                "runtime_state_overview": runtime_overview,
                "recent_text": recent_text,
                "controlled_character": str(session.get("controlled_character", "")).strip(),
                "self_profile": dict(session.get("self_insert", {}) or {}),
            }
        )
        return dict(bundle.get("payload", {}) or {})
