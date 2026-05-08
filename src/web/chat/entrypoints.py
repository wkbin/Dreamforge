from __future__ import annotations

from typing import Any, Callable

from src.core.exceptions import LLMRequestError


def create_dialogue_session_payload(
    *,
    run_id: str,
    manifest: dict[str, Any],
    dialogue: Any,
    mode: str,
    participants: list[str],
    controlled_character: str,
    self_profile: dict[str, str] | None,
    build_dialogue_opening_message: Callable[[dict[str, Any]], str],
    load_pending_turn_payload: Callable[[str, str], dict[str, Any]],
    generate_dialogue_responses: Callable[[str, dict[str, Any]], list[dict[str, str]]],
    friendly_dialogue_llm_error: Callable[[Exception], str],
) -> dict[str, Any]:
    session = dialogue.create_session(
        manifest,
        mode=mode,
        participants=participants,
        controlled_character=controlled_character,
        self_profile=self_profile,
    )
    session_id = str(session.get("session_id", "")).strip()
    opening_message = build_dialogue_opening_message(session)
    dialogue.prepare_turn(
        manifest,
        session_id=session_id,
        message=opening_message,
        speaker_override="场景提示",
        transcript_message="",
    )
    pending_payload = load_pending_turn_payload(run_id, session_id)
    try:
        responses = generate_dialogue_responses(run_id, pending_payload)
    except LLMRequestError as exc:
        raise ValueError(friendly_dialogue_llm_error(exc)) from exc
    return dialogue.ingest_turn_responses(
        run_id,
        session_id=session_id,
        responses=responses,
    )


def reply_dialogue_turn_payload(
    *,
    run_id: str,
    session_id: str,
    message: str,
    manifest: dict[str, Any],
    dialogue: Any,
    load_pending_turn_payload: Callable[[str, str], dict[str, Any]],
    generate_dialogue_responses: Callable[[str, dict[str, Any]], list[dict[str, str]]],
    friendly_dialogue_llm_error: Callable[[Exception], str],
) -> dict[str, Any]:
    dialogue.prepare_turn(manifest, session_id=session_id, message=message)
    pending_payload = load_pending_turn_payload(run_id, session_id)
    try:
        responses = generate_dialogue_responses(run_id, pending_payload)
    except LLMRequestError as exc:
        raise ValueError(friendly_dialogue_llm_error(exc)) from exc
    return dialogue.ingest_turn_responses(run_id, session_id=session_id, responses=responses)


def suggest_dialogue_turn_payload(
    *,
    run_id: str,
    session_id: str,
    seed_text: str,
    manifest: dict[str, Any],
    dialogue: Any,
    generate_dialogue_suggestion: Callable[[str, dict[str, Any]], str],
    friendly_dialogue_llm_error: Callable[[Exception], str],
) -> dict[str, str]:
    payload = dialogue.build_suggestion_payload(
        manifest,
        session_id=session_id,
        seed_text=seed_text,
    )
    try:
        suggestion = generate_dialogue_suggestion(run_id, payload)
    except LLMRequestError as exc:
        raise ValueError(friendly_dialogue_llm_error(exc)) from exc
    return {"suggestion": suggestion}
