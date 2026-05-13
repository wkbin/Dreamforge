#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable

from .workflow_completion import build_persona_completion_status, write_json

DEFAULT_NAV_LOAD_ORDER = (
    "SOUL",
    "GOALS",
    "STYLE",
    "TRAUMA",
    "IDENTITY",
    "BACKGROUND",
    "CAPABILITY",
    "BONDS",
    "CONFLICTS",
    "ROLE",
    "AGENTS",
    "RELATIONS",
    "MEMORY",
)

PERSONA_FILE_CATALOG = {
    "SOUL": {
        "optional": False,
        "role": "core values, worldview, boundaries",
        "behaviors": "stance, taboo, refusal, value judgment",
        "write_policy": "manual_edit",
    },
    "GOALS": {
        "optional": True,
        "role": "long-term drive, unresolved desire, strategic priority",
        "behaviors": "decision preference, long arc pressure, ambition",
        "write_policy": "manual_edit",
    },
    "STYLE": {
        "optional": True,
        "role": "signature phrasing, cadence, surface emotion, sample lines",
        "behaviors": "word choice, sentence length, tone, recurring fragments",
        "write_policy": "manual_edit",
    },
    "TRAUMA": {
        "optional": True,
        "role": "pain points, scars, triggers, never-do rules",
        "behaviors": "trigger reactions, avoidance, hard boundaries",
        "write_policy": "manual_edit",
    },
    "IDENTITY": {
        "optional": False,
        "role": "background, lived experience, habits, emotion profile",
        "behaviors": "self-reference, memory framing, habit-driven reactions",
        "write_policy": "manual_edit",
    },
    "BACKGROUND": {
        "optional": True,
        "role": "world identity, faction position, environment imprint, survival context",
        "behaviors": "camp alignment, social rank, environmental pressure, worldview fit",
        "write_policy": "manual_edit",
    },
    "CAPABILITY": {
        "optional": True,
        "role": "strengths, weaknesses, blind spots, action tendency",
        "behaviors": "what the character is good at, where they fail, how they overreach",
        "write_policy": "manual_edit",
    },
    "BONDS": {
        "optional": True,
        "role": "relationship habits, trust boundary, reward-and-resentment logic",
        "behaviors": "how the character treats allies, strangers, enemies, and debts",
        "write_policy": "manual_edit",
    },
    "CONFLICTS": {
        "optional": True,
        "role": "hidden desire, inner contradiction, fear triggers, private self",
        "behaviors": "internal pull, weakness exposure, private vs public self",
        "write_policy": "manual_edit",
    },
    "ROLE": {
        "optional": True,
        "role": "story function, stance stability, world-rule compatibility",
        "behaviors": "plot pressure, pivot role, alignment stability",
        "write_policy": "manual_edit",
    },
    "AGENTS": {
        "optional": False,
        "role": "runtime behavior rules, silence policy, group chat routing",
        "behaviors": "when to speak, when to hold back, how to engage others",
        "write_policy": "manual_edit",
    },
    "RELATIONS": {
        "optional": True,
        "role": "target-specific trust, affection, appellations, friction points",
        "behaviors": "tone toward each character, appellations, conflict framing",
        "write_policy": "manual_edit",
    },
    "MEMORY": {
        "optional": False,
        "role": "stable notes plus runtime write-back from user guidance and corrections",
        "behaviors": "persistent user constraints, correction carry-over, mutable notes",
        "write_policy": "runtime_append",
    },
}

LIST_FIELDS = {
    "role_tags",
    "life_experience",
    "taboo_topics",
    "forbidden_behaviors",
    "core_traits",
    "cognitive_limits",
    "decision_rules",
    "fear_triggers",
    "key_bonds",
    "preference_like",
    "dislike_hate",
    "typical_lines",
    "strengths",
    "weaknesses",
    "signature_phrases",
    "sentence_openers",
    "connective_tokens",
    "sentence_endings",
    "forbidden_fillers",
}

SCALAR_FIELDS = {
    "name",
    "novel_id",
    "source_path",
    "timeline_stage",
    "core_identity",
    "gender",
    "age_stage",
    "faction_position",
    "story_role",
    "stance_stability",
    "identity_anchor",
    "world_rule_fit",
    "background_imprint",
    "trauma_scar",
    "world_belong",
    "rule_view",
    "plot_restriction",
    "soul_goal",
    "hidden_desire",
    "temperament_type",
    "worldview",
    "belief_anchor",
    "moral_bottom_line",
    "restraint_threshold",
    "inner_conflict",
    "self_cognition",
    "private_self",
    "thinking_style",
    "reward_logic",
    "action_style",
    "stress_response",
    "emotion_model",
    "social_mode",
    "carry_style",
    "others_impression",
    "appearance_feature",
    "habit_action",
    "interest_claim",
    "resource_dependence",
    "trade_principle",
    "disguise_switch",
    "ooc_redline",
    "speech_style",
    "cadence",
    "arc_type",
    "arc_blocker",
    "arc_summary",
    "group_chat_policy",
    "silence_policy",
    "correction_policy",
    "canon_memory",
    "relationship_updates",
    "user_edits",
    "notable_interactions",
    "evidence_source",
    "contradiction_note",
    "anger_style",
    "joy_style",
    "grievance_style",
}

