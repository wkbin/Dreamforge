#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .persona_bundle import load_profile_source, render_profile_md

PERSONA_REVIEW_FIELD_LABELS = {
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

PERSONA_REVIEW_FIELDS = tuple(PERSONA_REVIEW_FIELD_LABELS.keys())

PERSONA_REVIEW_KEY_FIELDS = (
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

PERSONA_REVIEW_ADVANCED_GROUPS = (
    (
        "内核细调",
        (
            "hidden_desire",
            "inner_conflict",
            "self_cognition",
            "private_self",
            "social_mode",
            "thinking_style",
            "decision_rules",
            "reward_logic",
            "others_impression",
        ),
    ),
    (
        "对白细调",
        (
            "cadence",
            "typical_lines",
            "signature_phrases",
            "sentence_openers",
            "sentence_endings",
        ),
    ),
    (
        "情绪细调",
        (
            "forbidden_behaviors",
            "emotion_model",
            "anger_style",
            "joy_style",
            "grievance_style",
        ),
    ),
)

PERSONA_AUTOFILLABLE_FIELDS = {
    "core_identity",
    "story_role",
    "identity_anchor",
    "temperament_type",
    "soul_goal",
    "hidden_desire",
    "inner_conflict",
    "self_cognition",
    "private_self",
    "speech_style",
    "social_mode",
    "thinking_style",
    "worldview",
    "belief_anchor",
    "moral_bottom_line",
    "core_traits",
    "key_bonds",
    "others_impression",
}

SELF_CARD_EXTRA_FIELDS = (
    "display_name",
    "scene_identity",
    "interaction_style",
)
SELF_CARD_FIELDS = (*SELF_CARD_EXTRA_FIELDS, *PERSONA_REVIEW_FIELDS)
SELF_CARD_REQUIRED_FIELDS = ("display_name", *PERSONA_REVIEW_KEY_FIELDS)
SELF_CARD_META_FILE = "card.json"

SELF_CARD_FIELD_LABELS = {
    "display_name": "角色名",
    "scene_identity": "入场身份",
    "interaction_style": "互动气氛",
    **PERSONA_REVIEW_FIELD_LABELS,
}

_LIST_STYLE_FIELDS = {"core_traits", "key_bonds"}
_USER_AGENT = "zaomeng-persona-review/1.0 (+https://github.com/wkbin/zaomeng)"
_SPEECH_LIST_FIELDS = {
    "signature_phrases",
    "sentence_openers",
    "sentence_endings",
    "typical_lines",
}
_PROFILE_LIST_FIELDS = {
    "core_traits",
    "key_bonds",
    "decision_rules",
    "forbidden_behaviors",
}
_EMOTION_FIELDS = {"anger_style", "joy_style", "grievance_style"}


def resolve_persona_review_source(persona_dir: str | Path) -> tuple[Path, Path, Path]:
    persona_path = Path(persona_dir)
    editable_path = persona_path / "PROFILE.md"
    generated_path = persona_path / "PROFILE.generated.md"
    source_path = editable_path if editable_path.exists() else generated_path
    return editable_path, generated_path, source_path


def read_persona_review_fields(profile: dict[str, Any]) -> dict[str, str]:
    return {field: _persona_review_field_value(profile, field) for field in PERSONA_REVIEW_FIELDS}


def apply_persona_review_updates(profile: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    for field in PERSONA_REVIEW_FIELDS:
        if field not in fields:
            continue
        _apply_persona_review_field(profile, field, fields.get(field, ""))
    return profile


def load_persona_review_payload(persona_dir: str | Path) -> dict[str, Any]:
    editable_path, generated_path, source_path = resolve_persona_review_source(persona_dir)
    if not source_path.exists():
        raise FileNotFoundError(str(persona_dir))
    profile = load_profile_source(source_path)
    return {
        "persona_dir": str(Path(persona_dir).resolve()),
        "editable_profile_path": str(editable_path.resolve()) if editable_path.exists() else "",
        "generated_profile_path": str(generated_path.resolve()) if generated_path.exists() else "",
        "fields": read_persona_review_fields(profile),
        "name": str(profile.get("name", "")).strip() or Path(persona_dir).name,
        "novel_id": str(profile.get("novel_id", "")).strip(),
        "novel_title": resolve_novel_title(profile=profile),
    }


def save_persona_review_profile(persona_dir: str | Path, fields: dict[str, Any]) -> dict[str, Any]:
    editable_path, _, source_path = resolve_persona_review_source(persona_dir)
    if not source_path.exists():
        raise FileNotFoundError(str(persona_dir))
    profile = load_profile_source(source_path)
    apply_persona_review_updates(profile, fields)
    editable_path.parent.mkdir(parents=True, exist_ok=True)
    editable_path.write_text(render_profile_md(profile), encoding="utf-8")
    return load_persona_review_payload(persona_dir)


def build_persona_field_completion_messages(
    *,
    character: str,
    field: str,
    novel_title: str,
    current_fields: dict[str, str],
    references: list[dict[str, str]] | None = None,
    use_model_knowledge: bool = False,
) -> list[dict[str, str]]:
    label = PERSONA_REVIEW_FIELD_LABELS.get(field, field)
    profile_summary = _render_profile_summary(current_fields, exclude_field=field)
    reference_text = _render_reference_summary(references or [])
    list_hint = "如果该字段适合多项值，请用全角分号“；”分隔。" if field in _LIST_STYLE_FIELDS else "只输出一个可直接落表单的自然中文结论。"
    if use_model_knowledge:
        user_prompt = "\n".join(
            [
                f"人物：{character}",
                f"作品：{novel_title or '未知作品'}",
                f"目标字段：{label} ({field})",
                "",
                "当前已知人物档案：",
                profile_summary or "（暂无其他已知字段）",
                "",
                "请先只依据你对该作品和角色的已有知识来判断能否补全这个字段。",
                "如果这是常见作品、经典角色、或你对该角色有稳定把握，可以直接给出适合写入人物校对表单的内容。",
                "如果你拿不准、记忆模糊、或只能靠猜测，请明确拒绝生成。",
                list_hint,
                "value 字段只能放最终要写入表单的内容，不能包含“我们要求”“需要从”“已知有”“可以根据”等分析过程。",
                "不要编造，不要输出剧情摘要，不要伪装成查到网页资料。",
                '严格返回 JSON：{"status":"filled"|"insufficient","value":"...","reason":"..."}',
            ]
        )
        system_content = (
            "你是人物资料补全助手。任务是优先根据模型已有知识，为单个角色字段生成可直接写入表单的短内容。"
            "只有在你对角色有稳定把握时才可填写；只要不确定，就必须返回 insufficient。"
            "禁止在 value 中复述任务、解释推理、列出要求，value 必须是可直接粘贴进表单的最终中文。"
        )
    else:
        user_prompt = "\n".join(
            [
                f"人物：{character}",
                f"作品：{novel_title or '未知作品'}",
                f"目标字段：{label} ({field})",
                "",
                "当前已知人物档案：",
                profile_summary or "（暂无其他已知字段）",
                "",
                "联网检索摘录：",
                reference_text or "（暂无可用网页摘录）",
                "",
                "请只根据联网摘录判断能否补全这个字段。",
                "如果资料足够，返回一段适合直接写入人物校对表单的内容。",
                "如果资料不足、互相矛盾、或只能靠脑补，请明确拒绝生成。",
                list_hint,
                "value 字段只能放最终要写入表单的内容，不能包含“我们要求”“需要从”“已知有”“可以根据”等分析过程。",
                "不要编造，不要把剧情长摘要塞进字段。",
                '严格返回 JSON：{"status":"filled"|"insufficient","value":"...","reason":"..."}',
            ]
        )
        system_content = (
            "你是人物资料补全助手。任务是根据给定的网页摘录，为单个角色字段生成可直接写入表单的短内容。"
            "只有在网页摘录能支撑时才可填写；只要证据不足，就必须返回 insufficient。"
            "禁止在 value 中复述任务、解释推理、列出要求，value 必须是可直接粘贴进表单的最终中文。"
        )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]


def build_persona_field_retry_messages(
    *,
    character: str,
    field: str,
    novel_title: str,
    current_fields: dict[str, str],
    references: list[dict[str, str]] | None = None,
    use_model_knowledge: bool = False,
) -> list[dict[str, str]]:
    label = PERSONA_REVIEW_FIELD_LABELS.get(field, field)
    profile_summary = _render_profile_summary(current_fields, exclude_field=field)
    reference_text = _render_reference_summary(references or [])
    if use_model_knowledge:
        user_prompt = "\n".join(
            [
                f"人物：{character}",
                f"作品：{novel_title or '未知作品'}",
                f"目标字段：{label} ({field})",
                "",
                "当前已知人物档案：",
                profile_summary or "（暂无其他已知字段）",
                "",
                "上一轮输出格式不对。",
                "现在不要 JSON，不要代码块，不要解释。",
                "如果你对该角色有稳定把握，只返回一句可直接写入表单的中文内容。",
                "如果你拿不准，就只返回：证据不足",
            ]
        )
    else:
        user_prompt = "\n".join(
            [
                f"人物：{character}",
                f"作品：{novel_title or '未知作品'}",
                f"目标字段：{label} ({field})",
                "",
                "当前已知人物档案：",
                profile_summary or "（暂无其他已知字段）",
                "",
                "联网检索摘录：",
                reference_text or "（暂无可用网页摘录）",
                "",
                "上一轮输出格式不对。",
                "现在不要 JSON，不要代码块，不要解释。",
                "如果这些摘录足够支持结论，只返回一句可直接写入表单的中文内容。",
                "如果仍然不足，就只返回：证据不足",
            ]
        )
    return [
        {"role": "system", "content": "你是人物资料补全助手。只返回最终结果本身，不要附加格式。"},
        {"role": "user", "content": user_prompt},
    ]


def parse_persona_field_completion_response(text: str) -> dict[str, str]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL).strip()
    payload = _extract_json_object(cleaned)
    if payload is None:
        return _infer_plaintext_completion(cleaned)
    status = str(payload.get("status", "")).strip().lower()
    raw_value = str(payload.get("value", "")).strip()
    value = _clean_completion_value(raw_value)
    reason = str(payload.get("reason", "")).strip()
    if status == "filled" and not value:
        return {"status": "insufficient", "value": "", "reason": "模型没有返回可直接写入表单的最终内容。"}
    if status != "filled" or not value:
        return {"status": "insufficient", "value": "", "reason": reason or "资料不足，无法可靠补全。"}
    return {"status": "filled", "value": value, "reason": reason}


def collect_persona_web_references(
    *,
    character: str,
    novel_title: str = "",
    timeout_seconds: float = 8.0,
    fetch_text: Callable[[str, float], str] | None = None,
) -> list[dict[str, str]]:
    fetcher = fetch_text or _fetch_text
    queries = _build_search_queries(character=character, novel_title=novel_title)
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for query in queries:
        for item in _search_bing(
            query,
            character=character,
            novel_title=novel_title,
            timeout_seconds=timeout_seconds,
            fetch_text=fetcher,
        ):
            key = (item.get("title", ""), item.get("snippet", ""))
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= 6:
                return results
    return results


def resolve_novel_title(*, profile: dict[str, Any]) -> str:
    for candidate in (
        profile.get("novel_title"),
        profile.get("novel_name"),
        profile.get("novel_id"),
    ):
        text = str(candidate or "").strip()
        if text:
            return re.sub(r"\.(txt|md|text|epub)$", "", text, flags=re.IGNORECASE)
    return ""


def blank_self_card_fields() -> dict[str, str]:
    return {field: "" for field in SELF_CARD_FIELDS}


def normalize_self_card_fields(fields: dict[str, Any] | None) -> dict[str, str]:
    normalized = blank_self_card_fields()
    for field in SELF_CARD_FIELDS:
        normalized[field] = str((fields or {}).get(field, "") or "").strip()
    if not normalized["scene_identity"]:
        normalized["scene_identity"] = normalized["core_identity"]
    return normalized


def validate_self_card_fields(fields: dict[str, str]) -> None:
    missing = [SELF_CARD_FIELD_LABELS.get(field, field) for field in SELF_CARD_REQUIRED_FIELDS if not str(fields.get(field, "")).strip()]
    if missing:
        raise ValueError(f"请先补全这些必填项：{'、'.join(missing)}")


def build_self_card_profile(fields: dict[str, str]) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "name": str(fields.get("display_name", "")).strip(),
        "display_name": str(fields.get("display_name", "")).strip(),
        "scene_identity": str(fields.get("scene_identity", "")).strip() or str(fields.get("core_identity", "")).strip(),
        "interaction_style": str(fields.get("interaction_style", "")).strip(),
        "novel_id": "__self_card__",
    }
    for field in PERSONA_REVIEW_FIELDS:
        value = str(fields.get(field, "")).strip()
        if value:
            profile[field] = value
    return profile


