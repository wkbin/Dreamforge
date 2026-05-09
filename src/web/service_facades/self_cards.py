from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.web.artifacts import load_profile_source, render_profile_md
from src.web.review import (
    build_random_self_card_messages,
    list_self_cards_payload,
    load_self_card_payload,
    parse_random_self_card_response,
    read_persona_review_fields,
    save_self_card_payload,
    delete_self_card_payload,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class SelfCardServiceMixin:
    def list_self_cards(self) -> list[dict[str, Any]]:
        return list_self_cards_payload(
            self.self_cards_root,
            load_profile_source=load_profile_source,
            read_persona_review_fields=read_persona_review_fields,
        )

    def get_self_card(self, card_id: str) -> dict[str, Any]:
        return load_self_card_payload(
            self.self_cards_root,
            card_id,
            load_profile_source=load_profile_source,
            read_persona_review_fields=read_persona_review_fields,
        )

    def save_self_card(self, *, card_id: str = "", fields: dict[str, Any]) -> dict[str, Any]:
        payload = save_self_card_payload(
            self.self_cards_root,
            card_id=card_id,
            fields=fields,
            render_profile_md=render_profile_md,
            utc_now=_utc_now,
        )
        return self.get_self_card(payload["card_id"])

    def delete_self_card(self, card_id: str) -> dict[str, str]:
        return delete_self_card_payload(self.self_cards_root, card_id)

    def generate_self_card(self) -> dict[str, Any]:
        if not self.model_is_configured():
            raise ValueError("Model is not configured yet.")
        config = self._build_runtime_config_for_run(run_dir=self.storage_root)
        parts = self._build_runtime_parts(config)
        llm_result = parts.llm.chat_completion(
            build_random_self_card_messages(),
            temperature=0.9,
            max_tokens=2200,
        )
        fields = parse_random_self_card_response(str(llm_result.get("content", "")))
        return {
            "fields": fields,
            "preview": {
                "display_name": fields["display_name"],
                "scene_identity": fields["scene_identity"],
                "core_identity": fields["core_identity"],
                "story_role": fields["story_role"],
                "temperament_type": fields["temperament_type"],
                "speech_style": fields["speech_style"],
                "soul_goal": fields["soul_goal"],
            },
        }
