#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

_SUPPORTED_DIALOGUE_MODES = {"act", "insert", "observe"}


def normalize_dialogue_suggestion_context(context: dict[str, Any]) -> dict[str, Any]:
    mode = str(context.get("mode", "observe")).strip() or "observe"
    if mode not in _SUPPORTED_DIALOGUE_MODES:
        raise ValueError(f"Unsupported dialogue suggestion mode: {mode}")
    speaker = str(context.get("speaker", "")).strip()
    participants = [str(item).strip() for item in list(context.get("participants", [])) if str(item).strip()]
    if not participants:
        raise ValueError("Dialogue suggestion context requires at least one participant.")
    persona_contexts = [_normalize_persona_context(item) for item in list(context.get("persona_contexts", [])) if isinstance(item, dict)]
    history = [_normalize_history_entry(item) for item in list(context.get("history", [])) if isinstance(item, dict)]
    relation_excerpt = str(context.get("relation_excerpt", "")).strip()
    controlled_character = str(context.get("controlled_character", "")).strip()
    seed_text = str(context.get("seed_text", "")).strip()
    user_persona = dict(context.get("user_persona", {}) or {})
    if mode == "act" and not speaker:
        speaker = controlled_character
    if mode == "insert" and not speaker:
        speaker = str(user_persona.get("display_name", "")).strip() or "你"
    if mode == "act":
        if not controlled_character and not speaker:
            raise ValueError("act mode requires controlled_character or speaker.")
        controlled_name = controlled_character or speaker
        has_persona = any(str(item.get("name", "")).strip() == controlled_name for item in persona_contexts)
        if not has_persona:
            raise ValueError("act mode requires a matching persona_context for the controlled character.")
    if mode == "insert":
        if not any(
            str(user_persona.get(key, "")).strip()
            for key in ("display_name", "scene_identity", "core_identity", "speech_style", "soul_goal")
        ):
            raise ValueError("insert mode requires a non-empty user_persona profile.")
    return {
        "mode": mode,
        "speaker": speaker,
        "participants": participants,
        "persona_contexts": persona_contexts,
        "history": history,
        "relation_excerpt": relation_excerpt,
        "controlled_character": controlled_character,
        "seed_text": seed_text,
        "user_persona": user_persona,
        "active_participants": [str(item).strip() for item in list(context.get("active_participants", [])) if str(item).strip()],
    }


