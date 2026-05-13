from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from src.web.review.persona_completion import PERSONA_REVIEW_FIELD_LABELS
from src.web.review.persona import PERSONA_REVIEW_FIELDS


SELF_CARD_EXTRA_FIELDS = (
    "display_name",
    "scene_identity",
    "interaction_style",
)

SELF_CARD_FIELDS = (*SELF_CARD_EXTRA_FIELDS, *PERSONA_REVIEW_FIELDS)
SELF_CARD_REQUIRED_FIELDS = (
    "display_name",
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
SELF_CARD_META_FILE = "card.json"

SELF_CARD_FIELD_LABELS = {
    "display_name": "角色名",
    "scene_identity": "入场身份",
    "interaction_style": "互动气氛",
    **PERSONA_REVIEW_FIELD_LABELS,
}


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


def read_self_card_fields(
    profile: dict[str, Any],
    *,
    read_persona_review_fields: Callable[[dict[str, Any]], dict[str, str]],
) -> dict[str, str]:
    fields = normalize_self_card_fields(read_persona_review_fields(profile))
    fields["display_name"] = str(profile.get("display_name", "")).strip() or str(profile.get("name", "")).strip()
    fields["scene_identity"] = str(profile.get("scene_identity", "")).strip() or fields["core_identity"]
    fields["interaction_style"] = str(profile.get("interaction_style", "")).strip()
    return fields


def list_self_cards_payload(
    cards_root: Path,
    *,
    load_profile_source: Callable[[Path], dict[str, Any]],
    read_persona_review_fields: Callable[[dict[str, Any]], dict[str, str]],
) -> list[dict[str, Any]]:
    if not cards_root.exists():
        return []
    items: list[dict[str, Any]] = []
    for card_dir in sorted(path for path in cards_root.iterdir() if path.is_dir()):
        item = load_self_card_payload(
            cards_root,
            card_dir.name,
            load_profile_source=load_profile_source,
            read_persona_review_fields=read_persona_review_fields,
        )
        if item:
            items.append(item)
    items.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("card_id", ""))), reverse=True)
    return items


def load_self_card_payload(
    cards_root: Path,
    card_id: str,
    *,
    load_profile_source: Callable[[Path], dict[str, Any]],
    read_persona_review_fields: Callable[[dict[str, Any]], dict[str, str]],
) -> dict[str, Any]:
    card_dir = cards_root / str(card_id or "").strip()
    if not card_dir.exists():
        raise FileNotFoundError(card_id)
    meta = _load_card_meta(card_dir)
    profile_path = _resolve_card_profile_path(card_dir)
    if profile_path is None:
        raise FileNotFoundError(card_id)
    profile = load_profile_source(profile_path)
    fields = read_self_card_fields(profile, read_persona_review_fields=read_persona_review_fields)
    return {
        "card_id": card_dir.name,
        "fields": fields,
        "preview": build_self_card_preview(fields),
        "profile_path": str(profile_path.resolve()),
        "created_at": str(meta.get("created_at", "")).strip(),
        "updated_at": str(meta.get("updated_at", "")).strip(),
    }


def save_self_card_payload(
    cards_root: Path,
    *,
    card_id: str,
    fields: dict[str, Any],
    render_profile_md: Callable[[dict[str, Any]], str],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    normalized = normalize_self_card_fields(fields)
    validate_self_card_fields(normalized)

    resolved_card_id = str(card_id or "").strip() or f"card-{uuid4().hex[:10]}"
    card_dir = cards_root / resolved_card_id
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
    return {
        "card_id": resolved_card_id,
        "fields": normalized,
        "preview": build_self_card_preview(normalized),
        "profile_path": str((card_dir / "PROFILE.md").resolve()),
        "created_at": created_at,
        "updated_at": now,
    }


def delete_self_card_payload(cards_root: Path, card_id: str) -> dict[str, str]:
    card_dir = cards_root / str(card_id or "").strip()
    if not card_dir.exists():
        raise FileNotFoundError(card_id)
    shutil.rmtree(card_dir)
    return {"status": "deleted", "card_id": card_dir.name}


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


def build_random_self_card_messages() -> list[dict[str, str]]:
    field_lines = [f'- {field}: {SELF_CARD_FIELD_LABELS.get(field, field)}' for field in SELF_CARD_FIELDS]
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
    for field in SELF_CARD_REQUIRED_FIELDS:
        if not normalized[field]:
            raise ValueError(f"模型没有填完整字段：{SELF_CARD_FIELD_LABELS.get(field, field)}")
    return normalized


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
