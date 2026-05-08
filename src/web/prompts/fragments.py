from __future__ import annotations

from typing import Any


def render_payload_section(title: str, value: Any) -> str:
    if isinstance(value, str):
        body = value.strip()
    else:
        import json

        body = json.dumps(value, ensure_ascii=False, indent=2)
    return f"## {title}\n{body}".strip()


def extract_markdown_section(markdown: str, heading: str) -> str:
    lines = str(markdown or "").splitlines()
    target = str(heading or "").strip()
    if not target:
        return ""
    start = -1
    level = 0
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        marker, _, title = line.partition(" ")
        if title.strip() == target:
            start = index
            level = len(marker)
            break
    if start < 0:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index].strip()
        if not line.startswith("#"):
            continue
        marker, _, _ = line.partition(" ")
        if len(marker) <= level:
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def build_profile_group_task_block(
    *,
    task_kind: str,
    group_name: str,
    fields: tuple[str, ...],
    repair_targets: dict[str, str] | None,
    dialogue_evidence: list[str] | None,
    draft_markdown: str,
    distill_prompt: str,
    output_schema: str,
) -> str:
    task_title = "REPAIR_TASK" if task_kind == "repair" else "COMPLETION_TASK"
    task_line = (
        f"请只修补这一组字段：{group_name}"
        if task_kind == "repair"
        else f"请只补齐这一组字段：{group_name}"
    )
    strictness_line = (
        "如果这一组里还有空字段，也一并补齐；只有正文确实没有稳定证据时才写“证据不足”。"
        if task_kind == "repair"
        else "如果正文没有稳定证据，不要留空，直接写“证据不足”。"
    )
    instruction_lines = [
        f"## {task_title}",
        task_line,
        "请沿用 skill 主提示与 schema 的字段定义、差分规则、原作优先原则和输出风格。",
        "你只处理下面列出的字段，不要自由重写整份 PROFILE。",
        strictness_line,
        "输出必须只包含这些字段的 Markdown 行，每个字段一行，格式严格为 `- field: value`。",
        "不要输出标题，不要输出代码块，不要解释，不要附加其他字段。",
        "请把剧情碎句、对白残句、未收束结论改写成稳定、可演绎的人格概括。",
        "如果问题落在说话风格，请优先从对白里收束语气、口头禅、起句、收尾和句子节奏。",
        "",
        "### TARGET_FIELDS",
        *[f"- {field}" for field in fields],
    ]
    if repair_targets:
        instruction_lines.extend(
            [
                "",
                "### FIELD_ISSUES",
                *[f"- {field}: {issue}" for field, issue in repair_targets.items()],
            ]
        )
    instruction_lines.extend(
        [
            "",
            "### DIALOGUE_EVIDENCE",
            *([f"- {item}" for item in list(dialogue_evidence or [])] or ["- 证据不足"]),
            "",
            render_payload_section("DISTILL_PROMPT_RULES", extract_markdown_section(distill_prompt, "规则")),
            render_payload_section("DISTILL_PROMPT_DIFF", extract_markdown_section(distill_prompt, "多角色蒸馏差分要求")),
            render_payload_section("OUTPUT_SCHEMA_GROUPS", extract_markdown_section(output_schema, "推荐字段分组")),
            render_payload_section("OUTPUT_SCHEMA_FIELD_GUARDS", extract_markdown_section(output_schema, "易混字段收紧定义")),
            render_payload_section("OUTPUT_SCHEMA_ORIGINALITY", extract_markdown_section(output_schema, "原作优先原则")),
            "",
            "### CURRENT_DRAFT",
            draft_markdown.strip(),
        ]
    )
    return "\n".join(part for part in instruction_lines if part is not None).strip()