def build_dialogue_suggestion_payload(context: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_dialogue_suggestion_context(context)
    mode = normalized["mode"]
    speaker = normalized["speaker"]
    participants = list(normalized["participants"])
    payload = {
        "kind": "zaomeng_dialogue_suggestion",
        "mode": mode,
        "input": {
            "speaker": speaker,
            "message": normalized["seed_text"],
            "participants": participants,
            "active_participants": list(normalized["active_participants"]),
        },
        "persona_contexts": list(normalized["persona_contexts"]),
        "history": list(normalized["history"]),
        "relation_context": {"relations_excerpt": normalized["relation_excerpt"]},
        "user_persona": _build_user_suggestion_persona(mode, normalized, normalized["persona_contexts"]),
        "instructions": {
            "mode": mode,
            "generation_goal": "Draft one short, natural, directly sendable next user line that fits the current scene, relationships, and persona voices.",
            "mode_rule": _suggestion_mode_rule(mode),
            "speaker_rule": _speaker_rule(mode, normalized),
            "response_style": _suggestion_style_rule(mode),
        },
        "host_action": {
            "expected_output": {"suggestion": "一句可直接发送的话"},
            "output_rule": "Keep it short, in-scene, directly sendable, and never explanatory.",
        },
        "host_prompt_brief": _host_suggestion_prompt_brief(mode, speaker, participants),
    }
    return payload


def compact_dialogue_suggestion_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact = deepcopy(payload)
    compact["history"] = list(compact.get("history", []) or [])[-4:]

    input_block = dict(compact.get("input", {}) or {})
    input_block["message"] = _trim_text(str(input_block.get("message", "")).strip(), 120)
    compact["input"] = input_block

    relation_context = dict(compact.get("relation_context", {}) or {})
    relation_context["relations_excerpt"] = _trim_text(str(relation_context.get("relations_excerpt", "")).strip(), 1200)
    compact["relation_context"] = relation_context

    compact["persona_contexts"] = [_compact_persona_context(item) for item in list(compact.get("persona_contexts", []) or [])[:4]]
    compact["user_persona"] = _compact_user_persona(dict(compact.get("user_persona", {}) or {}))
    return compact


def build_dialogue_suggestion_llm_messages(payload: dict[str, Any], *, retry_on_empty: bool = False) -> list[dict[str, str]]:
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
        system_parts.append("上一次你的输出不是可直接发送的台词。重来：只给一句短而自然的话，像聊天框里马上要发出去的内容。")
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


def _speaker_rule(mode: str, context: dict[str, Any]) -> str:
    if mode == "act":
        speaker = str(context.get("speaker", "")).strip() or "该角色"
        return f"The drafted line must sound like {speaker}, not like a narrator or advisor."
    if mode == "insert":
        return "The drafted line must sound like the self-insert user speaking naturally inside the current scene."
    return "The drafted line must be an in-world scene nudge, not a cast member reply and not meta narration."


def _suggestion_mode_rule(mode: str) -> str:
    if mode == "act":
        return "Draft the user's next line as the controlled character, fully in character."
    if mode == "insert":
        return "Draft the user's next line as the self-insert identity inside the scene."
    return "Draft the user's next line as a short scene-steering utterance that introduces movement, tension, reaction, interruption, or new information; not a character reply."


def _suggestion_style_rule(mode: str) -> str:
    if mode == "observe":
        return "Prefer one short scene-driving prompt that pushes the plot forward immediately, such as a new beat, interruption, reveal, gesture, or emotional turn, with no explanation attached."
    if mode == "act":
        return "Prefer one concise in-character line that another participant can answer naturally, as final sendable wording."
    return "Prefer one concise line that sounds like the self-insert user speaking naturally in the scene, as final sendable wording."


def _build_user_suggestion_persona(mode: str, context: dict[str, Any], persona_contexts: list[dict[str, Any]]) -> dict[str, Any]:
    if mode == "act":
        controlled = str(context.get("controlled_character", "")).strip() or str(context.get("speaker", "")).strip()
        matched = next((item for item in persona_contexts if str(item.get("name", "")).strip() == controlled), {})
        return {
            "mode": "act",
            "speaker": controlled,
            "source": "controlled_character_persona",
            "must_follow": "Write exactly as this controlled character would speak in the current scene.",
            "profile": dict(matched.get("profile", {}) or {}),
            "preview": dict(matched.get("preview", {}) or {}),
        }
    if mode == "insert":
        card = dict(context.get("user_persona", {}) or {})
        return {
            "mode": "insert",
            "speaker": str(card.get("display_name", "")).strip() or "你",
            "source": "self_insert_profile",
            "must_follow": "Write as the self-insert user, keeping their full role card, identity, motives, and speaking flavor consistent.",
            "profile": dict(card),
        }
    return {
        "mode": "observe",
        "speaker": "User",
        "source": "observer_hint",
        "must_follow": "Write as a scene observer giving a short in-world nudge that actively moves the scene, rather than speaking as a cast member.",
        "profile": {
            "goal": "push_plot_forward",
            "preferred_moves": [
                "introduce a new action",
                "add a small interruption",
                "surface a hidden tension",
                "shift the emotional temperature",
                "make someone notice something important",
            ],
        },
    }


def _host_suggestion_prompt_brief(mode: str, speaker: str, participants: list[str]) -> str:
    if mode == "act":
        return f"Help the user speak as {speaker} with one believable next line."
    if mode == "insert":
        return f"Help the user speak as {speaker} inside the current scene with one natural next line."
    cast = ", ".join(participants) or "the cast"
    return f"Help the user guide {cast} with one short prompt that clearly pushes the scene into its next beat."


def _normalize_persona_context(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name", "")).strip(),
        "preview": dict(item.get("preview", {}) or {}),
        "profile": dict(item.get("profile", {}) or {}),
    }


def _normalize_history_entry(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "speaker": str(item.get("speaker", "")).strip(),
        "message": str(item.get("message", "")).strip(),
        "target": str(item.get("target", "")).strip(),
    }


def _compact_persona_context(item: dict[str, Any]) -> dict[str, Any]:
    preview = dict(item.get("preview", {}) or {})
    profile = dict(item.get("profile", {}) or {})
    compact_preview = {
        key: value
        for key, value in {
            "display_name": str(preview.get("display_name", "")).strip(),
            "core_identity": str(preview.get("core_identity", "")).strip(),
            "speech_style": str(preview.get("speech_style", "")).strip(),
            "appearance_feature": _trim_text(str(preview.get("appearance_feature", "")).strip(), 80),
        }.items()
        if _has_meaningful_value(value)
    }
    compact_profile = {
        key: value
        for key, value in {
            "core_identity": str(profile.get("core_identity", "")).strip(),
            "story_role": str(profile.get("story_role", "")).strip(),
            "gender": str(profile.get("gender", "")).strip(),
            "age_stage": str(profile.get("age_stage", "")).strip(),
            "appearance_feature": _trim_text(str(profile.get("appearance_feature", "")).strip(), 100),
            "habit_action": _trim_text(str(profile.get("habit_action", "")).strip(), 80),
            "speech_style": str(profile.get("speech_style", "")).strip(),
            "temperament_type": str(profile.get("temperament_type", "")).strip(),
            "stress_response": str(profile.get("stress_response", "")).strip(),
            "key_bonds": _normalize_short_list(profile.get("key_bonds")),
            "preference_like": _normalize_short_list(profile.get("preference_like")),
            "dislike_hate": _normalize_short_list(profile.get("dislike_hate")),
        }.items()
        if _has_meaningful_value(value)
    }
    return {
        "name": str(item.get("name", "")).strip(),
        "preview": compact_preview,
        "profile": compact_profile,
    }


def _compact_user_persona(persona: dict[str, Any]) -> dict[str, Any]:
    profile = dict(persona.get("profile", persona) or {})
    compact_profile = {
        key: value
        for key, value in {
            "display_name": str(profile.get("display_name", "")).strip(),
            "scene_identity": str(profile.get("scene_identity", "")).strip(),
            "interaction_style": str(profile.get("interaction_style", "")).strip(),
            "core_identity": str(profile.get("core_identity", "")).strip(),
            "story_role": str(profile.get("story_role", "")).strip(),
            "gender": str(profile.get("gender", "")).strip(),
            "age_stage": str(profile.get("age_stage", "")).strip(),
            "appearance_feature": _trim_text(str(profile.get("appearance_feature", "")).strip(), 100),
            "habit_action": _trim_text(str(profile.get("habit_action", "")).strip(), 80),
            "soul_goal": str(profile.get("soul_goal", "")).strip(),
            "speech_style": str(profile.get("speech_style", "")).strip(),
            "worldview": _trim_text(str(profile.get("worldview", "")).strip(), 120),
            "belief_anchor": _trim_text(str(profile.get("belief_anchor", "")).strip(), 120),
            "stress_response": _trim_text(str(profile.get("stress_response", "")).strip(), 120),
            "key_bonds": _normalize_short_list(profile.get("key_bonds")),
            "preference_like": _normalize_short_list(profile.get("preference_like")),
            "dislike_hate": _normalize_short_list(profile.get("dislike_hate")),
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
