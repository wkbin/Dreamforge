from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.file_utils import save_markdown_data
from src.web.artifacts.ingest import load_relations_source
from src.web.chat import (
    build_dialogue_llm_messages,
    build_dialogue_suggestion_llm_messages,
    build_dialogue_opening_message,
    compact_dialogue_suggestion_payload,
    create_dialogue_session_payload,
    friendly_dialogue_llm_error,
    generate_dialogue_suggestion,
    generate_dialogue_responses,
    generate_dialogue_responses_for_run,
    generate_dialogue_suggestion_for_run,
    parse_dialogue_suggestion,
    parse_dialogue_responses,
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
            remember_long_term_memory=self._remember_dialogue_long_term_memory,
            evolve_relations_from_turn=self._evolve_relations_from_turn,
        )

    def get_dialogue_session(self, run_id: str, session_id: str) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        return self.dialogue.get_session(run_id, session_id)

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
            remember_long_term_memory=self._remember_dialogue_long_term_memory,
            evolve_relations_from_turn=self._evolve_relations_from_turn,
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

    def _remember_dialogue_long_term_memory(
        self,
        run_id: str,
        session_id: str,
        message: str,
        message_kind: str,
    ) -> None:
        if not message:
            return
        try:
            config = self._build_runtime_config_for_run(run_dir=self.runs_root / run_id)
            parts = self._build_runtime_parts(config)
            text = str(message).strip()
            prefix = "[剧情推动]" if str(message_kind or "").strip() == "narration" else "[对话]"
            parts.session_store.append_long_term_memory(session_id, f"{prefix} {text}", metadata={"run_id": run_id})
        except Exception:
            return

    def _evolve_relations_from_turn(
        self,
        run_id: str,
        pending_payload: dict[str, Any],
        responses: list[dict[str, str]],
    ) -> None:
        if not responses:
            return
        try:
            manifest = self._require_manifest(run_id)
            relation_graph = dict(manifest.get("artifact_index", {}).get("relation_graph", {}) or {})
            relation_path = Path(str(relation_graph.get("relations_file", "")).strip())
            if not relation_path.exists():
                return
            relation_payload = load_relations_source(relation_path)
            relations = dict(relation_payload.get("relations", {}) or {})
            input_block = dict(pending_payload.get("input", {}) or {})
            speaker = str(input_block.get("speaker", "")).strip()
            participants = [str(item).strip() for item in input_block.get("participants", []) if str(item).strip()]
            active = [str(item).strip() for item in input_block.get("active_participants", []) if str(item).strip()]
            candidates = active or participants

            def pair_key(a: str, b: str) -> str:
                return "_".join(sorted([a, b]))

            for reply in responses:
                responder = str(reply.get("speaker", "")).strip()
                message = str(reply.get("message", "")).strip()
                if not responder or not message:
                    continue
                target = speaker
                if not target or target in {"User", "场景提示", "旁白"}:
                    pool = [name for name in candidates if name and name != responder]
                    target = pool[0] if pool else ""
                if not target or target == responder:
                    continue
                key = pair_key(responder, target)
                relation = dict(relations.get(key, {}) or {})
                trust = int(relation.get("trust", 5) or 5)
                affection = int(relation.get("affection", 5) or 5)
                hostility = int(relation.get("hostility", 0) or 0)
                ambiguity = int(relation.get("ambiguity", 3) or 3)
                if any(token in message for token in ("谢谢", "抱歉", "理解", "关心", "在意", "一起")):
                    trust = min(10, trust + 1)
                    affection = min(10, affection + 1)
                    hostility = max(0, hostility - 1)
                if any(token in message for token in ("滚", "讨厌", "厌恶", "闭嘴", "烦", "恨", "威胁")):
                    hostility = min(10, hostility + 2)
                    trust = max(0, trust - 1)
                    affection = max(0, affection - 2)
                if any(token in message for token in ("也许", "或许", "未必", "再说")):
                    ambiguity = min(10, ambiguity + 1)

                relation.update(
                    {
                        "trust": trust,
                        "affection": affection,
                        "hostility": hostility,
                        "ambiguity": ambiguity,
                    }
                )
                evidence_lines = relation.get("evidence_lines", [])
                if not isinstance(evidence_lines, list):
                    evidence_lines = []
                evidence_lines.append(f"{responder}->{target}: {message}"[:220])
                relation["evidence_lines"] = evidence_lines[-10:]
                relations[key] = relation

            conflict_list = []
            for key, relation in relations.items():
                if not isinstance(relation, dict):
                    continue
                trust = int(relation.get("trust", 5) or 5)
                affection = int(relation.get("affection", 5) or 5)
                hostility = int(relation.get("hostility", 0) or 0)
                ambiguity = int(relation.get("ambiguity", 3) or 3)
                tags = []
                if trust >= 8 and hostility >= 6:
                    tags.append("high_trust_high_hostility")
                if affection >= 8 and hostility >= 6:
                    tags.append("high_affection_high_hostility")
                if ambiguity >= 8 and max(trust, affection, hostility) >= 8:
                    tags.append("high_ambiguity_with_extreme_signal")
                if tags:
                    conflict_list.append(
                        {
                            "pair_key": key,
                            "tags": tags,
                            "trust": trust,
                            "affection": affection,
                            "hostility": hostility,
                            "ambiguity": ambiguity,
                        }
                    )
            relation_payload["relations"] = relations
            relation_payload["conflicts"] = conflict_list
            relation_payload["novel_id"] = str(manifest.get("novel_id", "")).strip() or run_id
            save_markdown_data(
                relation_path,
                relation_payload,
                title="RELATION_GRAPH",
                summary=[
                    f"- novel_id: {relation_payload['novel_id']}",
                    f"- relation_count: {len(relations)}",
                    f"- conflict_count: {len(conflict_list)}",
                ],
            )
        except Exception:
            return
