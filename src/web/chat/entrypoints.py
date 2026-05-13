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
    scene_profile: dict[str, str] | None,
    self_profile: dict[str, str] | None,
    build_dialogue_opening_message: Callable[[dict[str, Any]], str],
    load_pending_turn_payload: Callable[[str, str], dict[str, Any]],
    generate_dialogue_responses: Callable[[str, dict[str, Any]], list[dict[str, str]]],
    friendly_dialogue_llm_error: Callable[[Exception], str],
    evolve_relations_from_turn: Callable[[str, dict[str, Any], list[dict[str, str]]], None],
    refresh_scene_progress: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    session = dialogue.create_session(
        manifest,
        mode=mode,
        participants=participants,
        controlled_character=controlled_character,
        scene_profile=scene_profile,
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
    evolve_relations_from_turn(run_id, pending_payload, responses)
    ingested = dialogue.ingest_turn_responses(
        run_id,
        session_id=session_id,
        responses=responses,
        remember_turn_memory=True,
    )
    if callable(refresh_scene_progress):
        ingested = refresh_scene_progress(run_id, ingested)
    return ingested


def reply_dialogue_turn_payload(
    *,
    run_id: str,
    session_id: str,
    message: str,
    message_kind: str,
    manifest: dict[str, Any],
    dialogue: Any,
    load_pending_turn_payload: Callable[[str, str], dict[str, Any]],
    generate_dialogue_responses: Callable[[str, dict[str, Any]], list[dict[str, str]]],
    friendly_dialogue_llm_error: Callable[[Exception], str],
    evolve_relations_from_turn: Callable[[str, dict[str, Any], list[dict[str, str]]], None],
    refresh_scene_progress: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    speaker_override = "场景提示" if str(message_kind or "").strip() == "narration" else ""
    dialogue.prepare_turn(
        manifest,
        session_id=session_id,
        message=message,
        message_kind=message_kind,
        speaker_override=speaker_override,
    )
    pending_payload = load_pending_turn_payload(run_id, session_id)
    try:
        responses = generate_dialogue_responses(run_id, pending_payload)
    except LLMRequestError as exc:
        raise ValueError(friendly_dialogue_llm_error(exc)) from exc
    evolve_relations_from_turn(run_id, pending_payload, responses)
    ingested = dialogue.ingest_turn_responses(
        run_id,
        session_id=session_id,
        responses=responses,
        remember_turn_memory=True,
    )
    if callable(refresh_scene_progress):
        ingested = refresh_scene_progress(run_id, ingested)
    return ingested


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