def read_self_card_fields(profile: dict[str, Any]) -> dict[str, str]:
    fields = normalize_self_card_fields(read_persona_review_fields(profile))
    fields["display_name"] = str(profile.get("display_name", "")).strip() or str(profile.get("name", "")).strip()
    fields["scene_identity"] = str(profile.get("scene_identity", "")).strip() or fields["core_identity"]
    fields["interaction_style"] = str(profile.get("interaction_style", "")).strip()
    return fields


def build_self_card_preview(fields: dict[str, str]) -> dict[str, str]:
    return {
        "display_name": str(fields.get("display_name", "")).strip(),
        "scene_identity": str(fields.get("scene_identity", "")).strip(),
        "core_identity": str(fields.get("core_identity", "")).strip(),
        "story_role": str(fields.get("story_role", "")).strip(),
        "temperament_type": str(fields.get("temperament_type", "")).strip(),
        "speech_style": str(fields.get("speech_style", "")).strip(),
        "soul_goal": str(fields.get("soul_goal", "")).strip(),
    }


def list_self_cards_payload(cards_root: str | Path) -> list[dict[str, Any]]:
    root = Path(cards_root)
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for card_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        item = load_self_card_payload(root, card_dir.name)
        if item:
            items.append(item)
    items.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("card_id", ""))), reverse=True)
    return items


