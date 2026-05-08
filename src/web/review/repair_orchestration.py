from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from src.core.config import Config


def maybe_repair_generated_relations(
    *,
    parts: Any,
    config: Config,
    payload: dict[str, Any],
    characters: list[str],
    relations_file: Path,
    relation_markdown: str,
    load_relations_source: Callable[[Path], dict[str, Any]],
    collect_relation_repair_issues: Callable[[dict[str, Any]], list[str]],
    build_relation_repair_messages: Callable[..., list[dict[str, str]]],
    sanitize_markdown_output: Callable[[str], str],
    llm_cap: Callable[[Config, str, int], int],
    relation_repair_max_tokens: int,
) -> str | None:
    issues: list[str] = []
    try:
        relation_payload = load_relations_source(relations_file)
        parsed_relations = dict(relation_payload.get("relations", {}) or {})
        if not parsed_relations:
            issues.append(
                "当前草稿未能解析出任何关系对；请严格改写成完整的 RELATION_GRAPH Markdown，并为每对角色使用 `## 角色A_角色B` 小节。"
            )
        else:
            issues.extend(collect_relation_repair_issues(relation_payload))
    except Exception:
        issues.append(
            "当前草稿格式无法解析；请严格改写成完整的 RELATION_GRAPH Markdown，并为每对角色使用 `## 角色A_角色B` 小节。"
        )
    if not issues:
        return None
    repair_result = parts.llm.chat_completion(
        build_relation_repair_messages(
            payload,
            characters=characters,
            relation_markdown=relation_markdown,
            issues=issues,
        ),
        temperature=float(config.get("llm.temperature", 0.15) or 0.15),
        max_tokens=llm_cap(config, "llm.max_tokens", relation_repair_max_tokens),
    )
    repaired = sanitize_markdown_output(str(repair_result.get("content", "")))
    return repaired or None


def maybe_repair_generated_profile(
    *,
    parts: Any,
    config: Config,
    payload: dict[str, Any],
    character: str,
    peer_characters: list[str],
    source_path: Path,
    load_profile_source: Callable[[Path], dict[str, Any]],
    extract_dialogue_evidence: Callable[[dict[str, Any]], list[str]],
    collect_profile_repair_targets: Callable[..., dict[str, str]],
    collect_profile_completion_groups: Callable[..., list[tuple[str, tuple[str, ...], dict[str, str]]]],
    build_distill_repair_messages: Callable[..., list[dict[str, str]]],
    build_distill_completion_messages: Callable[..., list[dict[str, str]]],
    sanitize_markdown_output: Callable[[str], str],
    merge_profile_patch: Callable[[dict[str, Any], str], None],
    apply_profile_missing_fallbacks: Callable[[dict[str, Any]], None],
    render_profile_md: Callable[[dict[str, Any]], str],
    llm_cap: Callable[[Config, str, int], int],
    profile_completion_group_limit: int,
    profile_repair_max_tokens: int,
    profile_completion_max_tokens: int,
) -> str | None:
    try:
        profile = load_profile_source(source_path)
    except Exception:
        return None
    dialogue_evidence = extract_dialogue_evidence(payload, character=character)
    repair_targets = collect_profile_repair_targets(profile, dialogue_evidence=dialogue_evidence)
    updated = False
    group_tasks = collect_profile_completion_groups(profile, repair_targets=repair_targets)
    if not updated and not group_tasks:
        return None
    if group_tasks:
        for group_name, fields, group_repairs in group_tasks[:profile_completion_group_limit]:
            if group_repairs:
                completion_result = parts.llm.chat_completion(
                    build_distill_repair_messages(
                        payload,
                        character=character,
                        peer_characters=peer_characters,
                        profile=profile,
                        group_name=group_name,
                        fields=fields,
                        repair_targets=group_repairs,
                        dialogue_evidence=dialogue_evidence,
                    ),
                    temperature=float(config.get("llm.temperature", 0.15) or 0.15),
                    max_tokens=llm_cap(config, "llm.max_tokens", profile_repair_max_tokens),
                )
            else:
                completion_result = parts.llm.chat_completion(
                    build_distill_completion_messages(
                        payload,
                        character=character,
                        peer_characters=peer_characters,
                        profile=profile,
                        group_name=group_name,
                        fields=fields,
                        dialogue_evidence=dialogue_evidence,
                    ),
                    temperature=float(config.get("llm.temperature", 0.1) or 0.1),
                    max_tokens=llm_cap(config, "llm.max_tokens", profile_completion_max_tokens),
                )
            patch_text = sanitize_markdown_output(str(completion_result.get("content", ""))).strip()
            if not patch_text:
                continue
            merge_profile_patch(profile, patch_text)
            updated = True

    apply_profile_missing_fallbacks(profile)
    rendered = render_profile_md(profile).strip()
    return (rendered + "\n") if updated and rendered else (rendered if rendered else None)
