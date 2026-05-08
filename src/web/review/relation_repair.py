from __future__ import annotations

import re
from typing import Any


def collect_relation_repair_issues(
    relation_payload: dict[str, Any],
    *,
    rewrite_fields: tuple[str, ...],
) -> list[str]:
    relations = dict(relation_payload.get("relations", {}) or {})
    issues: list[str] = []
    for pair_key, item in sorted(relations.items()):
        if not isinstance(item, dict):
            continue
        for field in rewrite_fields:
            value = str(item.get(field, "")).strip()
            if not value:
                if field == "hidden_attitude":
                    continue
                if field == "relation_change":
                    issues.append(f"{pair_key}.{field}: 为空")
                continue
            if looks_like_unstable_relation_scalar(value):
                issues.append(f"{pair_key}.{field}: 像剧情摘要或叙述片段 -> {value}")
            elif field == "relation_change" and len(value) > 12:
                issues.append(f"{pair_key}.{field}: 过长，不像关系趋势标签 -> {value}")
    return issues


def looks_like_unstable_relation_scalar(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if any(token in text for token in ('"', "“", "”", "‘", "’", "「", "」")):
        return True
    if text.endswith(("：", ":", "，", ",", "；", ";", "、")):
        return True
    if len(text) > 42:
        return True
    return bool(
        re.search(
            r"(只见|忽见|回头|转过|只听|听见|听得|说道|笑道|问道|喝道|骂道|叹道|叫道|大家想着|心里还自|拍着手|走了出来|看了.*一眼|转过大厅|墙角边|旧诗有云)",
            text,
        )
    )


def build_relation_repair_messages(
    base_messages: list[dict[str, str]],
    *,
    relation_markdown: str,
    issues: list[str],
) -> list[dict[str, str]]:
    repair_instruction = "\n".join(
        [
            "## REPAIR_TASK",
            "你刚刚生成的关系图谱里，有少数关系字段更像剧情摘要、叙述碎句，或不像关系趋势结论。",
            "请只修正这些问题字段，让它们回到关系结论表达。",
            "typical_interaction 应写互动模式，不写具体桥段流水账。",
            "conflict_point 应写冲突焦点，不写整段剧情。",
            "relation_change 应写简短趋势，如升温、恶化、稳定、反复波动、固化。",
            "hidden_attitude 只在有表里落差时填写；没有证据可以留空。",
            "输出仍然必须是完整的 RELATION_GRAPH Markdown，不要解释。",
            "",
            "### ISSUES",
            *[f"- {item}" for item in issues],
            "",
            "### CURRENT_DRAFT",
            relation_markdown.strip(),
        ]
    ).strip()
    return [
        base_messages[0],
        {"role": "user", "content": f"{base_messages[1]['content']}\n\n{repair_instruction}"},
    ]