def load_self_card_payload(cards_root: str | Path, card_id: str) -> dict[str, Any]:
    card_dir = Path(cards_root) / str(card_id or "").strip()
    if not card_dir.exists():
        raise FileNotFoundError(card_id)
    meta = _load_card_meta(card_dir)
    profile_path = _resolve_card_profile_path(card_dir)
    if profile_path is None:
        raise FileNotFoundError(card_id)
    profile = load_profile_source(profile_path)
    fields = read_self_card_fields(profile)
    return {
        "card_id": card_dir.name,
        "fields": fields,
        "preview": build_self_card_preview(fields),
        "profile_path": str(profile_path.resolve()),
        "created_at": str(meta.get("created_at", "")).strip(),
        "updated_at": str(meta.get("updated_at", "")).strip(),
    }


def save_self_card_payload(cards_root: str | Path, *, card_id: str, fields: dict[str, Any], utc_now: Callable[[], str]) -> dict[str, Any]:
    normalized = normalize_self_card_fields(fields)
    validate_self_card_fields(normalized)

    resolved_card_id = str(card_id or "").strip() or f"card-{_safe_id(normalized.get('display_name', 'self'))}"
    card_dir = Path(cards_root) / resolved_card_id
    if str(card_id or "").strip() and not card_dir.exists():
        raise FileNotFoundError(card_id)
    card_dir.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    meta = _load_card_meta(card_dir) if (card_dir / SELF_CARD_META_FILE).exists() else {}
    created_at = str(meta.get("created_at", "")).strip() or now
    profile = build_self_card_profile(normalized)
    (card_dir / "PROFILE.md").write_text(render_profile_md(profile), encoding="utf-8")
    (card_dir / SELF_CARD_META_FILE).write_text(
        json.dumps(
            {
                "card_id": resolved_card_id,
                "created_at": created_at,
                "updated_at": now,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return load_self_card_payload(cards_root, resolved_card_id)


def delete_self_card_payload(cards_root: str | Path, card_id: str) -> dict[str, str]:
    card_dir = Path(cards_root) / str(card_id or "").strip()
    if not card_dir.exists():
        raise FileNotFoundError(card_id)
    for path in sorted(card_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    card_dir.rmdir()
    return {"status": "deleted", "card_id": card_dir.name}


def build_random_self_card_messages() -> list[dict[str, str]]:
    field_lines = [f"- {field}: {SELF_CARD_FIELD_LABELS.get(field, field)}" for field in SELF_CARD_FIELDS]
    return [
        {
            "role": "system",
            "content": (
                "你是原创角色卡生成器。请生成一个适合中文小说互动场景的原创角色，不依赖任何现有作品。"
                "输出必须是 JSON 对象，键只允许来自给定字段；每个字段都给出可直接写入表单的中文短内容。"
                "不要解释，不要代码块，不要附加备注。"
            ),
        },
        {
            "role": "user",
            "content": "\n".join(
                [
                    "请随机生成一张完整的原创角色卡。",
                    "要求：",
                    "1. 这是用于“以自己入场”的角色卡，所以要有明确称呼、入场身份、互动气氛。",
                    "2. 关键字段必须具体，避免空泛词。",
                    "3. 列表型字段请用全角分号“；”分隔。",
                    "4. 所有字段都要填写；实在不需要的细字段也请给一句简短但自然的内容。",
                    "5. 保持前后一致，语气偏小说角色设定，而不是现实简历。",
                    "",
                    "字段清单：",
                    *field_lines,
                    "",
                    '返回格式示例：{"display_name":"...","scene_identity":"..."}',
                ]
            ),
        },
    ]


def parse_random_self_card_response(text: str) -> dict[str, str]:
    payload = _extract_json_object(text)
    if payload is None:
        raise ValueError("模型返回格式不完整。")
    normalized = normalize_self_card_fields(payload)
    validate_self_card_fields(normalized)
    for field in PERSONA_REVIEW_FIELDS:
        if not normalized[field]:
            raise ValueError(f"模型没有填完整字段：{SELF_CARD_FIELD_LABELS.get(field, field)}")
    return normalized


def _persona_review_field_value(profile: dict[str, Any], field: str) -> str:
    if field == "cadence":
        return str((profile.get("speech_habits", {}) or {}).get("cadence", "")).strip() or str(profile.get("cadence", "")).strip()
    if field in _SPEECH_LIST_FIELDS:
        return "；".join(_profile_list_value(profile, field))
    if field in _PROFILE_LIST_FIELDS:
        return "；".join(_profile_list_value(profile, field))
    if field in _EMOTION_FIELDS:
        return str((profile.get("emotion_profile", {}) or {}).get(field, "")).strip() or str(profile.get(field, "")).strip()
    return str(profile.get(field, "") or "").strip()


def _apply_persona_review_field(profile: dict[str, Any], field: str, value: Any) -> None:
    value_text = str(value or "").strip()
    if field == "cadence":
        profile["cadence"] = value_text
        profile.setdefault("speech_habits", {})
        profile["speech_habits"]["cadence"] = value_text
        return
    if field in _SPEECH_LIST_FIELDS:
        items = _split_profile_list_value(value_text)
        profile[field] = items
        profile.setdefault("speech_habits", {})
        profile["speech_habits"][field] = list(items)
        return
    if field in _PROFILE_LIST_FIELDS:
        profile[field] = _split_profile_list_value(value_text)
        return
    if field in _EMOTION_FIELDS:
        profile[field] = value_text
        profile.setdefault("emotion_profile", {})
        profile["emotion_profile"][field] = value_text
        return
    profile[field] = value_text


def _split_profile_list_value(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"\s*[；;]\s*", text) if item.strip()]


def _profile_list_value(profile: dict[str, Any], key: str) -> list[str]:
    direct = profile.get(key, [])
    if isinstance(direct, list):
        return [str(item).strip() for item in direct if str(item).strip()]
    speech_habits = profile.get("speech_habits", {})
    if isinstance(speech_habits, dict):
        nested = speech_habits.get(key, [])
        if isinstance(nested, list):
            return [str(item).strip() for item in nested if str(item).strip()]
    return []


def _render_profile_summary(fields: dict[str, str], *, exclude_field: str) -> str:
    lines: list[str] = []
    for key, label in PERSONA_REVIEW_FIELD_LABELS.items():
        if key == exclude_field:
            continue
        value = str(fields.get(key, "")).strip()
        if value:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines[:14])


def _render_reference_summary(references: list[dict[str, str]]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(references[:6], start=1):
        title = str(item.get("title", "")).strip() or f"结果 {index}"
        snippet = str(item.get("snippet", "")).strip()
        source = str(item.get("source", "")).strip()
        if not snippet:
            continue
        blocks.append(f"[{index}] {title}\n来源: {source or '网页摘要'}\n摘要: {snippet}")
    return "\n\n".join(blocks)


def _build_search_queries(*, character: str, novel_title: str) -> list[str]:
    base = str(character or "").strip()
    book = str(novel_title or "").strip()
    queries = [
        f"\"{base}\" \"{book}\" 人物介绍 角色".strip(),
        f"\"{base}\" \"{book}\" 人物分析 角色设定".strip(),
        f"\"{base}\" \"{book}\" 性格特点 人物".strip(),
        f"\"{base}\" \"{book}\" 角色介绍".strip(),
        f"\"{base}\" 人物介绍 {book}".strip(),
        f"\"{base}\" 角色设定 {book}".strip(),
    ]
    return [item for item in dict.fromkeys(queries) if item]


def _search_bing(
    query: str,
    *,
    character: str,
    novel_title: str,
    timeout_seconds: float,
    fetch_text: Callable[[str, float], str],
) -> list[dict[str, str]]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=zh-Hans"
    try:
        page = fetch_text(url, timeout_seconds)
    except Exception:
        return []
    blocks = re.findall(r'<li class="b_algo".*?</li>', page, flags=re.DOTALL | re.IGNORECASE)
    results: list[dict[str, str]] = []
    for block in blocks:
        title_match = re.search(r"<h2[^>]*>(.*?)</h2>", block, flags=re.DOTALL | re.IGNORECASE)
        snippet_match = re.search(r"<p[^>]*>(.*?)</p>", block, flags=re.DOTALL | re.IGNORECASE)
        title = _html_to_text(title_match.group(1)) if title_match else ""
        snippet = _html_to_text(snippet_match.group(1)) if snippet_match else ""
        if len(snippet) < 18:
            continue
        if _looks_like_dictionary_result(title=title, snippet=snippet):
            continue
        if not _looks_like_character_result(
            title=title,
            snippet=snippet,
            character=character,
            novel_title=novel_title,
        ):
            continue
        results.append(
            {
                "title": title,
                "snippet": snippet,
                "source": "Bing",
                "query": query,
            }
        )
        if len(results) >= 4:
            break
    return results


def _fetch_text(url: str, timeout_seconds: float) -> str:
    request = Request(url, headers={"User-Agent": _USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def _html_to_text(value: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", str(value or ""), flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _looks_like_dictionary_result(*, title: str, snippet: str) -> bool:
    haystack = f"{title}\n{snippet}".lower()
    junk_keywords = (
        "汉语字典",
        "汉语词典",
        "词典",
        "字典",
        "康熙字典",
        "汉典",
        "每日一字",
        "部首",
        "拼音",
        "笔画",
        "释义",
        "字义",
        "怎么读",
        "什么意思",
        "通用规范汉字",
        "一级字",
        "二级字",
        "三级字",
    )
    return any(keyword in haystack for keyword in junk_keywords)


def _looks_like_character_result(*, title: str, snippet: str, character: str, novel_title: str) -> bool:
    joined = f"{title}\n{snippet}"
    normalized_character = str(character or "").strip()
    normalized_novel = str(novel_title or "").strip()
    if normalized_character and normalized_character not in joined:
        return False
    if len(normalized_character) <= 1 and normalized_novel and normalized_novel not in joined:
        return False
    if normalized_novel:
        novel_hit = normalized_novel in joined
        role_hit = any(token in joined for token in ("人物", "角色", "主角", "配角", "设定", "性格"))
        return novel_hit or role_hit
    return True


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _infer_plaintext_completion(text: str) -> dict[str, str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return {"status": "insufficient", "value": "", "reason": "模型没有返回可用内容。"}
    normalized = cleaned.replace("\r", "")
    if _looks_like_broken_json_value_fragment(normalized):
        return {"status": "insufficient", "value": "", "reason": "模型返回格式不完整。"}
    refusal_markers = (
        "证据不足",
        "资料不足",
        "信息不足",
        "无法可靠",
        "无法判断",
        "不确定",
        "拿不准",
        "把握不够",
        "记忆模糊",
        "不能确定",
        "无法生成",
        "insufficient",
    )
    if any(marker in normalized for marker in refusal_markers):
        return {"status": "insufficient", "value": "", "reason": cleaned}

    extracted = _extract_completion_candidate_from_meta_text(normalized)
    if extracted:
        return {"status": "filled", "value": extracted, "reason": "已从分析式返回中提取最终结果。"}

    value_match = re.search(r'(?:^|\n)(?:value|答案|建议|可写为|可填写|补全建议)\s*[:：]\s*(.+)', normalized, flags=re.IGNORECASE)
    if value_match:
        candidate = value_match.group(1).strip()
    else:
        lines = [line.strip(" -\t") for line in normalized.splitlines() if line.strip()]
        candidate = lines[0] if lines else normalized

    candidate = _clean_completion_value(candidate)
    if not candidate and _looks_like_meta_reasoning(normalized):
        return {"status": "insufficient", "value": "", "reason": "模型返回了思考过程，没有直接给出最终结果。"}
    if not candidate:
        return {"status": "insufficient", "value": "", "reason": "模型返回格式不完整。"}
    return {"status": "filled", "value": candidate, "reason": "已从自然语言返回中提取结果。"}


def _clean_completion_value(text: str) -> str:
    candidate = str(text or "").strip()
    if not candidate:
        return ""
    extracted = _extract_completion_candidate_from_meta_text(candidate)
    if extracted:
        candidate = extracted
    candidate = re.sub(r"^(可以写成|可写成|建议填写|建议写为|可填写|可写为|答案|建议)\s*[:：]?\s*", "", candidate).strip()
    candidate = candidate.strip('"').strip("“”")
    candidate = re.sub(r"\s+", " ", candidate)
    if _looks_like_meta_reasoning(candidate):
        return ""
    if _looks_like_truncated_completion_value(candidate):
        return ""
    if not _looks_like_usable_completion_value(candidate):
        return ""
    return candidate


def _looks_like_usable_completion_value(value: str) -> bool:
    text = str(value or "").strip()
    if len(text) < 2:
        return False
    if re.fullmatch(r"[\{\}\[\]\(\):：,，.;；'\"`]+", text):
        return False
    if _looks_like_broken_json_value_fragment(text):
        return False
    if _looks_like_truncated_completion_value(text):
        return False
    return True


def _looks_like_truncated_completion_value(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.endswith(("、", "，", ",", "；", ";", "：", ":", "/", "（", "(", "《", "“", "\"")):
        return True
    if text.count("（") > text.count("）"):
        return True
    if text.count("(") > text.count(")"):
        return True
    return False


def _looks_like_broken_json_value_fragment(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if re.search(r'["\']value["\']\s*:', normalized, flags=re.IGNORECASE):
        return True
    if re.search(r'["\'](?:status|reason)["\']\s*:', normalized, flags=re.IGNORECASE):
        return True
    return False


def _looks_like_meta_reasoning(text: str) -> bool:
    normalized = str(text or "").strip()
    meta_markers = (
        "我们被要求",
        "我们要求",
        "我知道",
        "我觉得",
        "我会给出",
        "我认为",
        "需要提取",
        "需要从",
        "已知有",
        "既然是",
        "理由：",
        "理由:",
        "可以提供",
        "可以根据",
        "我对这个角色",
    )
    return any(marker in normalized for marker in meta_markers)


def _extract_completion_candidate_from_meta_text(text: str) -> str:
    normalized = str(text or "").strip()
    patterns = (
        r"(?:可以根据[^。；\n]{0,60}写|可根据[^。；\n]{0,60}写)\s*[:：]\s*(.+?)(?:。理由[:：]|理由[:：]|$)",
        r"(?:可以给出|可给出|建议写成|建议填写|可写为|可填写)\s*[:：]\s*(.+?)(?:。理由[:：]|理由[:：]|$)",
        r"(?:最终答案|最终可写为|最终建议)\s*[:：]\s*(.+?)(?:。理由[:：]|理由[:：]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.DOTALL)
        if not match:
            continue
        candidate = match.group(1).strip().strip('"').strip("“”")
        candidate = re.sub(r"\s+", " ", candidate)
        if (
            _looks_like_usable_completion_value(candidate)
            and not _looks_like_meta_reasoning(candidate)
            and not _looks_like_truncated_completion_value(candidate)
        ):
            return candidate

    list_like_match = re.search(r"([^。；\n]*；[^。]*)(?:。|$)", normalized)
    if list_like_match:
        candidate = list_like_match.group(1).strip()
        candidate = re.sub(r"^(?:我觉得我可以给出|可以给出|我会给出)\s*[:：]?\s*", "", candidate)
        if (
            _looks_like_usable_completion_value(candidate)
            and not _looks_like_meta_reasoning(candidate)
            and not _looks_like_truncated_completion_value(candidate)
        ):
            return candidate
    return ""


def _load_card_meta(card_dir: Path) -> dict[str, Any]:
    meta_path = card_dir / SELF_CARD_META_FILE
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _resolve_card_profile_path(card_dir: Path) -> Path | None:
    for candidate_name in ("PROFILE.md", "PROFILE.generated.md"):
        candidate = card_dir / candidate_name
        if candidate.exists():
            return candidate
    return None


def _safe_id(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", str(value or "").strip())
    slug = slug.strip("-_")
    return slug or "self-card"
