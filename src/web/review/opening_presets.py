from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


OPENING_PRESET_FIELDS = (
    "title",
    "note",
    "mode",
    "participants",
    "controlled_character",
    "scene_card_id",
    "scene_card",
    "self_card_id",
    "self_card",
    "self_name",
    "self_identity",
    "self_style",
)
OPENING_PRESET_META_FILE = "card.json"
OPENING_PRESET_DATA_FILE = "opening-preset.json"


def blank_opening_preset_fields() -> dict[str, Any]:
    return {
        "title": "",
        "note": "",
        "mode": "observe",
        "participants": [],
        "controlled_character": "",
        "scene_card_id": "",
        "scene_card": {},
        "self_card_id": "",
        "self_card": {},
        "self_name": "",
        "self_identity": "",
        "self_style": "",
    }


def _normalize_string_list(values: Any) -> list[str]:
    if isinstance(values, str):
        raw_items = values.replace("，", ",").split(",")
    elif isinstance(values, (list, tuple, set)):
        raw_items = list(values)
    else:
        raw_items = []
    deduped: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _normalize_card_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    fields = value.get("fields")
    preview = value.get("preview")
    snapshot = {
        "card_id": str(value.get("card_id", "") or "").strip(),
        "fields": dict(fields) if isinstance(fields, dict) else {},
        "preview": dict(preview) if isinstance(preview, dict) else {},
    }
    return snapshot


def normalize_opening_preset_fields(fields: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(fields or {})
    normalized = blank_opening_preset_fields()
    normalized["title"] = str(source.get("title", "") or "").strip()
    normalized["note"] = str(source.get("note", "") or "").strip()
    mode = str(source.get("mode", "observe") or "observe").strip() or "observe"
    normalized["mode"] = mode if mode in {"observe", "act", "insert"} else "observe"
    normalized["participants"] = _normalize_string_list(source.get("participants", []))
    normalized["controlled_character"] = str(source.get("controlled_character", "") or "").strip()
    normalized["scene_card_id"] = str(source.get("scene_card_id", "") or "").strip()
    normalized["scene_card"] = _normalize_card_snapshot(source.get("scene_card", {}))
    normalized["self_card_id"] = str(source.get("self_card_id", "") or "").strip()
    normalized["self_card"] = _normalize_card_snapshot(source.get("self_card", {}))
    normalized["self_name"] = str(source.get("self_name", "") or "").strip()
    normalized["self_identity"] = str(source.get("self_identity", "") or "").strip()
    normalized["self_style"] = str(source.get("self_style", "") or "").strip()
    return normalized


def validate_opening_preset_fields(fields: dict[str, Any]) -> None:
    if not str(fields.get("title", "")).strip():
        raise ValueError("请先给这套开局模板起个名字。")
    participants = _normalize_string_list(fields.get("participants", []))
    if not participants:
        raise ValueError("请先至少选一位同席人物，再保存模板。")
    mode = str(fields.get("mode", "observe") or "observe").strip() or "observe"
    if mode == "act" and not str(fields.get("controlled_character", "")).strip():
        raise ValueError("化身书中人时，请先写下由你扮演谁。")
    if mode == "insert":
        has_self_card = bool(dict(fields.get("self_card", {}) or {}).get("fields"))
        has_self_profile = any(
            str(fields.get(key, "") or "").strip()
            for key in ("self_name", "self_identity", "self_style")
        )
        if not has_self_card and not has_self_profile:
            raise ValueError("以自己入场时，请先接入角色卡或补全你的入场口径。")


def build_opening_preset_preview(fields: dict[str, Any]) -> dict[str, Any]:
    participants = _normalize_string_list(fields.get("participants", []))
    scene_card = dict(fields.get("scene_card", {}) or {})
    self_card = dict(fields.get("self_card", {}) or {})
    scene_title = str(
        dict(scene_card.get("preview", {}) or {}).get("title")
        or dict(scene_card.get("fields", {}) or {}).get("title")
        or ""
    ).strip()
    self_name = str(fields.get("self_name", "") or "").strip() or str(
        dict(self_card.get("preview", {}) or {}).get("display_name")
        or dict(self_card.get("fields", {}) or {}).get("display_name")
        or ""
    ).strip()
    return {
        "title": str(fields.get("title", "") or "").strip(),
        "note": str(fields.get("note", "") or "").strip(),
        "mode": str(fields.get("mode", "observe") or "observe").strip() or "observe",
        "participants": participants,
        "participant_count": len(participants),
        "controlled_character": str(fields.get("controlled_character", "") or "").strip(),
        "scene_title": scene_title,
        "self_name": self_name,
    }


def _load_card_meta(card_dir: Path) -> dict[str, Any]:
    meta_path = card_dir / OPENING_PRESET_META_FILE
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _load_opening_preset_fields(card_dir: Path) -> dict[str, Any]:
    data_path = card_dir / OPENING_PRESET_DATA_FILE
    if not data_path.exists():
        return blank_opening_preset_fields()
    try:
        return normalize_opening_preset_fields(json.loads(data_path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return blank_opening_preset_fields()


def load_opening_preset_payload(presets_root: Path, card_id: str) -> dict[str, Any]:
    card_dir = presets_root / str(card_id or "").strip()
    if not card_dir.exists():
        raise FileNotFoundError(card_id)
    meta = _load_card_meta(card_dir)
    fields = _load_opening_preset_fields(card_dir)
    return {
        "card_id": card_dir.name,
        "fields": fields,
        "preview": build_opening_preset_preview(fields),
        "created_at": str(meta.get("created_at", "")).strip(),
        "updated_at": str(meta.get("updated_at", "")).strip(),
    }


def list_opening_presets_payload(presets_root: Path) -> list[dict[str, Any]]:
    if not presets_root.exists():
        return []
    items: list[dict[str, Any]] = []
    for card_dir in sorted(path for path in presets_root.iterdir() if path.is_dir()):
        try:
            items.append(load_opening_preset_payload(presets_root, card_dir.name))
        except FileNotFoundError:
            continue
    items.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("card_id", ""))), reverse=True)
    return items


def save_opening_preset_payload(
    presets_root: Path,
    *,
    card_id: str,
    fields: dict[str, Any],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    normalized = normalize_opening_preset_fields(fields)
    validate_opening_preset_fields(normalized)
    resolved_card_id = str(card_id or "").strip() or f"opening-{uuid4().hex[:10]}"
    card_dir = presets_root / resolved_card_id
    if str(card_id or "").strip() and not card_dir.exists():
        raise FileNotFoundError(card_id)
    card_dir.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    meta = _load_card_meta(card_dir) if (card_dir / OPENING_PRESET_META_FILE).exists() else {}
    created_at = str(meta.get("created_at", "")).strip() or now
    (card_dir / OPENING_PRESET_DATA_FILE).write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (card_dir / OPENING_PRESET_META_FILE).write_text(
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
        "preview": build_opening_preset_preview(normalized),
        "created_at": created_at,
        "updated_at": now,
    }


def delete_opening_preset_payload(presets_root: Path, card_id: str) -> dict[str, str]:
    card_dir = presets_root / str(card_id or "").strip()
    if not card_dir.exists():
        raise FileNotFoundError(card_id)
    shutil.rmtree(card_dir)
    return {"status": "deleted", "card_id": card_dir.name}
