#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

from src.utils.file_utils import ensure_dir, safe_filename


def export_persona_bundle(
    out_dir: Path,
    profile: Dict[str, Any],
    *,
    default_nav_load_order: Iterable[str],
    persona_file_catalog: Dict[str, Dict[str, Any]],
) -> None:
    char_dir = ensure_dir(out_dir / safe_filename(profile.get("name", "unnamed")))
    profile_content = render_profile_md(profile)
    (char_dir / "PROFILE.generated.md").write_text(profile_content, encoding="utf-8")
    editable_profile = char_dir / "PROFILE.md"
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
        generated = char_dir / f"{base_name}.generated.md"
        generated.write_text(content, encoding="utf-8")
        editable = char_dir / f"{base_name}.md"
        if not editable.exists():
            editable.write_text(content, encoding="utf-8")

    refresh_persona_navigation(
        char_dir,
        str(profile.get("name", "")),
        default_nav_load_order=default_nav_load_order,
        persona_file_catalog=persona_file_catalog,
    )


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
        f"- values: {join_metric_map(profile.get('values', {}))}\n"
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
        f"- arc_start: {join_metric_map(arc.get('start', {}))}\n"
        f"- arc_mid: {join_metric_map(arc.get('mid', {}))}\n"
        f"- arc_end: {join_metric_map(arc.get('end', {}))}\n"
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
        f"- background_imprint: {profile.get('background_imprint', '')}\n"
        f"- trauma_scar: {profile.get('trauma_scar', '')}\n"
        f"- world_rule_fit: {profile.get('world_rule_fit', '')}\n"
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
        "- group_chat_policy: 群聊中优先回应明确点名、关系最紧密或当前冲突最相关的对象\n"
        "- silence_policy: 未被点名且无强关联时可保持一拍沉默，不抢答\n"
        "- correction_policy: 用户纠正与持续提示要写入 MEMORY，并在后续对话沿用\n"
        f"- decision_rules: {join_items(profile.get('decision_rules', []))}\n"
    )


def render_memory_md(profile: Dict[str, Any]) -> str:
    return (
        "# MEMORY\n\n"
        "## Stable Memory\n"
        f"- canon_memory: {join_items(profile.get('life_experience', []))}\n"
        f"- relationship_updates: \n"
        "\n## Mutable Notes\n"
        "- user_edits: \n"
        "- notable_interactions: \n"
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
        or str(profile.get("stress_response", "")).strip()
    )


def join_items(items: Iterable[Any]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return "；".join(cleaned)


def join_metric_map(items: Dict[str, Any]) -> str:
    if not isinstance(items, dict):
        return ""
    ordered = [f"{key}={value}" for key, value in items.items() if str(key).strip()]
    return "；".join(ordered)
