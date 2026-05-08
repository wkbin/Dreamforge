from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def load_pending_turn_payload(
    *,
    runs_root: Path,
    run_id: str,
    session_id: str,
    load_json_file: Callable[[Path], dict[str, Any] | None],
) -> dict[str, Any]:
    session_path = runs_root / run_id / "dialogue" / session_id / "session.json"
    session_payload = load_json_file(session_path) or {}
    pending_path_text = str(session_payload.get("pending_turn", {}).get("payload_path", "")).strip()
    if not pending_path_text:
        raise ValueError("Pending turn payload was not created.")
    pending_path = Path(pending_path_text)
    pending_payload = load_json_file(pending_path)
    if not pending_payload:
        raise ValueError("Pending turn payload is empty.")
    return pending_payload


def generate_dialogue_responses_for_run(
    *,
    run_dir: Path,
    payload: dict[str, Any],
    build_runtime_config_for_run: Callable[..., Any],
    build_runtime_parts: Callable[[Any], Any],
    generate_dialogue_responses: Callable[..., list[dict[str, str]]],
    build_dialogue_llm_messages: Callable[[dict[str, Any], bool], list[dict[str, str]]],
    parse_dialogue_responses: Callable[[str, list[str]], list[dict[str, str]]],
) -> list[dict[str, str]]:
    config = build_runtime_config_for_run(run_dir=run_dir)
    parts = build_runtime_parts(config)
    if not hasattr(parts.llm, "chat_completion"):
        raise ValueError("Configured model does not support chat generation.")

    allowed_speakers = [str(item.get("name", "")).strip() for item in payload.get("responder_hints", [])]
    allowed_speakers.extend(["旁白", "场景提示"])
    return generate_dialogue_responses(
        payload=payload,
        allowed_speakers=allowed_speakers,
        temperature=float(config.get("llm.temperature", 0.35) or 0.35),
        max_tokens=int(config.get("llm.max_tokens", 900) or 900),
        chat_completion=lambda messages, temperature, max_tokens: parts.llm.chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ),
        build_messages=lambda current_payload, retry_on_empty: build_dialogue_llm_messages(
            current_payload,
            retry_on_empty,
        ),
        parse_responses=parse_dialogue_responses,
    )


def generate_dialogue_suggestion_for_run(
    *,
    run_dir: Path,
    payload: dict[str, Any],
    build_runtime_config_for_run: Callable[..., Any],
    build_runtime_parts: Callable[[Any], Any],
    generate_dialogue_suggestion: Callable[..., str],
    build_dialogue_suggestion_llm_messages: Callable[[dict[str, Any], bool], list[dict[str, str]]],
    parse_dialogue_suggestion: Callable[[str], str],
) -> str:
    config = build_runtime_config_for_run(run_dir=run_dir)
    parts = build_runtime_parts(config)
    if not hasattr(parts.llm, "chat_completion"):
        raise ValueError("Configured model does not support chat generation.")

    return generate_dialogue_suggestion(
        payload=payload,
        temperature=float(config.get("llm.temperature", 0.45) or 0.45),
        max_tokens=int(config.get("llm.max_tokens", 180) or 180),
        chat_completion=lambda messages, temperature, max_tokens: parts.llm.chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ),
        build_messages=lambda current_payload, retry_on_empty: build_dialogue_suggestion_llm_messages(
            current_payload,
            retry_on_empty,
        ),
        parse_suggestion=parse_dialogue_suggestion,
    )
