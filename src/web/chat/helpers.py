from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable

from src.core.exceptions import LLMRequestError


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
        scene_identity = str(self_profile.get("scene_identity", "")).strip() or str(self_profile.get("core_identity", "")).strip()
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
    if any(token in lowered for token in ("maximum context", "context length", "prompt is too long", "too many tokens", "max context")):
        return "当前模型拒绝了这次续写建议请求，通常是上下文太长。系统已尝试自动压缩；如果仍失败，请减少参与角色或先清空一部分聊天上下文后重试。"
    return message or "当前模型调用失败，请检查模型配置后重试。"


def should_retry_suggestion_with_compact_payload(exc: Exception) -> bool:
    if not isinstance(exc, LLMRequestError):
        return False
    lowered = str(exc or "").lower()
    if "400" in lowered and "bad request" in lowered:
        return True
    return any(
        token in lowered
        for token in (
            "maximum context",
            "context length",
            "prompt is too long",
            "too many tokens",
            "max context",
            "context_window_exceeded",
        )
    )


def compact_dialogue_suggestion_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact = deepcopy(payload)

    compact["history"] = list(compact.get("history", []) or [])[-4:]

    input_block = dict(compact.get("input", {}) or {})
    input_block["message"] = _trim_text(str(input_block.get("message", "")).strip(), 120)
    compact["input"] = input_block

    relation_context = dict(compact.get("relation_context", {}) or {})
    relation_context["relations_excerpt"] = _trim_text(str(relation_context.get("relations_excerpt", "")).strip(), 1200)
    compact["relation_context"] = relation_context

    compact["persona_contexts"] = [
        _compact_persona_context(item) for item in list(compact.get("persona_contexts", []) or [])[:4]
    ]
    compact["user_persona"] = _compact_user_persona(dict(compact.get("user_persona", {}) or {}))
    return compact


def _compact_persona_context(item: dict[str, Any]) -> dict[str, Any]:
    preview = dict(item.get("preview", {}) or {})
    profile = dict(item.get("profile", {}) or {})
    compact_preview = {
        key: value
        for key, value in {
            "display_name": str(preview.get("display_name", "")).strip(),
            "core_identity": str(preview.get("core_identity", "")).strip(),
            "speech_style": str(preview.get("speech_style", "")).strip(),
        }.items()
        if _has_meaningful_value(value)
    }
    compact_profile = {
        key: value
        for key, value in {
            "core_identity": str(profile.get("core_identity", "")).strip(),
            "story_role": str(profile.get("story_role", "")).strip(),
            "speech_style": str(profile.get("speech_style", "")).strip(),
            "temperament_type": str(profile.get("temperament_type", "")).strip(),
            "stress_response": str(profile.get("stress_response", "")).strip(),
            "key_bonds": _normalize_short_list(profile.get("key_bonds")),
        }.items()
        if _has_meaningful_value(value)
    }
    return {
        "name": str(item.get("name", "")).strip(),
        "preview": compact_preview,
        "profile": compact_profile,
    }


def _compact_user_persona(persona: dict[str, Any]) -> dict[str, Any]:
    profile = dict(persona.get("profile", {}) or {})
    compact_profile = {
        key: value
        for key, value in {
            "display_name": str(profile.get("display_name", "")).strip(),
            "scene_identity": str(profile.get("scene_identity", "")).strip(),
            "interaction_style": str(profile.get("interaction_style", "")).strip(),
            "core_identity": str(profile.get("core_identity", "")).strip(),
            "story_role": str(profile.get("story_role", "")).strip(),
            "soul_goal": str(profile.get("soul_goal", "")).strip(),
            "speech_style": str(profile.get("speech_style", "")).strip(),
            "worldview": _trim_text(str(profile.get("worldview", "")).strip(), 120),
            "belief_anchor": _trim_text(str(profile.get("belief_anchor", "")).strip(), 120),
            "stress_response": _trim_text(str(profile.get("stress_response", "")).strip(), 120),
            "key_bonds": _normalize_short_list(profile.get("key_bonds")),
            "preferred_moves": _normalize_short_list(profile.get("preferred_moves")),
            "goal": str(profile.get("goal", "")).strip(),
        }.items()
        if _has_meaningful_value(value)
    }
    compact_persona = dict(persona)
    compact_persona["profile"] = compact_profile
    return compact_persona


def _normalize_short_list(value: Any) -> list[str] | str:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned[:4]
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.replace("；", ";").split(";") if part.strip()]
    return parts[:4] if parts else text


