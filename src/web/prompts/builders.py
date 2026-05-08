from __future__ import annotations

from typing import Any

from src.web.prompts.fragments import build_profile_group_task_block, render_payload_section


def build_chunk_distill_guidance(
    *,
    chunk_label: str = "",
    chunk_index: int = 0,
    chunk_total: int = 0,
    chunk_mode: str = "",
) -> str:
    if not chunk_total:
        return ""
    lines = [
        "## CHUNK_MODE",
        f"- 当前是证据块 {chunk_index}/{chunk_total}：{chunk_label or '未命名证据块'}",
        "- 这是分批蒸馏中的局部草稿，请尽量完整，但允许写“证据不足”。",
        "- 不要因为当前块缺少信息，就虚构角色稳定特征。",
    ]
    if chunk_mode == "partial":
        lines.append("- 输出仍然必须是 PROFILE.generated.md 格式，但这是局部草案，后续还会汇总。")
    return "\n".join(lines).strip()


def build_relation_chunk_guidance(
    *,
    chunk_label: str = "",
    chunk_index: int = 0,
    chunk_total: int = 0,
    chunk_mode: str = "",
) -> str:
    if not chunk_total:
        return ""
    lines = [
        "## CHUNK_MODE",
        f"- 当前是关系证据块 {chunk_index}/{chunk_total}：{chunk_label or '未命名关系块'}",
        "- 这是分批关系抽取中的局部草稿，请只保留当前证据块里能站得住的关系。",
        "- 不要为了凑完整图谱而硬补没有证据的人物关系。",
    ]
    if chunk_mode == "partial":
        lines.append("- 输出仍然必须是完整 RELATION_GRAPH Markdown，但这是局部草案，后续还会汇总。")
    return "\n".join(lines).strip()


def build_distill_priority_guidance(character: str) -> str:
    lines = [
        "## PRIORITY_GUIDANCE",
        f"- 先判断 {character} 的核心身份、故事位置、立场锚点，再补深层人格。",
        "- 再判断该角色长期稳定的价值观、信念支点、情绪失控阈值，不要被单一桥段带偏。",
        "- 最后收束到说话风格、典型反应、关系落点与 OOC 边界。",
        "- 如果前期与后期明显变化，请在 timeline_stage / arc_* / contradiction_note 中体现，不要强行揉成一个静态人格。",
        "- 如果同批角色之间容易混淆，优先把差异写在 identity_anchor、soul_goal、belief_anchor、stress_response 上。",
        "",
        "### FIELD_GROUPS",
        "- 第一组：core_identity / story_role / identity_anchor / faction_position / world_belong",
        "- 第二组：soul_goal / worldview / belief_anchor / moral_bottom_line / restraint_threshold",
        "- 第三组：social_mode / stress_response / reward_logic / speech_style / typical_lines / key_bonds",
    ]
    return "\n".join(lines).strip()


def build_dialogue_style_guidance(evidence_lines: list[str]) -> str:
    lines = [
        "## DIALOGUE_STYLE",
        "- 语言风格不要只写抽象词，如“冷静克制”“温柔含蓄”。要尽量落到句子手感上。",
        "- 优先从对白里提取：口头禅、常见起句、连接词、句尾习惯、语气词、代表句。",
        "- 如果没有稳定证据，可以写证据不足；不要硬编不属于这个角色的语气词。",
        "- typical_lines 应尽量保留角色自己的说话味道，不要改写成旁白总结句。",
        "### DIALOGUE_EVIDENCE",
        *([f"- {item}" for item in evidence_lines] or ["- 证据不足"]),
    ]
    return "\n".join(lines).strip()


def build_excerpt_stage_guidance(excerpt_stages: dict[str, Any]) -> str:
    start = str(excerpt_stages.get("start", "")).strip()
    mid = str(excerpt_stages.get("mid", "")).strip()
    end = str(excerpt_stages.get("end", "")).strip()
    lines = [
        "## EVIDENCE_STAGES",
        "- 请把前段证据更多用于判断初始底色、出身烙印、早期立场。",
        "- 请把中段证据更多用于判断稳定互动模式、冲突升级、关系走向。",
        "- 请把后段证据更多用于判断弧线收束、信念变化、边界是否松动。",
        f"### START\n{start or '证据不足'}",
        f"### MID\n{mid or '证据不足'}",
        f"### END\n{end or '证据不足'}",
    ]
    return "\n".join(lines).strip()


