from __future__ import annotations

import json
from typing import Any, Callable


def build_dialogue_opening_message(session: dict[str, Any]) -> str:
    mode = str(session.get("mode", "observe")).strip() or "observe"
    participants = [str(item).strip() for item in session.get("participants", []) if str(item).strip()]
    cast = "、".join(participants) or "当前角色"
    if mode == "act":
        controlled = str(session.get("controlled_character", "")).strip() or "该角色"
        return (
            f"请先为 {controlled} 与 {cast} 生成一个自然开场。"
            "先给 1 条简短的场景提示或旁白，再让其他角色先接出第一轮对话，不要等待用户补充。"
        )
    if mode == "insert":
        self_profile = dict(session.get("self_insert", {}) or {})
        display_name = str(self_profile.get("display_name", "")).strip() or "我"
        scene_identity = str(self_profile.get("scene_identity", "")).strip()
        identity_suffix = f"，身份是{scene_identity}" if scene_identity else ""
        return (
            f"请先为 {display_name}{identity_suffix} 与 {cast} 生成一个自然开场。"
            "先给 1 条简短的场景提示或旁白，再让角色们先开口，对这个进入场景的人作出第一轮反应。"
        )
    return (
        f"请先为 {cast} 生成一个自然开场。"
        "先给 1 条简短的场景提示或旁白，再让角色们开始第一轮对话，让场景自己动起来。"
    )


def friendly_dialogue_llm_error(exc: Exception) -> str:
    message = str(exc or "").strip()
    lowered = message.lower()
    if any(token in lowered for token in ("invalidsubscription", "codingplan", "subscription has expired", "does not have a valid")):
        return "当前模型账号没有可用的对话生成订阅权限，请更换可用模型，或检查并续订当前账号权限。"
    return message or "当前模型调用失败，请检查模型配置后重试。"


def build_dialogue_llm_messages(payload: dict[str, Any], *, retry_on_empty: bool = False) -> list[dict[str, str]]:
    input_block = dict(payload.get("input", {}) or {})
    session_mode = str(payload.get("mode", "")).strip() or "observe"
    participants = [str(item).strip() for item in input_block.get("participants", []) if str(item).strip()]
    persona_contexts = payload.get("persona_contexts", [])
    relation_excerpt = str(payload.get("relation_context", {}).get("relations_excerpt", "")).strip()
    history = payload.get("history", [])
    instructions = dict(payload.get("instructions", {}) or {})
    host_action = dict(payload.get("host_action", {}) or {})
    response_limit = int(host_action.get("response_limit_hint", 2) or 2)

    system_parts = [
        str(payload.get("host_prompt_brief", "")).strip(),
        str(instructions.get("generation_goal", "")).strip(),
        str(instructions.get("mode_rule", "")).strip(),
        str(instructions.get("speaker_rule", "")).strip(),
        str(instructions.get("response_style", "")).strip(),
        str(host_action.get("output_rule", "")).strip(),
        "只返回 JSON 数组，每项必须包含 speaker 和 message。",
    ]
    if retry_on_empty:
        system_parts.append('这次至少返回 1 条可用回复；如果角色暂时不宜直接接话，可先返回 speaker 为“旁白”或“场景提示”的一条提示。')
    system_prompt = "\n".join(part for part in system_parts if part)

    user_payload = {
        "mode": session_mode,
        "speaker": str(input_block.get("speaker", "")).strip(),
        "message": str(input_block.get("message", "")).strip(),
        "participants": participants,
        "response_limit": response_limit,
        "persona_contexts": persona_contexts,
        "history": history,
        "relation_excerpt": relation_excerpt,
        "expected_output": host_action.get("expected_output", [{"speaker": "角色名", "message": "回复内容"}]),
        "retry_on_empty": retry_on_empty,
    }
    user_prompt = json.dumps(user_payload, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def parse_dialogue_responses(content: str, allowed_speakers: list[str]) -> list[dict[str, str]]:
    text = str(content or "").strip()
    if not text:
        raise ValueError("Model returned an empty reply.")
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()
    parsed: Any
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model reply is not valid JSON.") from None
        parsed = json.loads(text[start : end + 1])

    if isinstance(parsed, dict):
        parsed = parsed.get("responses", [])
    if not isinstance(parsed, list):
        raise ValueError("Model reply is not a response list.")

    allowed = {name for name in allowed_speakers if name}
    clean_responses: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        speaker = str(item.get("speaker", "")).strip()
        message = str(item.get("message", "")).strip()
        if not speaker or not message:
            continue
        if allowed and speaker not in allowed:
            continue
        clean_responses.append({"speaker": speaker, "message": message})
    if not clean_responses:
        raise ValueError("Model reply did not contain usable character responses.")
    return clean_responses


def generate_dialogue_responses(
    *,
    payload: dict[str, Any],
    allowed_speakers: list[str],
    temperature: float,
    max_tokens: int,
    chat_completion: Callable[[list[dict[str, str]], float, int], dict[str, Any]],
    build_messages: Callable[[dict[str, Any], bool], list[dict[str, str]]],
    parse_responses: Callable[[str, list[str]], list[dict[str, str]]],
) -> list[dict[str, str]]:
    attempts = (
        build_messages(payload, False),
        build_messages(payload, True),
    )
    last_error: Exception | None = None
    for index, llm_messages in enumerate(attempts):
        llm_result = chat_completion(llm_messages, temperature, max_tokens)
        content = str(llm_result.get("content", "")).strip()
        if not content:
            last_error = ValueError("Model returned an empty reply.")
            if index + 1 < len(attempts):
                continue
            break
        try:
            return parse_responses(content, allowed_speakers)
        except ValueError as exc:
            last_error = exc
            if index + 1 < len(attempts):
                continue
            raise
    raise ValueError("模型没有返回可用的角色回复。") from last_error
