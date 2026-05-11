from __future__ import annotations

from typing import Any

KEY_FIELDS = (
    "core_identity",
    "story_role",
    "identity_anchor",
    "temperament_type",
    "soul_goal",
    "core_traits",
    "key_bonds",
    "speech_style",
    "worldview",
    "belief_anchor",
    "moral_bottom_line",
    "restraint_threshold",
    "stress_response",
)

FIELD_LABELS = {
    "core_identity": "核心身份",
    "story_role": "故事位置",
    "identity_anchor": "身份锚点",
    "temperament_type": "气质底色",
    "soul_goal": "灵魂目标",
    "hidden_desire": "隐秘渴望",
    "inner_conflict": "内在冲突",
    "self_cognition": "自我认知",
    "private_self": "私下的一面",
    "speech_style": "说话方式",
    "cadence": "语句节奏",
    "typical_lines": "代表句",
    "signature_phrases": "口头禅",
    "sentence_openers": "起句习惯",
    "sentence_endings": "句尾习惯",
    "social_mode": "社交模式",
    "thinking_style": "思考方式",
    "decision_rules": "决策规则",
    "reward_logic": "回报逻辑",
    "worldview": "世界观",
    "belief_anchor": "信念支点",
    "moral_bottom_line": "道德底线",
    "restraint_threshold": "失控阈值",
    "core_traits": "核心特质",
    "key_bonds": "重要牵系",
    "forbidden_behaviors": "不会做的事",
    "stress_response": "应激反应",
    "emotion_model": "情绪底模",
    "anger_style": "发怒方式",
    "joy_style": "开心方式",
    "grievance_style": "委屈方式",
    "others_impression": "他人观感",
}


def summarize_redistill_character_change(
    *,
    character: str,
    previous_fields: dict[str, str],
    next_fields: dict[str, str],
) -> dict[str, Any] | None:
    name = str(character or "").strip()
    if not name or not previous_fields:
        return None

    added_fields: list[str] = []
    rewritten_fields: list[str] = []
    removed_fields: list[str] = []
    changed_fields: list[str] = []

    for field, previous_value in previous_fields.items():
        before = str(previous_value or "").strip()
        after = str(next_fields.get(field, "") or "").strip()
        if before == after:
            continue
        changed_fields.append(field)
        if not before and after:
            added_fields.append(field)
        elif before and not after:
            removed_fields.append(field)
        else:
            rewritten_fields.append(field)

    if not changed_fields:
        return None

    highlighted = [field for field in KEY_FIELDS if field in changed_fields] or changed_fields
    highlighted_labels = [FIELD_LABELS.get(field, field) for field in highlighted[:5]]

    segments: list[str] = []
    if added_fields:
        segments.append(f"新增 {len(added_fields)} 项")
    if rewritten_fields:
        segments.append(f"改写 {len(rewritten_fields)} 项")
    if removed_fields:
        segments.append(f"清空 {len(removed_fields)} 项")
    summary = f"{name} 本轮补稳：{'，'.join(segments)}"
    if highlighted_labels:
        summary += f"；重点涉及：{'、'.join(highlighted_labels)}"

    return {
        "character": name,
        "summary": summary,
        "changed_count": len(changed_fields),
        "added_count": len(added_fields),
        "rewritten_count": len(rewritten_fields),
        "removed_count": len(removed_fields),
        "changed_fields": changed_fields,
        "changed_field_labels": [FIELD_LABELS.get(field, field) for field in changed_fields],
        "highlight_fields": highlighted[:5],
        "highlight_field_labels": highlighted_labels,
        "has_key_field_changes": any(field in KEY_FIELDS for field in changed_fields),
    }