INT_FIELDS = {
    "arc_confidence",
    "description_count",
    "dialogue_count",
    "thought_count",
    "chunk_count",
}

MAP_FIELDS = {"values", "arc_start", "arc_mid", "arc_end"}


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def safe_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", str(name or "").strip())
    return cleaned or "unnamed"


def split_scalar_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    parts = re.split(r"\s*[；;]\s*", text)
    return [part.strip() for part in parts if part.strip()]


def parse_metric_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key).strip(): item for key, item in value.items() if str(key).strip()}
    text = str(value or "").strip()
    if not text:
        return {}
    parsed: dict[str, Any] = {}
    for part in re.split(r"\s*[；;]\s*", text):
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        key_text = key.strip()
        value_text = raw_value.strip()
        if not key_text:
            continue
        try:
            parsed[key_text] = int(value_text)
        except ValueError:
            parsed[key_text] = value_text
    return parsed


def join_items(items: Iterable[Any]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return "；".join(cleaned)


def join_metric_map(items: Dict[str, Any]) -> str:
    if not isinstance(items, dict):
        return ""
    ordered = [f"{key}={value}" for key, value in items.items() if str(key).strip()]
    return "；".join(ordered)


def render_metric_map_or_insufficient(items: Dict[str, Any]) -> str:
    rendered = join_metric_map(items)
    return rendered or "证据不足"


def _parse_markdown_kv(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        key_text = key.strip()
        value_text = value.strip()
        if not key_text:
            continue
        if key_text in parsed and parsed[key_text] and value_text:
            parsed[key_text] = f"{parsed[key_text]}；{value_text}"
        else:
            parsed[key_text] = value_text
    return parsed


def normalize_profile(profile: Dict[str, Any], *, source_hint: Path | None = None) -> dict[str, Any]:
    data = dict(profile or {})
    normalized: dict[str, Any] = {}

    for field in SCALAR_FIELDS:
        if field in data:
            normalized[field] = str(data.get(field, "")).strip()

    for field in LIST_FIELDS:
        if field in data:
            normalized[field] = split_scalar_list(data.get(field))

    for field in MAP_FIELDS:
        if field in data:
            normalized[field] = parse_metric_map(data.get(field))

    for field in INT_FIELDS:
        raw_value = data.get(field, 0)
        try:
            normalized[field] = int(raw_value)
        except (TypeError, ValueError):
            normalized[field] = 0

    speech_habits = data.get("speech_habits", {})
    if not isinstance(speech_habits, dict):
        speech_habits = {}
    normalized["speech_habits"] = {
        "cadence": str(speech_habits.get("cadence", normalized.get("cadence", ""))).strip(),
        "signature_phrases": split_scalar_list(speech_habits.get("signature_phrases", data.get("signature_phrases", []))),
        "sentence_openers": split_scalar_list(speech_habits.get("sentence_openers", data.get("sentence_openers", []))),
        "connective_tokens": split_scalar_list(speech_habits.get("connective_tokens", data.get("connective_tokens", []))),
        "sentence_endings": split_scalar_list(speech_habits.get("sentence_endings", data.get("sentence_endings", []))),
        "forbidden_fillers": split_scalar_list(speech_habits.get("forbidden_fillers", data.get("forbidden_fillers", []))),
    }

    emotion_profile = data.get("emotion_profile", {})
    if not isinstance(emotion_profile, dict):
        emotion_profile = {}
    normalized["emotion_profile"] = {
        "anger_style": str(emotion_profile.get("anger_style", data.get("anger_style", ""))).strip(),
        "joy_style": str(emotion_profile.get("joy_style", data.get("joy_style", ""))).strip(),
        "grievance_style": str(emotion_profile.get("grievance_style", data.get("grievance_style", ""))).strip(),
    }

    arc = data.get("arc", {})
    if not isinstance(arc, dict):
        arc = {}
    normalized["arc"] = {
        "start": parse_metric_map(arc.get("start", data.get("arc_start", {}))),
        "mid": parse_metric_map(arc.get("mid", data.get("arc_mid", {}))),
        "end": parse_metric_map(arc.get("end", data.get("arc_end", {}))),
    }

    evidence = data.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    normalized["evidence"] = {
        "description_count": _coerce_int(evidence.get("description_count", data.get("description_count", 0))),
        "dialogue_count": _coerce_int(evidence.get("dialogue_count", data.get("dialogue_count", 0))),
        "thought_count": _coerce_int(evidence.get("thought_count", data.get("thought_count", 0))),
        "chunk_count": _coerce_int(evidence.get("chunk_count", data.get("chunk_count", 0))),
    }

    if source_hint is not None:
        if not normalized.get("name"):
            normalized["name"] = source_hint.parent.name if source_hint.name.startswith("PROFILE") else source_hint.stem
        if not normalized.get("novel_id") and len(source_hint.parts) >= 2:
            normalized["novel_id"] = source_hint.parent.parent.name if source_hint.name.startswith("PROFILE") else ""
        if not normalized.get("source_path"):
            normalized["source_path"] = ""

    normalized.setdefault("name", "unnamed")
    normalized.setdefault("novel_id", "")
    normalized.setdefault("source_path", "")
    for field in SCALAR_FIELDS:
        normalized.setdefault(field, "")
    for field in LIST_FIELDS:
        normalized.setdefault(field, [])
    normalized.setdefault("values", {})
    normalized.setdefault("speech_habits", {"cadence": "", "signature_phrases": [], "sentence_openers": [], "connective_tokens": [], "sentence_endings": [], "forbidden_fillers": []})
    normalized.setdefault("emotion_profile", {"anger_style": "", "joy_style": "", "grievance_style": ""})
    normalized.setdefault("arc", {"start": {}, "mid": {}, "end": {}})
    normalized.setdefault("evidence", {"description_count": 0, "dialogue_count": 0, "thought_count": 0, "chunk_count": 0})
    normalized["arc_confidence"] = _coerce_int(data.get("arc_confidence", normalized.get("arc_confidence", 0)))
    return normalized


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_profile_source(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("profile"), dict):
            payload = payload["profile"]
        if not isinstance(payload, dict):
            raise ValueError("JSON profile source must be an object")
        return normalize_profile(payload, source_hint=source)
    return parse_profile_markdown(source.read_text(encoding="utf-8"), source_hint=source)


def parse_profile_markdown(text: str, *, source_hint: Path | None = None) -> dict[str, Any]:
    raw = _parse_markdown_kv(text)
    return normalize_profile(raw, source_hint=source_hint)


def load_existing_persona_bundle(persona_dir: str | Path) -> dict[str, Any]:
    root = Path(persona_dir)
    if not root.exists():
        raise FileNotFoundError(f"persona directory does not exist: {root}")

    merged: dict[str, Any] = {}
    ordered_files = [
        root / "PROFILE.generated.md",
        root / "PROFILE.md",
    ]
    for base_name in DEFAULT_NAV_LOAD_ORDER:
        ordered_files.extend(
            [
                root / f"{base_name}.generated.md",
                root / f"{base_name}.md",
            ]
        )

    loaded_any = False
    for path in ordered_files:
        if not path.exists() or not path.is_file():
            continue
        loaded_any = True
        current = parse_profile_markdown(path.read_text(encoding="utf-8"), source_hint=path)
        merged = _merge_normalized_profiles(merged, current)

    if not loaded_any:
        raise FileNotFoundError(f"no persona markdown files found under {root}")
    return normalize_profile(merged, source_hint=root / "PROFILE.generated.md")


def materialize_persona_bundle(
    persona_dir: str | Path,
    profile: Dict[str, Any],
    *,
    default_nav_load_order: Iterable[str] = DEFAULT_NAV_LOAD_ORDER,
    persona_file_catalog: Dict[str, Dict[str, Any]] = PERSONA_FILE_CATALOG,
) -> Path:
    target_dir = ensure_dir(persona_dir)
    profile = normalize_profile(profile)

    profile_content = render_profile_md(profile)
    (target_dir / "PROFILE.generated.md").write_text(profile_content, encoding="utf-8")
    editable_profile = target_dir / "PROFILE.md"
    if not editable_profile.exists():
        editable_profile.write_text(profile_content, encoding="utf-8")

    bundle = {
        "SOUL": render_soul_md(profile),
        "IDENTITY": render_identity_md(profile),
        "BACKGROUND": render_background_md(profile),
        "CAPABILITY": render_capability_md(profile),
        "BONDS": render_bonds_md(profile),
        "CONFLICTS": render_conflicts_md(profile),
        "ROLE": render_role_md(profile),
        "AGENTS": render_agents_md(profile),
        "MEMORY": render_memory_md(profile),
    }
    if should_create_goals_md(profile):
        bundle["GOALS"] = render_goals_md(profile)
    if should_create_style_md(profile):
        bundle["STYLE"] = render_style_md(profile)
    if should_create_trauma_md(profile):
        bundle["TRAUMA"] = render_trauma_md(profile)

    for base_name, content in bundle.items():
        generated = target_dir / f"{base_name}.generated.md"
        generated.write_text(content, encoding="utf-8")
        editable = target_dir / f"{base_name}.md"
        if not editable.exists():
            editable.write_text(content, encoding="utf-8")

    refresh_persona_navigation(
        target_dir,
        str(profile.get("name", "")),
        default_nav_load_order=default_nav_load_order,
        persona_file_catalog=persona_file_catalog,
    )
    status = build_persona_completion_status(
        target_dir,
        name=str(profile.get("name", "")),
        novel_id=str(profile.get("novel_id", "")),
    )
    write_json(target_dir / "ARTIFACT_STATUS.generated.json", status)
    return target_dir


def _merge_normalized_profiles(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    if not base:
        return dict(incoming)

    merged = dict(base)
    for key in SCALAR_FIELDS:
        value = str(incoming.get(key, "")).strip()
        if value:
            merged[key] = value
    for key in LIST_FIELDS:
        values = split_scalar_list(incoming.get(key, []))
        if not values:
            continue
        existing = split_scalar_list(merged.get(key, []))
        merged[key] = _merge_unique(existing, values)
    for key in MAP_FIELDS:
        values = parse_metric_map(incoming.get(key, {}))
        if values:
            merged[key] = {**parse_metric_map(merged.get(key, {})), **values}

    incoming_speech = incoming.get("speech_habits", {}) if isinstance(incoming.get("speech_habits", {}), dict) else {}
    merged_speech = merged.get("speech_habits", {}) if isinstance(merged.get("speech_habits", {}), dict) else {}
    if incoming_speech:
        merged["speech_habits"] = {
            "cadence": str(incoming_speech.get("cadence", merged_speech.get("cadence", ""))).strip(),
            "signature_phrases": _merge_unique(
                split_scalar_list(merged_speech.get("signature_phrases", [])),
                split_scalar_list(incoming_speech.get("signature_phrases", [])),
            ),
            "sentence_openers": _merge_unique(
                split_scalar_list(merged_speech.get("sentence_openers", [])),
                split_scalar_list(incoming_speech.get("sentence_openers", [])),
            ),
            "connective_tokens": _merge_unique(
                split_scalar_list(merged_speech.get("connective_tokens", [])),
                split_scalar_list(incoming_speech.get("connective_tokens", [])),
            ),
            "sentence_endings": _merge_unique(
                split_scalar_list(merged_speech.get("sentence_endings", [])),
                split_scalar_list(incoming_speech.get("sentence_endings", [])),
            ),
            "forbidden_fillers": _merge_unique(
                split_scalar_list(merged_speech.get("forbidden_fillers", [])),
                split_scalar_list(incoming_speech.get("forbidden_fillers", [])),
            ),
        }

    incoming_emotion = incoming.get("emotion_profile", {}) if isinstance(incoming.get("emotion_profile", {}), dict) else {}
    merged_emotion = merged.get("emotion_profile", {}) if isinstance(merged.get("emotion_profile", {}), dict) else {}
    if incoming_emotion:
        merged["emotion_profile"] = {
            "anger_style": str(incoming_emotion.get("anger_style", merged_emotion.get("anger_style", ""))).strip(),
            "joy_style": str(incoming_emotion.get("joy_style", merged_emotion.get("joy_style", ""))).strip(),
            "grievance_style": str(incoming_emotion.get("grievance_style", merged_emotion.get("grievance_style", ""))).strip(),
        }

    incoming_arc = incoming.get("arc", {}) if isinstance(incoming.get("arc", {}), dict) else {}
    merged_arc = merged.get("arc", {}) if isinstance(merged.get("arc", {}), dict) else {}
    if incoming_arc:
        merged["arc"] = {
            "start": {**parse_metric_map(merged_arc.get("start", {})), **parse_metric_map(incoming_arc.get("start", {}))},
            "mid": {**parse_metric_map(merged_arc.get("mid", {})), **parse_metric_map(incoming_arc.get("mid", {}))},
            "end": {**parse_metric_map(merged_arc.get("end", {})), **parse_metric_map(incoming_arc.get("end", {}))},
        }

    incoming_evidence = incoming.get("evidence", {}) if isinstance(incoming.get("evidence", {}), dict) else {}
    merged_evidence = merged.get("evidence", {}) if isinstance(merged.get("evidence", {}), dict) else {}
    if incoming_evidence:
        merged["evidence"] = {
            "description_count": max(_coerce_int(merged_evidence.get("description_count", 0)), _coerce_int(incoming_evidence.get("description_count", 0))),
            "dialogue_count": max(_coerce_int(merged_evidence.get("dialogue_count", 0)), _coerce_int(incoming_evidence.get("dialogue_count", 0))),
            "thought_count": max(_coerce_int(merged_evidence.get("thought_count", 0)), _coerce_int(incoming_evidence.get("thought_count", 0))),
            "chunk_count": max(_coerce_int(merged_evidence.get("chunk_count", 0)), _coerce_int(incoming_evidence.get("chunk_count", 0))),
        }
    merged["arc_confidence"] = max(_coerce_int(merged.get("arc_confidence", 0)), _coerce_int(incoming.get("arc_confidence", 0)))
    return merged


def _merge_unique(base: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    seen = set()
    for item in [*base, *incoming]:
        text = str(item).strip()
        if not text or text in seen:
            continue
        merged.append(text)
        seen.add(text)
    return merged


def refresh_persona_navigation(
    persona_dir: Path,
    character_name: str,
    *,
    default_nav_load_order: Iterable[str],
    persona_file_catalog: Dict[str, Dict[str, Any]],
) -> None:
    generated = persona_dir / "NAVIGATION.generated.md"
    generated.write_text(
        render_navigation_generated_md(
            persona_dir,
            character_name,
            default_nav_load_order=default_nav_load_order,
            persona_file_catalog=persona_file_catalog,
        ),
        encoding="utf-8",
    )
    editable = persona_dir / "NAVIGATION.md"
    if not editable.exists():
        editable.write_text(render_navigation_override_md(), encoding="utf-8")


def render_navigation_generated_md(
    persona_dir: Path,
    character_name: str,
    *,
    default_nav_load_order: Iterable[str],
    persona_file_catalog: Dict[str, Dict[str, Any]],
) -> str:
    load_order = list(default_nav_load_order)
    active_order = [base_name for base_name in load_order if persona_file_is_active(persona_dir, base_name, persona_file_catalog)]
    if not active_order:
        active_order = ["SOUL", "IDENTITY", "AGENTS", "MEMORY"]

    lines = [
        "# NAVIGATION",
        "<!-- Runtime entrypoint. Read this file first, then follow load_order. -->",
        "",
        "## Runtime",
        f"- character: {character_name}",
        f"- load_order: {' -> '.join(active_order)}",
        "- first_read: NAVIGATION.generated.md -> NAVIGATION.md overrides",
        "- write_back: MEMORY handles durable user guidance and corrections; RELATIONS handles target-specific manual edits",
        "",
    ]
    for base_name in load_order:
        meta = persona_file_catalog.get(base_name, {})
        lines.extend(
            [
                f"## {base_name}",
                f"- status: {'active' if persona_file_is_active(persona_dir, base_name, persona_file_catalog) else 'inactive'}",
                f"- optional: {'yes' if meta.get('optional', True) else 'no'}",
                f"- file: {base_name}.md",
                f"- fallback: {base_name}.generated.md",
                f"- present: {'yes' if persona_file_exists(persona_dir, base_name) else 'no'}",
                f"- role: {meta.get('role', '')}",
                f"- behaviors: {meta.get('behaviors', '')}",
                f"- write_policy: {meta.get('write_policy', 'manual_edit')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_navigation_override_md() -> str:
    return (
        "# NAVIGATION\n"
        "<!-- Optional overrides for the generated navigation map.\n"
        "Use the same key format as NAVIGATION.generated.md.\n"
        "-->\n"
    )


def persona_file_exists(persona_dir: Path, base_name: str) -> bool:
    return (persona_dir / f"{base_name}.md").exists() or (persona_dir / f"{base_name}.generated.md").exists()


def persona_file_is_active(
    persona_dir: Path,
    base_name: str,
    persona_file_catalog: Dict[str, Dict[str, Any]],
) -> bool:
    if not persona_file_catalog.get(base_name, {}).get("optional", True):
        return True
    return persona_file_exists(persona_dir, base_name)


def render_profile_md(profile: Dict[str, Any]) -> str:
    speech_habits = profile.get("speech_habits", {}) if isinstance(profile.get("speech_habits", {}), dict) else {}
    emotion = profile.get("emotion_profile", {}) if isinstance(profile.get("emotion_profile", {}), dict) else {}
    arc = profile.get("arc", {}) if isinstance(profile.get("arc", {}), dict) else {}
    evidence = profile.get("evidence", {}) if isinstance(profile.get("evidence", {}), dict) else {}
    return (
        "# PROFILE\n"
        "<!-- Canonical markdown profile storage. Runtime loads this file before persona overlays. -->\n\n"
        "## Meta\n"
        f"- name: {profile.get('name', '')}\n"
        f"- novel_id: {profile.get('novel_id', '')}\n"
        f"- source_path: {profile.get('source_path', '')}\n\n"
        "## Basic Positioning\n"
        f"- timeline_stage: {profile.get('timeline_stage', '')}\n"
        f"- role_tags: {join_items(profile.get('role_tags', []))}\n"
        f"- core_identity: {profile.get('core_identity', '')}\n"
        f"- gender: {profile.get('gender', '')}\n"
        f"- age_stage: {profile.get('age_stage', '')}\n"
        f"- faction_position: {profile.get('faction_position', '')}\n"
        f"- story_role: {profile.get('story_role', '')}\n"
        f"- stance_stability: {profile.get('stance_stability', '')}\n"
        f"- identity_anchor: {profile.get('identity_anchor', '')}\n"
        f"- world_rule_fit: {profile.get('world_rule_fit', '')}\n\n"
        "## Root Layer\n"
        f"- background_imprint: {profile.get('background_imprint', '')}\n"
        f"- life_experience: {join_items(profile.get('life_experience', []))}\n"
        f"- trauma_scar: {profile.get('trauma_scar', '')}\n"
        f"- taboo_topics: {join_items(profile.get('taboo_topics', []))}\n"
        f"- forbidden_behaviors: {join_items(profile.get('forbidden_behaviors', []))}\n\n"
        "## World Binding\n"
        f"- world_belong: {profile.get('world_belong', '')}\n"
        f"- rule_view: {profile.get('rule_view', '')}\n"
        f"- plot_restriction: {profile.get('plot_restriction', '')}\n\n"
        "## Inner Core\n"
        f"- soul_goal: {profile.get('soul_goal', '')}\n"
        f"- hidden_desire: {profile.get('hidden_desire', '')}\n"
        f"- core_traits: {join_items(profile.get('core_traits', []))}\n"
        f"- temperament_type: {profile.get('temperament_type', '')}\n"
        f"- values: {render_metric_map_or_insufficient(profile.get('values', {}))}\n"
        f"- worldview: {profile.get('worldview', '')}\n"
        f"- belief_anchor: {profile.get('belief_anchor', '')}\n"
        f"- moral_bottom_line: {profile.get('moral_bottom_line', '')}\n"
        f"- restraint_threshold: {profile.get('restraint_threshold', '')}\n\n"
        "## Value And Conflict\n"
        f"- inner_conflict: {profile.get('inner_conflict', '')}\n"
        f"- self_cognition: {profile.get('self_cognition', '')}\n"
        f"- private_self: {profile.get('private_self', '')}\n"
        f"- thinking_style: {profile.get('thinking_style', '')}\n"
        f"- cognitive_limits: {join_items(profile.get('cognitive_limits', []))}\n\n"
        "## Decision Logic\n"
        f"- decision_rules: {join_items(profile.get('decision_rules', []))}\n"
        f"- reward_logic: {profile.get('reward_logic', '')}\n"
        f"- action_style: {profile.get('action_style', '')}\n\n"
        "## Emotion And Stress\n"
        f"- fear_triggers: {join_items(profile.get('fear_triggers', []))}\n"
        f"- stress_response: {profile.get('stress_response', '')}\n"
        f"- emotion_model: {profile.get('emotion_model', '')}\n"
        f"- anger_style: {emotion.get('anger_style', '')}\n"
        f"- joy_style: {emotion.get('joy_style', '')}\n"
        f"- grievance_style: {emotion.get('grievance_style', '')}\n\n"
        "## Social Pattern\n"
        f"- social_mode: {profile.get('social_mode', '')}\n"
        f"- carry_style: {profile.get('carry_style', '')}\n"
        f"- others_impression: {profile.get('others_impression', '')}\n"
        f"- key_bonds: {join_items(profile.get('key_bonds', []))}\n\n"
        "## External Detail\n"
        f"- appearance_feature: {profile.get('appearance_feature', '')}\n"
        f"- habit_action: {profile.get('habit_action', '')}\n"
        f"- preference_like: {join_items(profile.get('preference_like', []))}\n"
        f"- dislike_hate: {join_items(profile.get('dislike_hate', []))}\n\n"
        "## Resource Logic\n"
        f"- interest_claim: {profile.get('interest_claim', '')}\n"
        f"- resource_dependence: {profile.get('resource_dependence', '')}\n"
        f"- trade_principle: {profile.get('trade_principle', '')}\n"
        f"- disguise_switch: {profile.get('disguise_switch', '')}\n"
        f"- ooc_redline: {profile.get('ooc_redline', '')}\n\n"
        "## Voice\n"
        f"- speech_style: {profile.get('speech_style', '')}\n"
        f"- typical_lines: {join_items(profile.get('typical_lines', []))}\n"
        f"- cadence: {speech_habits.get('cadence', '')}\n"
        f"- signature_phrases: {join_items(speech_habits.get('signature_phrases', []))}\n"
        f"- sentence_openers: {join_items(speech_habits.get('sentence_openers', []))}\n"
        f"- connective_tokens: {join_items(speech_habits.get('connective_tokens', []))}\n"
        f"- sentence_endings: {join_items(speech_habits.get('sentence_endings', []))}\n"
        f"- forbidden_fillers: {join_items(speech_habits.get('forbidden_fillers', []))}\n\n"
        "## Capability\n"
        f"- strengths: {join_items(profile.get('strengths', []))}\n"
        f"- weaknesses: {join_items(profile.get('weaknesses', []))}\n\n"
        "## Arc\n"
        f"- arc_start: {render_metric_map_or_insufficient(arc.get('start', {}))}\n"
        f"- arc_mid: {render_metric_map_or_insufficient(arc.get('mid', {}))}\n"
        f"- arc_end: {render_metric_map_or_insufficient(arc.get('end', {}))}\n"
        f"- arc_type: {profile.get('arc_type', '')}\n"
        f"- arc_blocker: {profile.get('arc_blocker', '')}\n"
        f"- arc_summary: {profile.get('arc_summary', '')}\n"
        f"- arc_confidence: {profile.get('arc_confidence', 0)}\n\n"
        "## Evidence\n"
        f"- description_count: {evidence.get('description_count', 0)}\n"
        f"- dialogue_count: {evidence.get('dialogue_count', 0)}\n"
        f"- thought_count: {evidence.get('thought_count', 0)}\n"
        f"- chunk_count: {evidence.get('chunk_count', 0)}\n"
        f"- evidence_source: {profile.get('evidence_source', '')}\n"
        f"- contradiction_note: {profile.get('contradiction_note', '')}\n"
    )


def render_soul_md(profile: Dict[str, Any]) -> str:
    return (
        "# SOUL\n\n"
        "## Core\n"
        f"- identity_anchor: {profile.get('identity_anchor', '')}\n"
        f"- soul_goal: {profile.get('soul_goal', '')}\n"
        f"- temperament_type: {profile.get('temperament_type', '')}\n"
        f"- worldview: {profile.get('worldview', '')}\n"
        f"- belief_anchor: {profile.get('belief_anchor', '')}\n"
        f"- moral_bottom_line: {profile.get('moral_bottom_line', '')}\n"
        f"- restraint_threshold: {profile.get('restraint_threshold', '')}\n"
        f"- thinking_style: {profile.get('thinking_style', '')}\n"
        f"- taboo_topics: {join_items(profile.get('taboo_topics', []))}\n"
        f"- forbidden_behaviors: {join_items(profile.get('forbidden_behaviors', []))}\n"
    )


def render_goals_md(profile: Dict[str, Any]) -> str:
    return (
        "# GOALS\n\n"
        "## Long Arc\n"
        f"- soul_goal: {profile.get('soul_goal', '')}\n"
        f"- decision_rules: {join_items(profile.get('decision_rules', []))}\n"
        f"- arc_end: {join_metric_map(profile.get('arc', {}).get('end', {}))}\n"
    )


def render_style_md(profile: Dict[str, Any]) -> str:
    speech_habits = profile.get("speech_habits", {}) if isinstance(profile.get("speech_habits", {}), dict) else {}
    return (
        "# STYLE\n\n"
        "## Expression\n"
        f"- speech_style: {profile.get('speech_style', '')}\n"
        f"- typical_lines: {join_items(profile.get('typical_lines', []))}\n"
        f"- cadence: {speech_habits.get('cadence', '')}\n"
        f"- signature_phrases: {join_items(speech_habits.get('signature_phrases', []))}\n"
        f"- sentence_openers: {join_items(speech_habits.get('sentence_openers', []))}\n"
        f"- connective_tokens: {join_items(speech_habits.get('connective_tokens', []))}\n"
        f"- sentence_endings: {join_items(speech_habits.get('sentence_endings', []))}\n"
        f"- forbidden_fillers: {join_items(speech_habits.get('forbidden_fillers', []))}\n"
    )


def render_trauma_md(profile: Dict[str, Any]) -> str:
    return (
        "# TRAUMA\n\n"
        "## Boundaries\n"
        f"- trauma_scar: {profile.get('trauma_scar', '')}\n"
        f"- taboo_topics: {join_items(profile.get('taboo_topics', []))}\n"
        f"- forbidden_behaviors: {join_items(profile.get('forbidden_behaviors', []))}\n"
        f"- fear_triggers: {join_items(profile.get('fear_triggers', []))}\n"
        f"- stress_response: {profile.get('stress_response', '')}\n"
        f"- grievance_style: {profile.get('emotion_profile', {}).get('grievance_style', '')}\n"
    )


def render_identity_md(profile: Dict[str, Any]) -> str:
    emotion = profile.get("emotion_profile", {}) if isinstance(profile.get("emotion_profile", {}), dict) else {}
    return (
        "# IDENTITY\n\n"
        "## Self\n"
        f"- identity_anchor: {profile.get('identity_anchor', '')}\n"
        f"- core_traits: {join_items(profile.get('core_traits', []))}\n"
        f"- temperament_type: {profile.get('temperament_type', '')}\n"
        f"- values: {join_metric_map(profile.get('values', {}))}\n"
        f"- self_cognition: {profile.get('self_cognition', '')}\n"
        f"- others_impression: {profile.get('others_impression', '')}\n"
        f"- life_experience: {join_items(profile.get('life_experience', []))}\n"
        f"- anger_style: {emotion.get('anger_style', '')}\n"
        f"- joy_style: {emotion.get('joy_style', '')}\n"
        f"- grievance_style: {emotion.get('grievance_style', '')}\n"
    )


def render_background_md(profile: Dict[str, Any]) -> str:
    return (
        "# BACKGROUND\n\n"
        "## World Position\n"
        f"- core_identity: {profile.get('core_identity', '')}\n"
        f"- faction_position: {profile.get('faction_position', '')}\n"
        f"- world_belong: {profile.get('world_belong', '')}\n"
        f"- background_imprint: {profile.get('background_imprint', '')}\n"
        f"- trauma_scar: {profile.get('trauma_scar', '')}\n"
        f"- world_rule_fit: {profile.get('world_rule_fit', '')}\n"
        f"- rule_view: {profile.get('rule_view', '')}\n"
        f"- plot_restriction: {profile.get('plot_restriction', '')}\n"
    )


def render_capability_md(profile: Dict[str, Any]) -> str:
    return (
        "# CAPABILITY\n\n"
        "## Strength And Cost\n"
        f"- strengths: {join_items(profile.get('strengths', []))}\n"
        f"- weaknesses: {join_items(profile.get('weaknesses', []))}\n"
        f"- cognitive_limits: {join_items(profile.get('cognitive_limits', []))}\n"
        f"- action_style: {profile.get('action_style', '')}\n"
    )


def render_bonds_md(profile: Dict[str, Any]) -> str:
    return (
        "# BONDS\n\n"
        "## Relationship Habit\n"
        f"- social_mode: {profile.get('social_mode', '')}\n"
        f"- carry_style: {profile.get('carry_style', '')}\n"
        f"- others_impression: {profile.get('others_impression', '')}\n"
        f"- key_bonds: {join_items(profile.get('key_bonds', []))}\n"
        f"- reward_logic: {profile.get('reward_logic', '')}\n"
        f"- belief_anchor: {profile.get('belief_anchor', '')}\n"
    )


def render_conflicts_md(profile: Dict[str, Any]) -> str:
    return (
        "# CONFLICTS\n\n"
        "## Inner Pull\n"
        f"- hidden_desire: {profile.get('hidden_desire', '')}\n"
        f"- inner_conflict: {profile.get('inner_conflict', '')}\n"
        f"- self_cognition: {profile.get('self_cognition', '')}\n"
        f"- moral_bottom_line: {profile.get('moral_bottom_line', '')}\n"
        f"- restraint_threshold: {profile.get('restraint_threshold', '')}\n"
        f"- fear_triggers: {join_items(profile.get('fear_triggers', []))}\n"
        f"- stress_response: {profile.get('stress_response', '')}\n"
        f"- private_self: {profile.get('private_self', '')}\n"
    )


def render_role_md(profile: Dict[str, Any]) -> str:
    return (
        "# ROLE\n\n"
        "## Plot Function\n"
        f"- story_role: {profile.get('story_role', '')}\n"
        f"- stance_stability: {profile.get('stance_stability', '')}\n"
        f"- world_rule_fit: {profile.get('world_rule_fit', '')}\n"
        f"- arc_end: {join_metric_map(profile.get('arc', {}).get('end', {}))}\n"
    )


def render_agents_md(profile: Dict[str, Any]) -> str:
    return (
        "# AGENTS\n\n"
        "## Runtime Rules\n"
        f"- group_chat_policy: {profile.get('group_chat_policy', '') or '群聊中优先回应被点名对象、当前冲突中心或最相关的关系目标'}\n"
        f"- silence_policy: {profile.get('silence_policy', '') or '未被点名且无强关联时允许短暂沉默，不抢答'}\n"
        f"- correction_policy: {profile.get('correction_policy', '') or '用户纠错与持续提示写入 MEMORY，并在后续对话中沿用'}\n"
        f"- decision_rules: {join_items(profile.get('decision_rules', []))}\n"
    )


def render_memory_md(profile: Dict[str, Any]) -> str:
    return (
        "# MEMORY\n\n"
        "## Stable Memory\n"
        f"- canon_memory: {profile.get('canon_memory', '') or join_items(profile.get('life_experience', []))}\n"
        f"- relationship_updates: {profile.get('relationship_updates', '')}\n"
        "\n## Mutable Notes\n"
        f"- user_edits: {profile.get('user_edits', '')}\n"
        f"- notable_interactions: {profile.get('notable_interactions', '')}\n"
    )


def should_create_goals_md(profile: Dict[str, Any]) -> bool:
    return bool(str(profile.get("soul_goal", "")).strip() or profile.get("decision_rules"))


def should_create_style_md(profile: Dict[str, Any]) -> bool:
    return bool(str(profile.get("speech_style", "")).strip() or profile.get("typical_lines"))


def should_create_trauma_md(profile: Dict[str, Any]) -> bool:
    return bool(
        str(profile.get("trauma_scar", "")).strip()
        or profile.get("taboo_topics")
        or profile.get("forbidden_behaviors")
        or profile.get("fear_triggers")
        or str(profile.get("stress_response", "")).strip()
    )
