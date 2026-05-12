from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


SCENE_CARD_FIELDS = (
    "title",
    "time_hint",
    "location",
    "atmosphere",
    "opening_situation",
    "public_goal",
    "hidden_tension",
    "scene_drive",
    "expected_rhythm",
    "forbidden_topics",
)
SCENE_CARD_REQUIRED_FIELDS = (
    "title",
    "location",
    "atmosphere",
    "opening_situation",
    "scene_drive",
)
SCENE_CARD_META_FILE = "card.json"
SCENE_CARD_DATA_FILE = "scene-card.json"

SCENE_CARD_FIELD_LABELS = {
    "title": "场景名",
    "time_hint": "时间提示",
    "location": "地点",
    "atmosphere": "场面气氛",
    "opening_situation": "开场局面",
    "public_goal": "明面目标",
    "hidden_tension": "暗线张力",
    "scene_drive": "推进方向",
    "expected_rhythm": "节奏手感",
    "forbidden_topics": "不想碰的话头",
}

_GROUP_SCENE_TOKENS = ("众人", "席间", "满座", "同席", "众目", "围坐", "宴", "厅", "堂", "多人")
_DUO_SCENE_TOKENS = ("二人", "对坐", "独处", "檐下", "私谈", "夜谈", "回廊", "亭中", "单独")
_INSERT_SCENE_TOKENS = ("来客", "访客", "外客", "误入", "新到", "初来", "借住", "入席", "登门")
_PLOT_PUSH_TOKENS = ("试探", "摊牌", "转折", "打断", "逼问", "推", "揭", "撞破", "失手", "变局")


def blank_scene_card_fields() -> dict[str, str]:
    return {field: "" for field in SCENE_CARD_FIELDS}


def normalize_scene_card_fields(fields: dict[str, Any] | None) -> dict[str, str]:
    normalized = blank_scene_card_fields()
    for field in SCENE_CARD_FIELDS:
        normalized[field] = str((fields or {}).get(field, "") or "").strip()
    return normalized


def validate_scene_card_fields(fields: dict[str, str]) -> None:
    missing = [SCENE_CARD_FIELD_LABELS.get(field, field) for field in SCENE_CARD_REQUIRED_FIELDS if not str(fields.get(field, "")).strip()]
    if missing:
        raise ValueError(f"请先补全这些必填项：{'、'.join(missing)}")


def build_scene_card_profile(fields: dict[str, str]) -> dict[str, str]:
    return {field: str(fields.get(field, "")).strip() for field in SCENE_CARD_FIELDS}


def list_scene_cards_payload(
    cards_root: Path,
    *,
    load_profile_source: Callable[[Path], dict[str, Any]],
) -> list[dict[str, Any]]:
    if not cards_root.exists():
        return []
    items: list[dict[str, Any]] = []
    for card_dir in sorted(path for path in cards_root.iterdir() if path.is_dir()):
        item = load_scene_card_payload(cards_root, card_dir.name, load_profile_source=load_profile_source)
        if item:
            items.append(item)
    items.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("card_id", ""))), reverse=True)
    return items