def _has_meaningful_value(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    return bool(str(value or "").strip())


def _trim_text(text: str, limit: int) -> str:
    cleaned = str(text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(1, limit - 1)].rstrip() + "…"


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


def build_dialogue_suggestion_llm_messages(
    payload: dict[str, Any],
    *,
    retry_on_empty: bool = False,
) -> list[dict[str, str]]:
    input_block = dict(payload.get("input", {}) or {})
    session_mode = str(payload.get("mode", "")).strip() or "observe"
    participants = [str(item).strip() for item in input_block.get("participants", []) if str(item).strip()]
    persona_contexts = payload.get("persona_contexts", [])
    user_persona = dict(payload.get("user_persona", {}) or {})
    relation_excerpt = str(payload.get("relation_context", {}).get("relations_excerpt", "")).strip()
    history = payload.get("history", [])
    instructions = dict(payload.get("instructions", {}) or {})
    host_action = dict(payload.get("host_action", {}) or {})

    system_parts = [
        str(payload.get("host_prompt_brief", "")).strip(),
        "你不是在解释剧情，也不是在做回复分析；你要直接代写一条用户下一句要发出去的话。",
        str(instructions.get("generation_goal", "")).strip(),
        str(instructions.get("mode_rule", "")).strip(),
        str(instructions.get("speaker_rule", "")).strip(),
        str(instructions.get("response_style", "")).strip(),
        str(host_action.get("output_rule", "")).strip(),
        "必须优先参考 user_persona：这代表当前应该由“你”如何说话。",
        "如果 mode=insert，就按 self-insert 的完整角色卡来写，不只参考上下文和别人刚才的回复。",
        "优先服从 self-insert 的核心身份、故事位置、灵魂目标、气质底色、世界观、信念支点、说话方式、应激反应和 interaction_style。",
        "如果上下文允许多种接法，优先选更符合 user_persona 的那一种，而不是只做一个泛用接话。",
        "如果 mode=act，就按 controlled character 的 persona profile、speech_style、temperament 和典型说话习惯来写。",
        "如果 mode=observe，就把这句话写成推动剧情的场景提示：让局势往前走，而不是复述、总结或劝说。",
        "只输出一句最终可发送的成品台词，不要解释上下文，不要总结历史，不要提供建议理由，不要写“作为/当前场景/我们可以/你可以/建议/回复：”这类分析话术。",
        "不要分段，不要项目符号，不要加引号，不要加说话人标签。",
    ]
    if retry_on_empty:
        system_parts.append(
            "上一次你的输出不是可直接发送的台词。重来：只给一句短而自然的话，像聊天框里马上要发出去的内容。"
        )
    system_prompt = "\n".join(part for part in system_parts if part)

    user_payload = {
        "mode": session_mode,
        "speaker": str(input_block.get("speaker", "")).strip(),
        "seed_text": str(input_block.get("message", "")).strip(),
        "user_persona": user_persona,
        "participants": participants,
        "persona_contexts": persona_contexts,
        "history": history,
        "relation_excerpt": relation_excerpt,
        "response_shape": host_action.get("expected_output", {"suggestion": "一句可直接发送的话"}),
        "good_examples": {
            "act_or_insert": [
                "抱歉，我刚才那句说重了。",
                "你先别气，我不是在呛你。",
                "那我换个说法，你别误会。",
            ],
            "observe": [
                "门外忽然传来两下敲门声，屋里一下静了。",
                "江澄先看见了他袖口上的血，话到嘴边忽然顿住。",
                "魏无羡低头笑了一下，却没立刻接这句话。",
            ],
        },
        "bad_examples": [
            "我们作为“你”是误入此间的来客……",
            "当前场景是对方在生气，我们可以先安抚……",
            "建议回复：先道歉，再解释。",
            "你们继续聊下去吧。",
        ],
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


def _looks_like_meta_suggestion(text: str) -> bool:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        return True
    if "\n" in str(text or ""):
        return True
    if len(normalized) > 90:
        return True

    meta_tokens = (
        "作为",
        "当前场景",
        "我们作为",
        "我们可以",
        "你可以",
        "建议",
        "回复：",
        "回复:",
        "历史显示",
        "上下文",
        "保持角色",
        "角色一致",
        "这句已经",
        "直接送出",
        "分析",
        "解释",
    )
    lowered = normalized.lower()
    if any(token in normalized for token in meta_tokens):
        return True
    if any(token in lowered for token in ("context", "suggestion", "reply:", "analysis")):
        return True
    return False


def parse_dialogue_suggestion(content: str) -> str:
    text = str(content or "").strip()
    if not text:
        raise ValueError("Model returned an empty suggestion.")
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        text = str(parsed.get("suggestion", "")).strip()
    elif isinstance(parsed, list) and parsed:
        first = parsed[0]
        if isinstance(first, dict):
            text = str(first.get("suggestion", "") or first.get("message", "")).strip()
        else:
            text = str(first).strip()
    else:
        text = text.strip().strip('"').strip("'")
    if "：" in text:
        prefix, rest = text.split("：", 1)
        if 0 < len(prefix.strip()) <= 16 and rest.strip():
            text = rest.strip()
    elif ":" in text:
        prefix, rest = text.split(":", 1)
        if 0 < len(prefix.strip()) <= 16 and rest.strip():
            text = rest.strip()
    text = " ".join(text.split()).strip()
    if not text:
        raise ValueError("Model reply did not contain a usable suggestion.")
    if _looks_like_meta_suggestion(text):
        raise ValueError("Model reply looked like explanation instead of a direct sendable line.")
    return text


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


def generate_dialogue_suggestion(
    *,
    payload: dict[str, Any],
    temperature: float,
    max_tokens: int,
    chat_completion: Callable[[list[dict[str, str]], float, int], dict[str, Any]],
    build_messages: Callable[[dict[str, Any], bool], list[dict[str, str]]],
    parse_suggestion: Callable[[str], str],
) -> str:
    attempts = (
        build_messages(payload, False),
        build_messages(payload, True),
    )
    last_error: Exception | None = None
    for index, llm_messages in enumerate(attempts):
        llm_result = chat_completion(llm_messages, temperature, max_tokens)
        content = str(llm_result.get("content", "")).strip()
        if not content:
            last_error = ValueError("Model returned an empty suggestion.")
            if index + 1 < len(attempts):
                continue
            break
        try:
            return parse_suggestion(content)
        except ValueError as exc:
            last_error = exc
            if index + 1 < len(attempts):
                continue
            raise
    raise ValueError("模型没有返回可用的续写建议。") from last_error
