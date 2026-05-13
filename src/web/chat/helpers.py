from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable

from src.core.exceptions import LLMRequestError


def build_dialogue_opening_message(session: dict[str, Any]) -> str:
    mode = str(session.get("mode", "observe")).strip() or "observe"
    participants = [str(item).strip() for item in session.get("participants", []) if str(item).strip()]
    cast = "、".join(participants) or "当前角色"
    scene_card = dict(session.get("scene_card", {}) or {})
    scene_title = str(scene_card.get("title", "")).strip()
    location = str(scene_card.get("location", "")).strip()
    atmosphere = str(scene_card.get("atmosphere", "")).strip()
    opening = str(scene_card.get("opening_situation", "")).strip()
    drive = str(scene_card.get("scene_drive", "")).strip()
    scene_prefix_bits = [bit for bit in (scene_title, location, atmosphere) if bit]
    scene_prefix = f"场景设定：{' / '.join(scene_prefix_bits)}。" if scene_prefix_bits else ""
    opening_suffix = f" 开场局面是：{opening}。" if opening else ""
    drive_suffix = f" 推进方向优先朝这边走：{drive}。" if drive else ""
    if mode == "act":
        controlled = str(session.get("controlled_character", "")).strip() or "该角色"
        return (
            f"{scene_prefix}请先为 {controlled} 与 {cast} 生成一个自然开场。"
            f"{opening_suffix}{drive_suffix}"
            "先给 1 条简短的场景提示或旁白，再让其他角色先接出第一轮对话，不要等待用户补充。"
        )
    if mode == "insert":
        self_profile = dict(session.get("self_insert", {}) or {})
        display_name = str(self_profile.get("display_name", "")).strip() or "我"
        scene_identity = str(self_profile.get("scene_identity", "")).strip() or str(self_profile.get("core_identity", "")).strip()
        identity_suffix = f"，身份是{scene_identity}" if scene_identity else ""
        return (
            f"{scene_prefix}请先为 {display_name}{identity_suffix} 与 {cast} 生成一个自然开场。"
            f"{opening_suffix}{drive_suffix}"
            "先给 1 条简短的场景提示或旁白，再让角色们先开口，对这个进入场景的人作出第一轮反应。"
        )
    return (
        f"{scene_prefix}请先为 {cast} 生成一个自然开场。"
        f"{opening_suffix}{drive_suffix}"
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
    compact["memory_context"] = _compact_memory_context(dict(compact.get("memory_context", {}) or {}))

    compact["persona_contexts"] = [
        _compact_persona_context(item) for item in list(compact.get("persona_contexts", []) or [])[:4]
    ]
    compact["user_persona"] = _compact_user_persona(dict(compact.get("user_persona", {}) or {}))
    return compact


def _compact_persona_context(item: dict[str, Any]) -> dict[str, Any]:
    preview = dict(item.get("preview", {}) or {})
    profile = dict(item.get("profile", {}) or {})
    snapshot = dict(item.get("session_snapshot", {}) or {})
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
    compact_snapshot = {
        key: value
        for key, value in {
            "mood": str(snapshot.get("mood", "")).strip(),
            "interaction_state": str(snapshot.get("interaction_state", "")).strip(),
            "focus": str(snapshot.get("focus", "")).strip(),
            "last_target": str(snapshot.get("last_target", "")).strip(),
            "last_event": _trim_text(str(snapshot.get("last_event", "")).strip(), 80),
        }.items()
        if _has_meaningful_value(value)
    }
    return {
        "name": str(item.get("name", "")).strip(),
        "preview": compact_preview,
        "profile": compact_profile,
        "session_snapshot": compact_snapshot,
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
    scene_card = dict(persona.get("scene_card", {}) or {})
    compact_persona["scene_card"] = {
        key: value
        for key, value in {
            "title": str(scene_card.get("title", "")).strip(),
            "location": str(scene_card.get("location", "")).strip(),
            "atmosphere": str(scene_card.get("atmosphere", "")).strip(),
            "opening_situation": _trim_text(str(scene_card.get("opening_situation", "")).strip(), 140),
            "public_goal": _trim_text(str(scene_card.get("public_goal", "")).strip(), 140),
            "hidden_tension": _trim_text(str(scene_card.get("hidden_tension", "")).strip(), 140),
            "scene_drive": _trim_text(str(scene_card.get("scene_drive", "")).strip(), 140),
            "expected_rhythm": str(scene_card.get("expected_rhythm", "")).strip(),
        }.items()
        if _has_meaningful_value(value)
    }
    return compact_persona


def _compact_memory_context(memory_context: dict[str, Any]) -> dict[str, Any]:
    session_summary = dict(memory_context.get("session_summary", {}) or {})
    archived_summary = dict(memory_context.get("archived_summary", {}) or {})
    retrieved_memories = list(memory_context.get("retrieved_memories", []) or [])
    scene_progress = dict(memory_context.get("scene_progress", {}) or {})
    relation_delta = dict(memory_context.get("relation_delta", {}) or {})
    character_snapshots = dict(memory_context.get("character_snapshots", {}) or {})
    event_signals = list(memory_context.get("event_signals", []) or [])
    compact_archived = {
        key: value
        for key, value in {
            "summary": _trim_text(str(archived_summary.get("summary", "")).strip(), 180),
            "key_points": [
                _trim_text(str(item).strip(), 80)
                for item in list(archived_summary.get("key_points", []) or [])[:3]
                if str(item).strip()
            ],
            "compressed_turns": archived_summary.get("compressed_turns", 0),
        }.items()
        if _has_meaningful_value(value)
    }
    compact_hits: list[dict[str, Any]] = []
    for item in retrieved_memories[:2]:
        compact_hit = {
            key: value
            for key, value in {
                "text": _trim_text(str(item.get("text", "")).strip(), 100),
                "speaker": str(item.get("speaker", "")).strip(),
                "target": str(item.get("target", "")).strip(),
                "kind": str(item.get("kind", "")).strip(),
            }.items()
            if _has_meaningful_value(value)
        }
        if compact_hit:
            compact_hits.append(compact_hit)
    return {
        key: value
        for key, value in {
            "session_summary": {
                inner_key: _trim_text(str(inner_value).strip(), 120)
                for inner_key, inner_value in session_summary.items()
                if _has_meaningful_value(inner_value)
            },
            "archived_summary": compact_archived,
            "retrieved_memories": compact_hits,
            "scene_progress": {
                inner_key: _trim_text(str(inner_value).strip(), 100)
                for inner_key, inner_value in scene_progress.items()
                if _has_meaningful_value(inner_value)
            },
            "relation_delta": {
                str(pair_key).strip(): {
                    metric_key: metric_value
                    for metric_key, metric_value in dict(delta or {}).items()
                    if metric_value not in ("", [], 0, None)
                }
                for pair_key, delta in list(relation_delta.items())[:3]
                if str(pair_key).strip()
            },
            "character_snapshots": {
                str(name).strip(): {
                    snap_key: _trim_text(str(snap_value).strip(), 80)
                    for snap_key, snap_value in dict(snapshot or {}).items()
                    if _has_meaningful_value(snap_value)
                }
                for name, snapshot in list(character_snapshots.items())[:4]
                if str(name).strip()
            },
            "event_signals": [
                {
                    key: (_trim_text(str(value).strip(), 80) if isinstance(value, str) else value)
                    for key, value in dict(item or {}).items()
                    if value not in ("", [], None, False)
                }
                for item in event_signals[-6:]
                if dict(item or {}).get("kind")
            ],
        }.items()
        if _has_meaningful_value(value)
    }


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
    message_kind = str(input_block.get("message_kind", "dialogue")).strip() or "dialogue"
    participants = [str(item).strip() for item in input_block.get("participants", []) if str(item).strip()]
    active_participants = [str(item).strip() for item in input_block.get("active_participants", []) if str(item).strip()]
    persona_contexts = payload.get("persona_contexts", [])
    relation_excerpt = str(payload.get("relation_context", {}).get("relations_excerpt", "")).strip()
    history = payload.get("history", [])
    memory_context = dict(payload.get("memory_context", {}) or {})
    instructions = dict(payload.get("instructions", {}) or {})
    host_action = dict(payload.get("host_action", {}) or {})
    scene_card = dict(payload.get("scene_card", {}) or {})
    response_limit = int(host_action.get("response_limit_hint", 2) or 2)

    system_parts = [
        str(payload.get("host_prompt_brief", "")).strip(),
        str(instructions.get("generation_goal", "")).strip(),
        str(instructions.get("mode_rule", "")).strip(),
        str(instructions.get("speaker_rule", "")).strip(),
        str(instructions.get("response_style", "")).strip(),
        str(instructions.get("scene_rule", "")).strip(),
        str(instructions.get("progression_rule", "")).strip(),
        str(instructions.get("response_count_rule", "")).strip(),
        str(host_action.get("output_rule", "")).strip(),
        "角色的明显小动作不要单独写成旁白或场景提示；应尽量内嵌到该角色自己的台词里，用很短的括号动作来带出。",
        "只返回 JSON 数组，每项必须包含 speaker 和 message。",
    ]
    if retry_on_empty:
        system_parts.append('这次至少返回 1 条可用回复；只有在确实需要场景切换、人物进退场或环境变化时，才返回 speaker 为“旁白”或“场景提示”的一条提示。')
    system_prompt = "\n".join(part for part in system_parts if part)

    user_payload = {
        "mode": session_mode,
        "message_kind": message_kind,
        "speaker": str(input_block.get("speaker", "")).strip(),
        "message": str(input_block.get("message", "")).strip(),
        "participants": participants,
        "active_participants": active_participants,
        "scene_card": scene_card,
        "memory_context": memory_context,
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
    memory_context = dict(payload.get("memory_context", {}) or {})
    instructions = dict(payload.get("instructions", {}) or {})
    host_action = dict(payload.get("host_action", {}) or {})
    scene_card = dict(payload.get("scene_card", {}) or {})

    system_parts = [
        str(payload.get("host_prompt_brief", "")).strip(),
        "你不是在解释剧情，也不是在做回复分析；你要直接代写一条用户下一句要发出去的话。",
        str(instructions.get("generation_goal", "")).strip(),
        str(instructions.get("mode_rule", "")).strip(),
        str(instructions.get("speaker_rule", "")).strip(),
        str(instructions.get("response_style", "")).strip(),
        str(instructions.get("scene_rule", "")).strip(),
        str(host_action.get("output_rule", "")).strip(),
        "必须优先参考 user_persona：这代表当前应该由“你”如何说话。",
        "如果 mode=insert，就按 self-insert 的完整角色卡来写，不只参考上下文和别人刚才的回复。",
        "优先服从 self-insert 的核心身份、故事位置、灵魂目标、气质底色、世界观、信念支点、说话方式、应激反应和 interaction_style。",
        "如果上下文允许多种接法，优先选更符合 user_persona 的那一种，而不是只做一个泛用接话。",
        "如果 mode=act，就按 controlled character 的 persona profile、speech_style、temperament 和典型说话习惯来写。",
        "如果 mode=observe，就把这句话写成推动剧情的场景提示：让局势往前走，而不是复述、总结或劝说。",
        "如果 scene_card 存在，优先服从它给出的地点、气氛、开场局面、明面目标、暗线张力与推进方向。",
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
        "scene_card": scene_card,
        "memory_context": memory_context,
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


def build_dialogue_scene_progress_messages(session: dict[str, Any]) -> list[dict[str, str]]:
    transcript = list(session.get("transcript", []) or [])
    recent: list[dict[str, str]] = []
    for item in transcript[-12:]:
        speaker = str(item.get("speaker", "")).strip()
        role = str(item.get("role", "")).strip()
        message = str(item.get("message", "")).strip()
        if not message:
            continue
        recent.append(
            {
                "speaker": speaker,
                "role": role,
                "message": _trim_text(message, 120),
            }
        )
    payload = {
        "mode": str(session.get("mode", "observe")).strip() or "observe",
        "participants": [str(item).strip() for item in list(session.get("participants", []) or []) if str(item).strip()],
        "scene_card": dict(session.get("session_card", {}).get("scene_card", {}) or session.get("scene_card", {}) or {}),
        "session_memory_summary": dict(session.get("session_memory_summary", {}) or {}),
        "recent_transcript": recent,
        "current_scene_progress": dict(session.get("scene_progress", {}) or {}),
        "event_signals": dict(session.get("event_signals", {}) or session.get("state", {}).get("event_signals", {}) or {}),
    }
    system_prompt = "\n".join(
        [
            "你不是来续写对白，而是来提取当前场景状态。",
            "请根据最近几轮对话，判断：谁仍在场、谁已经离场、时间是否推进、地点是否变化、这一幕是否已经适合提示下一幕。",
            "offstage_participants 里的人默认不应继续直接开口，除非最近文本明确写到他们回来、进门、现身、重新加入。",
            "如果最近内容已经从白天聊到傍晚、夜里、深夜等，time_hint 要跟着更新，而不是一直停在原时间。",
            "如果几个人已经离开原场所进入更私密的新地点，其他未同去角色不要继续被视作同场。",
            "event_signals 里如果出现 scene_transition / cast_enter / cast_exit / atmosphere_shift / time_change / environment_change / beat_complete，要把它们纳入判断。",
            "should_offer_scene_shift 只在这一幕已经聊出明显一拍、适合自然转场时返回 true。",
            "只返回 JSON 对象，不要解释。",
            "格式：{\"present_participants\":[],\"offstage_participants\":[],\"time_hint\":\"\",\"location\":\"\",\"progression_note\":\"\",\"should_offer_scene_shift\":false,\"scene_shift_reason\":\"\"}",
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def build_dialogue_relation_state_messages(
    session: dict[str, Any],
    pending_payload: dict[str, Any],
    responses: list[dict[str, str]],
) -> list[dict[str, str]]:
    transcript = list(session.get("transcript", []) or [])
    recent: list[dict[str, str]] = []
    for item in transcript[-10:]:
        speaker = str(item.get("speaker", "")).strip()
        role = str(item.get("role", "")).strip()
        message = str(item.get("message", "")).strip()
        if not message:
            continue
        recent.append(
            {
                "speaker": speaker,
                "role": role,
                "message": _trim_text(message, 120),
            }
        )
    current_state = {
        "relation_delta": dict(session.get("state", {}).get("relation_delta", {}) or {}),
        "character_snapshots": dict(session.get("state", {}).get("character_snapshots", {}) or {}),
        "event_signals": dict(session.get("state", {}).get("event_signals", {}) or {}),
    }
    payload = {
        "participants": [str(item).strip() for item in list(session.get("participants", []) or []) if str(item).strip()],
        "pending_input": {
            "speaker": str(dict(pending_payload.get("input", {}) or {}).get("speaker", "")).strip(),
            "message": _trim_text(str(dict(pending_payload.get("input", {}) or {}).get("message", "")).strip(), 120),
            "active_participants": [
                str(item).strip()
                for item in list(dict(pending_payload.get("input", {}) or {}).get("active_participants", []) or [])
                if str(item).strip()
            ],
        },
        "recent_transcript": recent,
        "new_responses": [
            {
                "speaker": str(item.get("speaker", "")).strip(),
                "message": _trim_text(str(item.get("message", "")).strip(), 120),
            }
            for item in list(responses or [])
            if str(item.get("speaker", "")).strip() and str(item.get("message", "")).strip()
        ],
        "current_state": current_state,
    }
    system_prompt = "\n".join(
        [
            "你不是来续写剧情，而是来轻量修正当前会话的关系增量和人物快照。",
            "current_state 是启发式先写好的底稿；你只能小幅修正、补全或删掉明显不合语境的项，不能凭空重写成另一套关系。",
            "relation_delta 只记录本会话里的增量变化，不是人物一生的最终关系定论。",
            "character_snapshots 只描述本会话当前阶段的状态，比如 mood、interaction_state、focus、last_target、last_event。",
            "event_signals 是统一事件层：场景进入/退出、角色登场/离场、明显动作、氛围突变、时间/环境变化、关系变化、互动重心变化、拍点完成都会记在这里。",
            "如果一句话不足以支持明显变化，就宁可保守，不要过拟合。",
            "只返回 JSON 对象，不要解释。",
            "格式：{\"relation_delta\":{},\"character_snapshots\":{}}",
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def parse_dialogue_scene_progress(content: str, participants: list[str]) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise ValueError("Model returned an empty scene progress state.")
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model reply is not valid scene progress JSON.") from None
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Scene progress state is not an object.")

    allowed = {str(item).strip() for item in participants if str(item).strip()}

    def clean_names(value: Any) -> list[str]:
        names: list[str] = []
        for item in list(value or []):
            name = str(item or "").strip()
            if not name or (allowed and name not in allowed) or name in names:
                continue
            names.append(name)
        return names

    present = clean_names(parsed.get("present_participants", []))
    offstage = [name for name in clean_names(parsed.get("offstage_participants", [])) if name not in present]
    return {
        "present_participants": present,
        "offstage_participants": offstage,
        "time_hint": _trim_text(str(parsed.get("time_hint", "")).strip(), 40),
        "location": _trim_text(str(parsed.get("location", "")).strip(), 40),
        "progression_note": _trim_text(str(parsed.get("progression_note", "")).strip(), 120),
        "should_offer_scene_shift": bool(parsed.get("should_offer_scene_shift", False)),
        "scene_shift_reason": _trim_text(str(parsed.get("scene_shift_reason", "")).strip(), 120),
    }


def parse_dialogue_relation_state(content: str, participants: list[str]) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise ValueError("Model returned an empty relation state.")
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model reply is not valid relation state JSON.") from None
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Relation state is not an object.")

    allowed = [str(item).strip() for item in participants if str(item).strip()]
    allowed_set = set(allowed)

    def pair_key(left: str, right: str) -> str:
        return "_".join(sorted([left, right]))

    allowed_pairs = {
        pair_key(left, right)
        for index, left in enumerate(allowed)
        for right in allowed[index + 1 :]
        if left and right
    }
    relation_delta: dict[str, Any] = {}
    for raw_key, raw_value in dict(parsed.get("relation_delta", {}) or {}).items():
        key = str(raw_key).strip()
        if not key or key not in allowed_pairs:
            continue
        item = dict(raw_value or {})
        normalized: dict[str, Any] = {}
        for field in ("trust", "affection", "hostility", "ambiguity"):
            try:
                amount = int(item.get(field, 0) or 0)
            except Exception:
                amount = 0
            if amount:
                normalized[field] = max(-3, min(3, amount))
        for field in ("last_event", "relation_change", "typical_interaction"):
            value = _trim_text(str(item.get(field, "")).strip(), 120)
            if value:
                normalized[field] = value
        evidence_lines = [
            _trim_text(str(line).strip(), 180)
            for line in list(item.get("evidence_lines", []) or [])
            if str(line).strip()
        ]
        if evidence_lines:
            normalized["evidence_lines"] = evidence_lines[:10]
        if normalized:
            relation_delta[key] = normalized

    character_snapshots: dict[str, Any] = {}
    for raw_name, raw_value in dict(parsed.get("character_snapshots", {}) or {}).items():
        name = str(raw_name).strip()
        if not name or name not in allowed_set:
            continue
        item = dict(raw_value or {})
        normalized = {
            "mood": _trim_text(str(item.get("mood", "")).strip(), 40),
            "interaction_state": _trim_text(str(item.get("interaction_state", "")).strip(), 40),
            "focus": _trim_text(str(item.get("focus", "")).strip(), 40),
            "last_target": _trim_text(str(item.get("last_target", "")).strip(), 40),
            "last_message": _trim_text(str(item.get("last_message", "")).strip(), 180),
            "last_event": _trim_text(str(item.get("last_event", "")).strip(), 180),
        }
        normalized = {key: value for key, value in normalized.items() if value}
        if normalized:
            if normalized.get("last_target") and normalized["last_target"] not in allowed_set:
                normalized.pop("last_target", None)
            character_snapshots[name] = normalized

    return {
        "relation_delta": relation_delta,
        "character_snapshots": character_snapshots,
    }


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
            responses = parse_responses(content, allowed_speakers)
            return _normalize_dialogue_responses(
                responses,
                response_limit=int(dict(payload.get("host_action", {}) or {}).get("response_limit_hint", 0) or 0),
            )
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


def _normalize_dialogue_responses(
    responses: list[dict[str, str]],
    *,
    response_limit: int,
) -> list[dict[str, str]]:
    # Keep only one line per character speaker per turn (except narration/meta speakers),
    # then cap to the turn hint so noisy outputs do not flood the transcript.
    cleaned: list[dict[str, str]] = []
    seen_character_speakers: set[str] = set()
    for item in responses:
        speaker = str(item.get("speaker", "")).strip()
        message = str(item.get("message", "")).strip()
        if not speaker or not message:
            continue
        if speaker not in {"旁白", "场景提示"}:
            if speaker in seen_character_speakers:
                continue
            seen_character_speakers.add(speaker)
        cleaned.append({"speaker": speaker, "message": message})

    if not cleaned:
        raise ValueError("Model reply did not contain usable character responses.")
    if response_limit > 0:
        return cleaned[:response_limit]
    return cleaned