def build_distill_llm_messages(
    payload: dict[str, Any],
    *,
    character: str,
    peers: list[str],
    excerpt_stage_guidance: str,
    dialogue_style_guidance: str,
    priority_guidance: str,
    chunk_guidance: str,
) -> list[dict[str, str]]:
    references = dict(payload.get("references", {}) or {})
    request = dict(payload.get("request", {}) or {})
    meta = dict(payload.get("meta", {}) or {})
    system_prompt = str(payload.get("prompt", "")).strip()
    focused_request = dict(request)
    focused_request.pop("excerpt_stages", None)
    user_parts = [
        f"目标角色：{character}",
        f"同批角色：{'、'.join(peers) if peers else '无'}",
        "请严格根据以下 skill payload 输出该角色唯一一份完整的 PROFILE.generated.md Markdown。",
        "不要解释，不要输出代码块，不要补充额外前后缀。",
        "如果证据不足，相关字段直接写“证据不足”。",
        priority_guidance,
        excerpt_stage_guidance,
        dialogue_style_guidance,
        chunk_guidance,
        render_payload_section("OUTPUT_SCHEMA", references.get("output_schema", "")),
        render_payload_section("STYLE_DIFFER", references.get("style_differ", "")),
        render_payload_section("LOGIC_CONSTRAINT", references.get("logic_constraint", "")),
        render_payload_section("VALIDATION_POLICY", references.get("validation_policy", "")),
        render_payload_section("REQUEST", focused_request),
        render_payload_section("META", meta),
    ]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(part for part in user_parts if part).strip()},
    ]


def build_distill_merge_messages(
    payload: dict[str, Any],
    *,
    character: str,
    peers: list[str],
    chunk_drafts: list[dict[str, str]],
    fallback_reason: str,
    excerpt_stage_guidance: str,
    dialogue_style_guidance: str,
    priority_guidance: str,
) -> list[dict[str, str]]:
    references = dict(payload.get("references", {}) or {})
    request = dict(payload.get("request", {}) or {})
    meta = dict(payload.get("meta", {}) or {})
    focused_request = dict(request)
    focused_request.pop("excerpt", None)
    focused_request.pop("excerpt_stages", None)
    drafts_text = "\n\n".join(
        f"### {item['label']}\n{item['content']}".strip()
        for item in chunk_drafts
        if str(item.get("content", "")).strip()
    ).strip()
    system_prompt = str(payload.get("prompt", "")).strip()
    user_parts = [
        f"目标角色：{character}",
        f"同批角色：{'、'.join(peers) if peers else '无'}",
        "以下是基于多个证据块得到的局部 PROFILE 草稿，请整合成唯一一份最终 PROFILE.generated.md。",
        "去重、纠偏、补足稳定特征；不要保留桥段碎句、剧情转述或互相打架的字段。",
        "说话风格优先保留重复出现的口头禅、语气词、起句、句尾和代表句味道。",
        "不要解释，不要输出代码块，不要补充额外前后缀。",
        f"补充分批原因参考：{fallback_reason}" if fallback_reason else "",
        priority_guidance,
        excerpt_stage_guidance,
        dialogue_style_guidance,
        render_payload_section("OUTPUT_SCHEMA", references.get("output_schema", "")),
        render_payload_section("STYLE_DIFFER", references.get("style_differ", "")),
        render_payload_section("LOGIC_CONSTRAINT", references.get("logic_constraint", "")),
        render_payload_section("VALIDATION_POLICY", references.get("validation_policy", "")),
        render_payload_section("REQUEST", focused_request),
        render_payload_section("CHUNK_DRAFTS", drafts_text or "证据不足"),
        render_payload_section("META", meta),
    ]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(part for part in user_parts if part).strip()},
    ]


