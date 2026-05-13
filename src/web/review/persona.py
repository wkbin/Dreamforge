from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PROFILE_LIST_FIELDS = {
    "role_tags",
    "life_experience",
    "taboo_topics",
    "forbidden_behaviors",
    "core_traits",
    "fear_triggers",
    "key_bonds",
    "preference_like",
    "dislike_hate",
    "decision_rules",
    "typical_lines",
    "strengths",
    "weaknesses",
    "signature_phrases",
    "sentence_openers",
    "connective_tokens",
    "sentence_endings",
    "forbidden_fillers",
    "cognitive_limits",
}

PROFILE_MAP_FIELDS = {"values"}

PERSONA_REVIEW_FIELDS = (
    "core_identity",
    "story_role",
    "identity_anchor",
    "temperament_type",
    "gender",
    "age_stage",
    "appearance_feature",
    "habit_action",
    "soul_goal",
    "hidden_desire",
    "inner_conflict",
    "self_cognition",
    "private_self",
    "speech_style",
    "cadence",
    "typical_lines",
    "signature_phrases",
    "sentence_openers",
    "sentence_endings",
    "social_mode",
    "thinking_style",
    "decision_rules",
    "reward_logic",
    "worldview",
    "belief_anchor",
    "moral_bottom_line",
    "restraint_threshold",
    "core_traits",
    "key_bonds",
    "preference_like",
    "dislike_hate",
    "forbidden_behaviors",
    "stress_response",
    "emotion_model",
    "anger_style",
    "joy_style",
    "grievance_style",
    "others_impression",
)

_SPEECH_LIST_FIELDS = {
    "signature_phrases",
    "sentence_openers",
    "connective_tokens",
    "sentence_endings",
    "forbidden_fillers",
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


def _persona_review_field_value(profile: dict[str, Any], field: str) -> str:
    if field == "cadence":
        return str((profile.get("speech_habits", {}) or {}).get("cadence", "")).strip() or str(profile.get("cadence", "")).strip()
    if field in _SPEECH_LIST_FIELDS:
        return "；".join(_profile_list_value(profile, field))
    if field in PROFILE_LIST_FIELDS:
        return "；".join(_profile_list_value(profile, field))
    if field in _EMOTION_FIELDS:
        return str((profile.get("emotion_profile", {}) or {}).get(field, "")).strip() or str(profile.get(field, "")).strip()
    if field in PROFILE_MAP_FIELDS:
        value = profile.get(field, {})
        if isinstance(value, dict):
            return "；".join(f"{key}={item}" for key, item in value.items() if str(key).strip())
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
    if field in PROFILE_LIST_FIELDS:
        profile[field] = _split_profile_list_value(value_text)
        return
    if field in _EMOTION_FIELDS:
        profile[field] = value_text
        profile.setdefault("emotion_profile", {})
        profile["emotion_profile"][field] = value_text
        return
    if field in PROFILE_MAP_FIELDS:
        profile[field] = _parse_profile_metric_map(value_text)
        return
    profile[field] = value_text


def _split_profile_list_value(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"\s*[；;]\s*", text) if item.strip()]


def _parse_profile_metric_map(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    parsed: dict[str, Any] = {}
    for part in re.split(r"\s*[；;]\s*", text):
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        key_text = key.strip()
        raw_text = raw.strip()
        if not key_text:
            continue
        try:
            parsed[key_text] = int(raw_text)
        except ValueError:
            parsed[key_text] = raw_text
    return parsed


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