def load_scene_card_payload(
    cards_root: Path,
    card_id: str,
    *,
    load_profile_source: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    card_dir = cards_root / str(card_id or "").strip()
    if not card_dir.exists():
        raise FileNotFoundError(card_id)
    meta = _load_card_meta(card_dir)
    fields = _load_scene_card_fields(card_dir, load_profile_source=load_profile_source)
    profile_path = _resolve_card_profile_path(card_dir)
    if profile_path is None and not any(fields.values()):
        raise FileNotFoundError(card_id)
    return {
        "card_id": card_dir.name,
        "fields": fields,
        "preview": build_scene_card_preview(fields),
        "profile_path": str((profile_path or (card_dir / SCENE_CARD_DATA_FILE)).resolve()),
        "created_at": str(meta.get("created_at", "")).strip(),
        "updated_at": str(meta.get("updated_at", "")).strip(),
    }


def save_scene_card_payload(
    cards_root: Path,
    *,
    card_id: str,
    fields: dict[str, Any],
    render_profile_md: Callable[[dict[str, Any]], str],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    normalized = normalize_scene_card_fields(fields)
    validate_scene_card_fields(normalized)

    resolved_card_id = str(card_id or "").strip() or f"scene-{uuid4().hex[:10]}"
    card_dir = cards_root / resolved_card_id
    if str(card_id or "").strip() and not card_dir.exists():
        raise FileNotFoundError(card_id)
    card_dir.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    meta = _load_card_meta(card_dir) if (card_dir / SCENE_CARD_META_FILE).exists() else {}
    created_at = str(meta.get("created_at", "")).strip() or now
    profile = build_scene_card_profile(normalized)
    (card_dir / SCENE_CARD_DATA_FILE).write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (card_dir / "SCENE.md").write_text(_render_scene_card_markdown(profile), encoding="utf-8")
    (card_dir / SCENE_CARD_META_FILE).write_text(
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
        "preview": build_scene_card_preview(normalized),
        "profile_path": str((card_dir / "SCENE.md").resolve()),
        "created_at": created_at,
        "updated_at": now,
    }


def delete_scene_card_payload(cards_root: Path, card_id: str) -> dict[str, str]:
    card_dir = cards_root / str(card_id or "").strip()
    if not card_dir.exists():
        raise FileNotFoundError(card_id)
    shutil.rmtree(card_dir)
    return {"status": "deleted", "card_id": card_dir.name}


def build_scene_card_preview(fields: dict[str, str]) -> dict[str, str]:
    return {
        "title": str(fields.get("title", "")).strip(),
        "time_hint": str(fields.get("time_hint", "")).strip(),
        "location": str(fields.get("location", "")).strip(),
        "atmosphere": str(fields.get("atmosphere", "")).strip(),
        "opening_situation": str(fields.get("opening_situation", "")).strip(),
        "scene_drive": str(fields.get("scene_drive", "")).strip(),
        "expected_rhythm": str(fields.get("expected_rhythm", "")).strip(),
    }


def build_random_scene_card_messages() -> list[dict[str, str]]:
    field_lines = [f'- {field}: {SCENE_CARD_FIELD_LABELS.get(field, field)}' for field in SCENE_CARD_FIELDS]
    return [
        {
            "role": "system",
            "content": (
                "你是中文互动小说的场景卡生成器。请输出一个适合角色对话开场的原创场景卡。"
                "输出必须是 JSON 对象，键只允许来自给定字段；每个字段都给出可直接写入表单的中文内容。"
                "不要解释，不要代码块，不要附加备注。"
            ),
        },
        {
            "role": "user",
            "content": "\n".join(
                [
                    "请随机生成一张完整的原创场景卡。",
                    "要求：",
                    "1. 要能直接拿来开启一段人物互动，而不是世界观设定条目。",
                    "2. 地点、气氛、开场局面要具体，让人一看就知道从哪一拍开始。",
                    "3. 场景推进方向要明确，能自然推动剧情往前。",
                    "4. 列表型字段请用全角分号“；”分隔。",
                    "5. 所有字段都要填写；没有特别禁忌时，也请给自然简短的内容。",
                    "",
                    "字段清单：",
                    *field_lines,
                    "",
                    '返回格式示例：{"title":"...","location":"..."}',
                ]
            ),
        },
    ]


def parse_random_scene_card_response(text: str) -> dict[str, str]:
    payload = _extract_json_object(text)
    if payload is None:
        raise ValueError("模型返回格式不完整。")
    normalized = normalize_scene_card_fields(payload)
    validate_scene_card_fields(normalized)
    for field in SCENE_CARD_FIELDS:
        if not normalized[field]:
            raise ValueError(f"模型没有填完整字段：{SCENE_CARD_FIELD_LABELS.get(field, field)}")
    return normalized


def recommend_scene_cards(
    cards: list[dict[str, Any]],
    *,
    mode: str,
    participants: list[str] | None = None,
) -> dict[str, Any]:
    normalized_mode = str(mode or "observe").strip() or "observe"
    participant_list = [str(item).strip() for item in (participants or []) if str(item).strip()]
    scored_items: list[dict[str, Any]] = []
    for item in cards:
        score, reasons = _score_scene_card(
            dict(item.get("fields", {}) or {}),
            mode=normalized_mode,
            participants=participant_list,
        )
        scored_items.append(
            {
                **item,
                "recommendation": {
                    "score": score,
                    "reasons": reasons,
                },
            }
        )
    scored_items.sort(
        key=lambda item: (
            int(item.get("recommendation", {}).get("score", 0) or 0),
            str(item.get("updated_at", "")),
            str(item.get("card_id", "")),
        ),
        reverse=True,
    )
    recommended_card_id = str(scored_items[0].get("card_id", "")).strip() if scored_items else ""
    return {
        "mode": normalized_mode,
        "participants": participant_list,
        "recommended_card_id": recommended_card_id,
        "items": scored_items,
    }


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
    meta_path = card_dir / SCENE_CARD_META_FILE
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _score_scene_card(
    fields: dict[str, Any],
    *,
    mode: str,
    participants: list[str],
) -> tuple[int, list[str]]:
    normalized = normalize_scene_card_fields(fields)
    combined_text = "\n".join(str(normalized.get(field, "")).strip() for field in SCENE_CARD_FIELDS)
    participant_count = len(participants)
    score = 0
    reasons: list[str] = []

    if normalized["scene_drive"]:
        score += 3
        reasons.append("推进方向明确")
    if normalized["opening_situation"]:
        score += 2
        reasons.append("开场局面具体")
    if normalized["atmosphere"]:
        score += 1
        reasons.append("气氛落点清楚")

    if participant_count >= 3:
        hit = _count_hits(combined_text, _GROUP_SCENE_TOKENS)
        if hit:
            score += 3 + min(2, hit - 1)
            reasons.append("更像多人同席场")
    elif participant_count == 2:
        hit = _count_hits(combined_text, _DUO_SCENE_TOKENS)
        if hit:
            score += 3 + min(1, hit - 1)
            reasons.append("更适合双人拉扯")

    if mode == "insert":
        hit = _count_hits(combined_text, _INSERT_SCENE_TOKENS)
        if hit:
            score += 4 + min(1, hit - 1)
            reasons.append("适合来客/自我入场")
    elif mode == "observe":
        hit = _count_hits(combined_text, _PLOT_PUSH_TOKENS)
        if hit:
            score += 3 + min(2, hit - 1)
            reasons.append("更利于旁观推动剧情")
    elif mode == "act":
        duo_hit = _count_hits(combined_text, _DUO_SCENE_TOKENS)
        if duo_hit:
            score += 2
            reasons.append("留有角色正面接戏空间")

    if normalized["public_goal"]:
        score += 1
    if normalized["hidden_tension"]:
        score += 1
    if normalized["expected_rhythm"]:
        score += 1

    if not reasons:
        reasons.append("信息比较完整，能直接开场")
    return score, reasons[:3]


def _count_hits(text: str, tokens: tuple[str, ...]) -> int:
    compact = str(text or "").strip()
    if not compact:
        return 0
    return sum(1 for token in tokens if token and token in compact)


def _load_scene_card_fields(
    card_dir: Path,
    *,
    load_profile_source: Callable[[Path], dict[str, Any]],
) -> dict[str, str]:
    data_path = card_dir / SCENE_CARD_DATA_FILE
    if data_path.exists():
        try:
            parsed = json.loads(data_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = {}
        return normalize_scene_card_fields(parsed if isinstance(parsed, dict) else {})
    profile_path = _resolve_card_profile_path(card_dir)
    if profile_path is None:
        return blank_scene_card_fields()
    return normalize_scene_card_fields(load_profile_source(profile_path))


def _resolve_card_profile_path(card_dir: Path) -> Path | None:
    for filename in ("SCENE.md", "scene-card.json", "PROFILE.md", "PROFILE.generated.md"):
        candidate = card_dir / filename
        if candidate.exists():
            return candidate
    return None


def _render_scene_card_markdown(fields: dict[str, str]) -> str:
    lines = ["# SCENE CARD", ""]
    for field in SCENE_CARD_FIELDS:
        label = SCENE_CARD_FIELD_LABELS.get(field, field)
        value = str(fields.get(field, "")).strip()
        lines.append(f"## {label}")
        lines.append(value or "（留空）")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