def build_distill_repair_messages(
    base_messages: list[dict[str, str]],
    *,
    payload: dict[str, Any],
    profile_markdown: str,
    group_name: str,
    fields: tuple[str, ...],
    repair_targets: dict[str, str],
    dialogue_evidence: list[str],
) -> list[dict[str, str]]:
    instruction = build_profile_group_task_block(
        task_kind="repair",
        group_name=group_name,
        fields=fields,
        repair_targets=repair_targets,
        dialogue_evidence=dialogue_evidence,
        draft_markdown=profile_markdown,
        distill_prompt=str(payload.get("prompt", "")),
        output_schema=str(dict(payload.get("references", {}) or {}).get("output_schema", "")),
    )
    return [
        base_messages[0],
        {"role": "user", "content": f"{base_messages[1]['content']}\n\n{instruction}"},
    ]


def build_distill_completion_messages(
    base_messages: list[dict[str, str]],
    *,
    payload: dict[str, Any],
    profile_markdown: str,
    group_name: str,
    fields: tuple[str, ...],
    dialogue_evidence: list[str],
) -> list[dict[str, str]]:
    instruction = build_profile_group_task_block(
        task_kind="completion",
        group_name=group_name,
        fields=fields,
        repair_targets={},
        dialogue_evidence=dialogue_evidence,
        draft_markdown=profile_markdown,
        distill_prompt=str(payload.get("prompt", "")),
        output_schema=str(dict(payload.get("references", {}) or {}).get("output_schema", "")),
    )
    return [
        base_messages[0],
        {"role": "user", "content": f"{base_messages[1]['content']}\n\n{instruction}"},
    ]


def build_relation_llm_messages(
    payload: dict[str, Any],
    *,
    characters: list[str],
    chunk_guidance: str,
) -> list[dict[str, str]]:
    references = dict(payload.get("references", {}) or {})
    request = dict(payload.get("request", {}) or {})
    meta = dict(payload.get("meta", {}) or {})
    relation_request = dict(request)
    relation_request["characters"] = list(characters)
    system_prompt = str(payload.get("prompt", "")).strip()
    user_parts = [
        "请严格输出一份完整的关系图谱 Markdown。",
        "不要解释，不要输出代码块，不要补充额外前后缀。",
        "只保留当前书段内有明确证据支撑的人物关系。",
        chunk_guidance,
        render_payload_section("OUTPUT_SCHEMA", references.get("output_schema", "")),
        render_payload_section("LOGIC_CONSTRAINT", references.get("logic_constraint", "")),
        render_payload_section("VALIDATION_POLICY", references.get("validation_policy", "")),
        render_payload_section("REQUEST", relation_request),
        render_payload_section("META", meta),
    ]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(part for part in user_parts if part).strip()},
    ]


def build_relation_merge_messages(
    payload: dict[str, Any],
    *,
    characters: list[str],
    chunk_drafts: list[dict[str, str]],
    fallback_reason: str,
) -> list[dict[str, str]]:
    references = dict(payload.get("references", {}) or {})
    request = dict(payload.get("request", {}) or {})
    meta = dict(payload.get("meta", {}) or {})
    relation_request = dict(request)
    relation_request["characters"] = list(characters)
    relation_request.pop("excerpt", None)
    relation_request.pop("excerpt_stages", None)
    drafts_text = "\n\n".join(
        f"### {item['label']}\n{item['content']}".strip()
        for item in chunk_drafts
        if str(item.get("content", "")).strip()
    ).strip()
    system_prompt = str(payload.get("prompt", "")).strip()
    user_parts = [
        "以下是基于多个证据块得到的局部关系图谱草稿，请整合成唯一一份最终 RELATION_GRAPH Markdown。",
        "去重、纠偏、补足稳定关系；不要保留剧情转述碎句。",
        "若某关系只在单一块中短暂出现且证据弱，可以不保留。",
        "不要解释，不要输出代码块，不要补充额外前后缀。",
        f"补充分批原因参考：{fallback_reason}" if fallback_reason else "",
        render_payload_section("OUTPUT_SCHEMA", references.get("output_schema", "")),
        render_payload_section("LOGIC_CONSTRAINT", references.get("logic_constraint", "")),
        render_payload_section("VALIDATION_POLICY", references.get("validation_policy", "")),
        render_payload_section("REQUEST", relation_request),
        render_payload_section("CHUNK_DRAFTS", drafts_text or "证据不足"),
        render_payload_section("META", meta),
    ]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(part for part in user_parts if part).strip()},
    ]
