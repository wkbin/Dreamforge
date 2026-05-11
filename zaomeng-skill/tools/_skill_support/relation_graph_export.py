#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .workflow_completion import build_capability_status, build_relation_completion_status, default_status_path, update_run_manifest, write_json


MERMAID_VERSION = "11.14.0"
MERMAID_BUNDLE_NAME = f"mermaid-{MERMAID_VERSION}.min.js"


def export_relation_graph(
    relations_file: str | Path,
    *,
    novel_id: str | None = None,
    config_path: str | None = None,
    manifest_path: str | Path | None = None,
) -> dict[str, str]:
    del config_path
    relation_path = Path(relations_file).resolve()
    relations_payload = _load_relations_payload(relation_path)
    relations = relations_payload["relations"]
    resolved_novel_id = str(novel_id or relations_payload.get("novel_id") or _novel_id_from_name(relation_path.stem)).strip()
    if not resolved_novel_id:
        raise ValueError("无法确定 novel_id")
    if not relations:
        raise ValueError("关系文件中没有可导出的 relations 数据")

    output_dir = relation_path.parent
    base_name = relation_path.stem
    mermaid_path = output_dir / f"{base_name}.mermaid.md"
    html_path = output_dir / f"{base_name}.html"
    mermaid_runtime_filename = _ensure_mermaid_runtime_asset(output_dir)

    characters_root = _infer_characters_root(relation_path, resolved_novel_id)
    node_styles = _build_visual_node_styles(characters_root, relations)
    mermaid_graph = _render_mermaid_graph(relations, node_styles=node_styles)
    html_text = _render_relation_html(
        resolved_novel_id,
        relations,
        node_styles=node_styles,
        mermaid_graph=mermaid_graph,
        mermaid_runtime_filename=mermaid_runtime_filename,
    )

    mermaid_path.write_text(mermaid_graph + "\n", encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")

    status_payload = build_relation_completion_status(
        relation_path,
        novel_id=resolved_novel_id,
        html_path=html_path,
        mermaid_path=mermaid_path,
    )
    status_path = write_json(output_dir / f"{base_name}.status.json", status_payload)
    capability_status_path = default_status_path(
        "export_graph",
        manifest_path=manifest_path,
        output_dir=output_dir,
    )
    capability_status = build_capability_status(
        "export_graph",
        status=status_payload["status"],
        success=bool(status_payload.get("success")),
        novel_id=resolved_novel_id,
        inputs={"relations_file": str(relation_path)},
        outputs={
            "html_path": str(html_path),
            "mermaid_path": str(mermaid_path),
            "relation_status_path": str(status_path),
        },
        manifest_path=manifest_path,
        message="relation graph exported",
    )
    write_json(capability_status_path, capability_status)
    if manifest_path:
        update_run_manifest(
            manifest_path,
            stage="graph_export_completed",
            status="running",
            message="relation graph exported",
            capability="export_graph",
            capability_status=capability_status,
            artifact_updates={
                "relation_graph": {
                    "html_path": str(html_path),
                    "mermaid_path": str(mermaid_path),
                    "relation_status_path": str(status_path),
                },
                "status_files": {"export_graph": str(capability_status_path.resolve())},
            },
            status_file=capability_status_path,
            graph_status="complete",
        )

    return {
        "novel_id": resolved_novel_id,
        "html_path": str(html_path),
        "mermaid_path": str(mermaid_path),
        "status_path": str(status_path),
        "capability_status_path": str(capability_status_path),
    }


def _load_relations_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        payload = json.loads(text)
        return {
            "novel_id": payload.get("novel_id", ""),
            "relations": dict(payload.get("relations", {}) or {}),
        }

    novel_id = ""
    relations: dict[str, dict[str, Any]] = {}
    current_key = ""
    current_payload: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- novel_id:"):
            novel_id = line.split(":", 1)[1].strip()
            continue
        if line.startswith("## "):
            current_key = line[3:].strip()
            current_payload = {}
            relations[current_key] = current_payload
            continue
        if line.startswith("- ") and ":" in line and current_payload is not None:
            key, raw_value = line[2:].split(":", 1)
            current_payload[key.strip()] = _coerce_value(raw_value.strip())

    return {"novel_id": novel_id, "relations": relations}


def _coerce_value(value: str) -> Any:
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _novel_id_from_name(name: str) -> str:
    text = str(name or "").strip()
    text = re.sub(r"(?i)_?relations?$", "", text).strip("_- ")
    return text


def _infer_characters_root(relation_path: Path, novel_id: str) -> Path | None:
    parts = list(relation_path.parts)
    try:
        index = parts.index("relations")
    except ValueError:
        return None
    base = Path(*parts[:index])
    candidate = base / "characters" / novel_id
    return candidate if candidate.exists() else None


def _build_relation_entries(relations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for pair_key, payload in sorted(relations.items()):
        names = pair_key.split("_")
        if len(names) != 2:
            continue
        trust = int(payload.get("trust", 5))
        affection = int(payload.get("affection", 5))
        hostility = int(payload.get("hostility", max(0, 5 - affection)))
        hidden_attitude = str(payload.get("hidden_attitude", "")).strip()
        conflict_point = str(payload.get("conflict_point", "")).strip()
        interaction = str(payload.get("typical_interaction", "")).strip()
        evolution = str(payload.get("relation_change", "")).strip() or _infer_evolution(trust, affection, hostility)
        relation_type = str(payload.get("relationship_type", "")).strip() or _infer_relationship_type(
            trust,
            affection,
            hostility,
            conflict_point,
            hidden_attitude,
        )
        intensity = _intensity_score(trust, affection, hostility)
        stability_score = _stability_score(evolution, int(payload.get("confidence", 6)), hidden_attitude)
        entries.append(
            {
                "key": pair_key,
                "trust": trust,
                "affection": affection,
                "hostility": hostility,
                "power_gap": int(payload.get("power_gap", 0)),
                "confidence": int(payload.get("confidence", 6)),
                "relationship_type": relation_type,
                "intensity": intensity,
                "stability_label": _stability_label(stability_score),
                "evolution": evolution,
                "conflict_point": conflict_point,
                "typical_interaction": interaction,
                "hidden_attitude": hidden_attitude,
                "evidence_summary": _evidence_summary(interaction, conflict_point, hidden_attitude),
            }
        )
    return entries


def _infer_relationship_type(
    trust: int,
    affection: int,
    hostility: int,
    conflict_point: str,
    hidden_attitude: str,
) -> str:
    if hostility >= 7:
        return "对立"
    if affection >= 8 and trust >= 8:
        return "深厚"
    if affection >= 7 and trust >= 6:
        return "亲近"
    if hostility >= 5 and affection >= 5:
        return "拉扯"
    if hostility >= 4 and conflict_point:
        return "竞争"
    if trust >= 7:
        return "协作"
    if hidden_attitude:
        return "复杂"
    return "中性"


def _infer_evolution(trust: int, affection: int, hostility: int) -> str:
    if hostility >= 7:
        return "恶化"
    if affection >= 7 and trust >= 7:
        return "升温"
    if hostility >= 5 and affection >= 5:
        return "反复波动"
    return "稳定"


def _intensity_score(trust: int, affection: int, hostility: int) -> int:
    return max(0, min(10, int(round((trust + affection + hostility) / 3))))


def _stability_score(evolution: str, confidence: int, hidden_attitude: str) -> int:
    score = confidence
    if evolution in {"反复波动", "恶化"}:
        score -= 3
    elif evolution == "升温":
        score -= 1
    if hidden_attitude:
        score -= 1
    return max(1, min(10, score))


def _stability_label(score: int) -> str:
    if score >= 8:
        return "稳定"
    if score >= 5:
        return "可变"
    return "脆弱"


def _evidence_summary(interaction: str, conflict_point: str, hidden_attitude: str) -> str:
    values = [value for value in (interaction, conflict_point, hidden_attitude) if value]
    return "；".join(values) or "证据摘要未提供"


def _build_visual_node_styles(
    characters_root: Path | None,
    relations: dict[str, dict[str, Any]],
) -> dict[str, dict[str, str]]:
    profile_metadata = _load_profile_visual_metadata(characters_root)
    node_names = _relation_node_names(relations)
    categories: list[str] = []
    node_styles: dict[str, dict[str, str]] = {}

    for name in node_names:
        profile = profile_metadata.get(name, {})
        category_key, legend = _node_category(profile)
        if category_key not in categories:
            categories.append(category_key)
        node_styles[name] = {
            "category_key": category_key,
            "legend": legend,
            "faction_position": str(profile.get("faction_position", "")).strip(),
            "story_role": str(profile.get("story_role", "")).strip(),
            "world_belong": str(profile.get("world_belong", "")).strip(),
        }

    palette_map: dict[str, dict[str, str]] = {}
    for index, category_key in enumerate(categories):
        palette = _category_palette(index)
        palette_map[category_key] = {
            "class_name": f"group_{index}",
            "fill": palette["fill"],
            "stroke": palette["stroke"],
            "text": palette["text"],
        }

    fallback = _default_node_style()
    for name, style in node_styles.items():
        style.update(palette_map.get(style.get("category_key", ""), fallback))

    return node_styles


def _load_profile_visual_metadata(root: Path | None) -> dict[str, dict[str, str]]:
    if root is None or not root.exists():
        return {}
    metadata: dict[str, dict[str, str]] = {}
    for persona_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        merged: dict[str, str] = {}
        for filename in ("PROFILE.generated.md", "PROFILE.md"):
            profile_path = persona_dir / filename
            if not profile_path.exists():
                continue
            merged.update(_parse_profile_visual_metadata(profile_path))
        if merged:
            metadata[persona_dir.name] = merged
    return metadata


def _parse_profile_visual_metadata(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in {"faction_position", "story_role", "world_belong"} and value:
            parsed[key] = value
    return parsed


def _relation_node_names(relations: dict[str, dict[str, Any]]) -> list[str]:
    names = set()
    for pair_key in relations:
        parts = pair_key.split("_")
        if len(parts) == 2:
            names.update(parts)
    return sorted(names)


def _node_category(profile: dict[str, str]) -> tuple[str, str]:
    faction = str(profile.get("faction_position", "")).strip()
    if faction:
        return f"faction::{faction}", f"阵营：{faction}"
    world_belong = str(profile.get("world_belong", "")).strip()
    if world_belong:
        return f"world::{world_belong}", f"归属：{world_belong}"
    role = str(profile.get("story_role", "")).strip()
    if role:
        return f"role::{role}", f"角色：{role}"
    return "unknown", "未标注阵营/角色"


def _category_palette(index: int) -> dict[str, str]:
    palette = [
        {"fill": "#fde2e2", "stroke": "#c43d3d", "text": "#6d1616"},
        {"fill": "#ece6ff", "stroke": "#7a56d1", "text": "#46237f"},
        {"fill": "#e4f5e7", "stroke": "#2d8a4d", "text": "#18532c"},
        {"fill": "#ffe9cf", "stroke": "#c77719", "text": "#7b4312"},
        {"fill": "#e0f2fe", "stroke": "#0d8bb1", "text": "#164e63"},
        {"fill": "#fce7f3", "stroke": "#c0267c", "text": "#831843"},
    ]
    return palette[index % len(palette)]


def _default_node_style() -> dict[str, str]:
    return {
        "class_name": "group_unknown",
        "legend": "未标注阵营/角色",
        "fill": "#f3f4f6",
        "stroke": "#6b7280",
        "text": "#111827",
        "faction_position": "",
        "story_role": "",
        "world_belong": "",
    }


def _render_mermaid_graph(
    relations: dict[str, dict[str, Any]],
    *,
    node_styles: dict[str, dict[str, str]] | None = None,
) -> str:
    lines = ["graph LR"]
    node_styles = node_styles or {}
    node_classes: dict[str, dict[str, str]] = {}
    link_styles: list[str] = []
    node_ids = {name: _graph_id(name, index) for index, name in enumerate(_relation_node_names(relations))}

    for pair_key, payload in sorted(relations.items()):
        names = pair_key.split("_")
        if len(names) != 2:
            continue
        left, right = names
        trust = int(payload.get("trust", 5))
        affection = int(payload.get("affection", 5))
        hostility = int(payload.get("hostility", max(0, 5 - affection)))
        closeness = _closeness_score(trust, affection)
        hidden_attitude = str(payload.get("hidden_attitude", "")).strip()
        relation_type = str(payload.get("relationship_type", "")).strip() or _infer_relationship_type(
            trust,
            affection,
            hostility,
            str(payload.get("conflict_point", "")).strip(),
            hidden_attitude,
        )
        evolution = str(payload.get("relation_change", "")).strip() or _infer_evolution(trust, affection, hostility)
        intensity = _intensity_score(trust, affection, hostility)
        stability_score = _stability_score(evolution, int(payload.get("confidence", 6)), hidden_attitude)
        label = f"信{trust} 情{affection} 冲{hostility}"
        left_id = node_ids.setdefault(left, _graph_id(left, len(node_ids)))
        right_id = node_ids.setdefault(right, _graph_id(right, len(node_ids)))
        lines.append(
            f"    {left_id}[\"{_mermaid_escape(left)}\"] ---|{_mermaid_escape(label)}| {right_id}[\"{_mermaid_escape(right)}\"]"
        )
        node_classes[left] = node_styles.get(left, _default_node_style())
        node_classes[right] = node_styles.get(right, _default_node_style())
        link_styles.append(
            _edge_style(
                trust,
                hostility,
                closeness,
                relation_type=relation_type,
                intensity=intensity,
                stability_score=stability_score,
                hidden_attitude=hidden_attitude,
            )
        )

    if len(lines) == 1:
        placeholder = _default_node_style()
        lines.append("    node_empty[\"暂无关系数据\"]")
        node_classes["empty"] = {**placeholder, "class_name": "group_empty"}

    class_definitions: dict[str, dict[str, str]] = {}
    for name, style in sorted(node_classes.items()):
        class_name = style.get("class_name", "group_unknown")
        node_id = "node_empty" if name == "empty" else node_ids.get(name, _graph_id(name, len(node_ids)))
        lines.append(f"    class {node_id} {class_name}")
        class_definitions[class_name] = style
    for class_name, style in sorted(class_definitions.items()):
        lines.append(
            "    classDef "
            f"{class_name} "
            f"fill:{style.get('fill', '#f3f4f6')},"
            f"stroke:{style.get('stroke', '#6b7280')},"
            f"color:{style.get('text', '#111827')},"
            "stroke-width:2px"
        )
    for index, style in enumerate(link_styles):
        lines.append(f"    linkStyle {index} {style}")
    return "\n".join(lines)


def _render_relation_html(
    novel_id: str,
    relations: dict[str, dict[str, Any]],
    *,
    node_styles: dict[str, dict[str, str]],
    mermaid_graph: str,
    mermaid_runtime_filename: str = "",
) -> str:
    relation_entries = _build_relation_entries(relations)
    relation_types = sorted({entry["relationship_type"] for entry in relation_entries})
    table_rows: list[str] = []
    for entry in relation_entries:
        tooltip = html.escape(entry["evidence_summary"])
        tone = _type_tone(entry["relationship_type"])
        table_rows.append(
            "<tr "
            f"data-type=\"{html.escape(entry['relationship_type'])}\" "
            f"data-trust=\"{entry['trust']}\" "
            f"data-intensity=\"{entry['intensity']}\" "
            f"title=\"{tooltip}\">"
            f"<td><span class=\"pair-key\">{html.escape(entry['key'])}</span></td>"
            f"<td><span class=\"badge {tone}\">{html.escape(entry['relationship_type'])}</span></td>"
            f"<td>{_metric_badge(entry['trust'], 'trust')}</td>"
            f"<td>{_metric_badge(entry['affection'], 'affection')}</td>"
            f"<td>{_metric_badge(entry['hostility'], 'hostility')}</td>"
            f"<td>{entry['intensity']}</td>"
            f"<td>{html.escape(entry['stability_label'])}</td>"
            f"<td>{html.escape(entry['evolution'])}</td>"
            f"<td>{html.escape(entry['conflict_point']) or '<span class=\"muted\">-</span>'}</td>"
            f"<td>{html.escape(entry['typical_interaction']) or '<span class=\"muted\">-</span>'}</td>"
            "</tr>"
        )
    if not table_rows:
        table_rows.append("<tr><td colspan=\"10\"><span class=\"muted\">暂无关系数据，生成后这里会显示图谱和明细。</span></td></tr>")

    relation_cards: list[str] = []
    for entry in relation_entries:
        tooltip = html.escape(entry["evidence_summary"])
        tone = _type_tone(entry["relationship_type"])
        relation_cards.append(
            "<li class=\"relation-item\" "
            f"data-type=\"{html.escape(entry['relationship_type'])}\" "
            f"data-trust=\"{entry['trust']}\" "
            f"data-intensity=\"{entry['intensity']}\" "
            f"title=\"{tooltip}\">"
            "<div>"
            "<div class=\"relation-head\">"
            f"<strong>{html.escape(entry['key'])}</strong>"
            f"<span class=\"badge {tone}\">{html.escape(entry['relationship_type'])}</span>"
            f"<span class=\"badge neutral\">{html.escape(entry['evolution'])}</span>"
            "</div>"
            "<div class=\"metric-row\">"
            f"{_metric_badge(entry['trust'], 'trust')}"
            f"{_metric_badge(entry['affection'], 'affection')}"
            f"{_metric_badge(entry['hostility'], 'hostility')}"
            f"{_metric_badge(entry['intensity'], 'intensity')}"
            "</div>"
            f"<div class=\"relation-meta\">稳定性：{html.escape(entry['stability_label'])} / 置信度：{entry['confidence']}</div>"
            f"<div class=\"relation-meta\">证据摘要：{html.escape(entry['evidence_summary'])}</div>"
            f"<div class=\"relation-meta\">典型互动：{html.escape(entry['typical_interaction']) or '未提供'}</div>"
            f"<div class=\"relation-meta\">冲突焦点：{html.escape(entry['conflict_point']) or '未提供'}</div>"
            f"<div class=\"relation-meta\">隐藏态度：{html.escape(entry['hidden_attitude']) or '未提供'}</div>"
            "</div>"
            "</li>"
        )
    if not relation_cards:
        relation_cards.append("<li class=\"empty\">暂无关系卡片。</li>")

    escaped_mermaid = html.escape(mermaid_graph)
    embedded_graph_html = ""
    relation_count = len(relation_entries)
    relation_entries_json = html.escape(json.dumps(relation_entries, ensure_ascii=False))
    node_styles_json = html.escape(json.dumps(node_styles, ensure_ascii=False))
    default_style_json = html.escape(json.dumps(_default_node_style(), ensure_ascii=False))
    runtime_script_tag = (
        f'  <script src="{html.escape(mermaid_runtime_filename)}"></script>\n'
        if mermaid_runtime_filename
        else ""
    )
    unique_categories: list[tuple[str, dict[str, str]]] = []
    seen_categories = set()
    for style in node_styles.values():
        class_name = style.get("class_name", "group_unknown")
        if class_name in seen_categories:
            continue
        seen_categories.add(class_name)
        unique_categories.append((class_name, style))
    node_cards: list[str] = []
    for name, style in sorted(node_styles.items()):
        details = []
        faction = str(style.get("faction_position", "")).strip()
        world_belong = str(style.get("world_belong", "")).strip()
        role = str(style.get("story_role", "")).strip()
        if faction:
            details.append(f"阵营：{html.escape(faction)}")
        if world_belong:
            details.append(f"归属：{html.escape(world_belong)}")
        if role:
            details.append(f"角色：{html.escape(role)}")
        if not details:
            details.append("未标注阵营/角色")
        node_cards.append(
            "<li class=\"node-item\" "
            f"title=\"{html.escape(' / '.join(details))}\">"
            f"<span class=\"swatch\" style=\"background:{style.get('fill', '#f3f4f6')}; border-color:{style.get('stroke', '#6b7280')};\"></span>"
            "<div>"
            f"<strong>{html.escape(name)}</strong>"
            f"<span>{' / '.join(details)}</span>"
            "</div>"
            "</li>"
        )
    if not node_cards:
        node_cards.append("<li class=\"node-item muted\">暂无节点元数据</li>")
    category_legend = "".join(
        (
            "<span class=\"legend-item\">"
            f"<span class=\"swatch\" style=\"background:{style.get('fill', '#f3f4f6')}; border-color:{style.get('stroke', '#6b7280')};\"></span>"
            f"{html.escape(style.get('legend', '未标注阵营/角色'))}"
            "</span>"
        )
        for _, style in unique_categories
    )
    conflict_count = sum(1 for entry in relation_entries if entry["hostility"] >= 6)
    high_trust_count = sum(1 for entry in relation_entries if entry["trust"] >= 7)
    visible_nodes = len(_relation_node_names(relations))
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        f"  <title>{html.escape(novel_id)} 人物关系图谱</title>\n"
        "  <style>\n"
        "    :root { --bg:#f6efe2; --ink:#1f2937; --muted:#6b7280; --line:#d6c7a7; --card:#fffaf0; --warm:#8a5a2b; --trust:#156f55; --affection:#b4583a; --hostility:#b42318; }\n"
        "    * { box-sizing:border-box; }\n"
        "    body { font-family: 'Noto Serif SC', 'Source Han Serif SC', serif; margin: 0; background: radial-gradient(circle at top, #fff9ef, var(--bg)); color: var(--ink); }\n"
        "    .page { max-width: 1280px; margin: 0 auto; padding: 28px 20px 36px; }\n"
        "    h1 { margin: 0 0 8px; font-size: 32px; }\n"
        "    .subtitle { color: var(--muted); margin-bottom: 20px; }\n"
        "    .summary { display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }\n"
        "    .filters { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px; }\n"
        "    .stat { background: linear-gradient(180deg, #fffdf8, #f7edd8); border:1px solid var(--line); border-radius: 14px; padding: 14px 16px; }\n"
        "    .filter { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; }\n"
        "    .filter label { display:block; color: var(--muted); font-size: 12px; margin-bottom: 8px; }\n"
        "    .filter input, .filter select { width: 100%; padding: 8px 10px; border-radius: 10px; border:1px solid #d8c6a1; background:#fffdf8; color: var(--ink); }\n"
        "    .stat-label { display:block; color: var(--muted); font-size: 12px; letter-spacing: .08em; margin-bottom: 8px; }\n"
        "    .stat-value { font-size: 26px; color: var(--warm); }\n"
        "    .grid { display:grid; grid-template-columns: minmax(0, 1.35fr) minmax(340px, .95fr); gap: 18px; align-items:start; }\n"
        "    .stack { display:grid; grid-template-columns: 1fr; gap: 18px; align-items:start; }\n"
        "    .card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 18px; box-shadow: 0 10px 35px rgba(90, 60, 20, .06); }\n"
        "    .card h2 { margin: 0 0 12px; font-size: 19px; }\n"
        "    .legend { display:flex; flex-wrap:wrap; gap:10px; margin: 4px 0 12px; }\n"
        "    .legend-item { display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; background:#fff; border:1px solid var(--line); font-size:13px; }\n"
        "    .swatch { width:12px; height:12px; border-radius:999px; display:inline-block; border:2px solid transparent; flex:0 0 auto; }\n"
        "    .edge-rule { display:grid; gap:10px; margin-top: 14px; }\n"
        "    .edge-rule strong { display:block; margin-bottom: 4px; }\n"
        "    .graph-shell { min-height: 480px; background: linear-gradient(180deg, #fffef9, #fcf5e8); border:1px dashed #dbc8a4; border-radius: 14px; padding: 12px; }\n"
        "    .graph-image { display:block; width:100%; height:auto; }\n"
        "    .mermaid { text-align:center; }\n"
        "    pre { white-space: pre-wrap; overflow-x: auto; background: #fffdf8; padding: 16px; border-radius: 12px; border:1px solid var(--line); }\n"
        "    details { margin-top: 16px; }\n"
        "    details summary { cursor: pointer; color: var(--warm); font-weight: 600; }\n"
        "    .node-list, .relation-list { list-style:none; margin:0; padding:0; display:grid; gap:10px; }\n"
        "    .node-item { display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:12px; background:#fffdf8; border:1px solid var(--line); }\n"
        "    .relation-item { display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:12px; background:#fffdf8; border:1px solid var(--line); }\n"
        "    .node-item strong { display:block; margin-bottom:4px; }\n"
        "    .node-item span { color: var(--muted); font-size: 13px; }\n"
        "    .relation-head { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:6px; }\n"
        "    .relation-meta { color: var(--muted); font-size: 13px; margin-top: 4px; }\n"
        "    .badge { display:inline-flex; align-items:center; padding:4px 9px; border-radius:999px; font-size:12px; border:1px solid transparent; }\n"
        "    .badge.warm { background:#e6f6ef; color:#166b49; border-color:#b7e2cf; }\n"
        "    .badge.mixed { background:#fff1dc; color:#9a5c0d; border-color:#f3d29d; }\n"
        "    .badge.danger { background:#fde8e7; color:#9f271f; border-color:#f3b6b1; }\n"
        "    .badge.neutral { background:#eef2f7; color:#475467; border-color:#cdd5df; }\n"
        "    .metric-row { display:flex; gap:8px; flex-wrap:wrap; margin: 6px 0; }\n"
        "    .table-shell { width: 100%; overflow-x: auto; border-radius: 12px; }\n"
        "    table { width: 100%; min-width: 980px; border-collapse: collapse; background: white; }\n"
        "    th, td { border: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }\n"
        "    th { background: #efe3c5; }\n"
        "    .pair-key { font-weight: 600; color: #4b3a28; }\n"
        "    .metric { display:inline-flex; min-width:40px; justify-content:center; padding:4px 10px; border-radius:999px; font-weight:700; color:#fff; }\n"
        "    .metric.trust { background: var(--trust); }\n"
        "    .metric.affection { background: var(--affection); }\n"
        "    .metric.hostility { background: var(--hostility); }\n"
        "    .metric.intensity { background: #6b7280; }\n"
        "    .muted { color: var(--muted); }\n"
        "    .empty { padding: 16px; border-radius: 12px; background:#fffdf8; border:1px dashed var(--line); color: var(--muted); }\n"
        "    .note { color: var(--muted); font-size: 13px; margin-top: 10px; }\n"
        "    @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } .page { padding: 20px 14px 28px; } h1 { font-size: 26px; } }\n"
        "  </style>\n"
        "  <script type=\"application/json\" id=\"relation-data\">"
        + relation_entries_json
        + "</script>\n"
        "  <script type=\"application/json\" id=\"node-style-data\">"
        + node_styles_json
        + "</script>\n"
        "  <script type=\"application/json\" id=\"default-style-data\">"
        + default_style_json
        + "</script>\n"
        + runtime_script_tag
        + "  <script>\n"
        "    const relationEntries = JSON.parse(document.getElementById('relation-data').textContent);\n"
        "    const nodeStyles = JSON.parse(document.getElementById('node-style-data').textContent);\n"
        "    const defaultStyle = JSON.parse(document.getElementById('default-style-data').textContent);\n"
        "    const escapeLabel = (value) => String(value).replace(/\\\\/g, '\\\\\\\\').replace(/\"/g, '\\\\\"');\n"
        "    const buildNodeIds = (entries) => {\n"
        "      const names = Array.from(new Set(entries.flatMap((entry) => entry.key.split('_')))).sort((a, b) => a.localeCompare(b, 'zh-CN'));\n"
        "      return new Map(names.map((name, index) => [name, `n${index}`]));\n"
        "    };\n"
        "    const edgeStyle = (entry) => {\n"
        "      const parts = [`stroke:${entry.hostility >= Math.max(6, entry.trust) ? '#c53b30' : (entry.relationship_type === '拉扯' || entry.relationship_type === '竞争') ? '#d18a1d' : entry.trust >= 8 ? '#1f8f63' : '#8a5a2b'}`, `stroke-width:${Math.max(2, Math.min(7, 1 + Math.round(entry.intensity / 2)))}px`];\n"
        "      if (entry.hidden_attitude || entry.stability_label === '脆弱') parts.push('stroke-dasharray:8 4');\n"
        "      return parts.join(',');\n"
        "    };\n"
        "    const buildMermaid = (entries) => {\n"
        "      const lines = ['graph LR'];\n"
        "      const nodeIds = buildNodeIds(entries);\n"
        "      const nodeClasses = new Map();\n"
        "      const classDefs = new Map();\n"
        "      if (!entries.length) {\n"
        "        lines.push('    node_empty[\"暂无符合筛选条件的关系\"]');\n"
        "        nodeClasses.set('empty', { ...defaultStyle, class_name: 'group_empty' });\n"
        "        classDefs.set('group_empty', { ...defaultStyle, class_name: 'group_empty' });\n"
        "      }\n"
        "      entries.forEach((entry) => {\n"
        "        const [left, right] = entry.key.split('_');\n"
        "        const leftId = nodeIds.get(left);\n"
        "        const rightId = nodeIds.get(right);\n"
        "        lines.push(`    ${leftId}[\"${escapeLabel(left)}\"] ---|${escapeLabel(`信${entry.trust} 情${entry.affection} 冲${entry.hostility}`)}| ${rightId}[\"${escapeLabel(right)}\"]`);\n"
        "        [left, right].forEach((name) => {\n"
        "          const style = nodeStyles[name] || defaultStyle;\n"
        "          nodeClasses.set(name, style);\n"
        "          classDefs.set(style.class_name, style);\n"
        "        });\n"
        "      });\n"
        "      Array.from(nodeClasses.entries()).sort(([a], [b]) => a.localeCompare(b, 'zh-CN')).forEach(([name, style]) => {\n"
        "        const nodeId = name === 'empty' ? 'node_empty' : nodeIds.get(name);\n"
        "        lines.push(`    class ${nodeId} ${style.class_name}`);\n"
        "      });\n"
        "      Array.from(classDefs.entries()).sort(([a], [b]) => a.localeCompare(b, 'zh-CN')).forEach(([className, style]) => {\n"
        "        lines.push(`    classDef ${className} fill:${style.fill},stroke:${style.stroke},color:${style.text},stroke-width:2px`);\n"
        "      });\n"
        "      entries.forEach((entry, index) => lines.push(`    linkStyle ${index} ${edgeStyle(entry)}`));\n"
        "      return lines.join('\\n');\n"
        "    };\n"
        "    const renderGraph = async (entries) => {\n"
        "      const definition = buildMermaid(entries);\n"
        "      document.getElementById('graph-source').textContent = definition;\n"
        "      const target = document.getElementById('graph-view');\n"
        "      const hasEmbeddedGraphic = Boolean(target.querySelector('svg, img, object'));\n"
        "      if (hasEmbeddedGraphic) {\n"
        "        return;\n"
        "      }\n"
        "      if (!window.mermaid) {\n"
        "        if (!target.querySelector('svg')) {\n"
        "          target.innerHTML = '<div class=\"empty\">Mermaid 脚本未加载成功。本地 file 页面可能被浏览器限制了外链脚本，请改用本地静态服务打开，或直接查看下方 Mermaid 源码。</div>';\n"
        "        }\n"
        "        return;\n"
        "      }\n"
        "      try {\n"
        "        window.mermaid.initialize({ startOnLoad: false, theme: 'base', securityLevel: 'loose', themeVariables: { primaryTextColor: '#1f2937', lineColor: '#7b5b34', primaryBorderColor: '#8a5a2b', clusterBorder: '#d6c7a7', fontFamily: 'Noto Serif SC, Source Han Serif SC, serif' } });\n"
        "        const rendered = await window.mermaid.render(`graph-${Date.now()}`, definition);\n"
        "        target.innerHTML = rendered.svg;\n"
        "      } catch (error) {\n"
        "        console.error('Mermaid render failed:', error);\n"
        "        target.innerHTML = '<div class=\"empty\">关系网络图渲染失败，请展开下方 Mermaid 源码检查语法。</div>';\n"
        "      }\n"
        "    };\n"
        "    const applyFilters = async () => {\n"
        "      const type = document.getElementById('filter-type').value;\n"
        "      const minTrust = Number(document.getElementById('filter-trust').value || 0);\n"
        "      const minIntensity = Number(document.getElementById('filter-intensity').value || 0);\n"
        "      const filtered = relationEntries.filter((entry) => (!type || entry.relationship_type === type) && entry.trust >= minTrust && entry.intensity >= minIntensity);\n"
        "      document.querySelectorAll('[data-type][data-trust][data-intensity]').forEach((element) => {\n"
        "        const visible = (!type || element.dataset.type === type) && Number(element.dataset.trust) >= minTrust && Number(element.dataset.intensity) >= minIntensity;\n"
        "        element.style.display = visible ? '' : 'none';\n"
        "      });\n"
        "      await renderGraph(filtered);\n"
        "    };\n"
        "    window.addEventListener('DOMContentLoaded', async () => {\n"
        "      ['filter-type', 'filter-trust', 'filter-intensity'].forEach((id) => document.getElementById(id).addEventListener('input', () => { void applyFilters(); }));\n"
        "      await applyFilters();\n"
        "    });\n"
        "  </script>\n"
        "</head>\n"
        "<body>\n"
        "  <div class=\"page\">\n"
        f"    <h1>{html.escape(novel_id)} 人物关系图谱</h1>\n"
        f"    <div class=\"subtitle\">共 {relation_count} 条关系。节点颜色优先按阵营，其次按归属与角色类型；绿色边偏信任，红色边偏冲突，橙色边偏拉扯，线越粗表示关系越强，虚线表示关系更不稳定或存在更强的隐藏态度。</div>\n"
        "    <div class=\"summary\">\n"
        f"      <div class=\"stat\"><span class=\"stat-label\">关系总数</span><span class=\"stat-value\">{relation_count}</span></div>\n"
        f"      <div class=\"stat\"><span class=\"stat-label\">高信任关系</span><span class=\"stat-value\">{high_trust_count}</span></div>\n"
        f"      <div class=\"stat\"><span class=\"stat-label\">高冲突关系</span><span class=\"stat-value\">{conflict_count}</span></div>\n"
        f"      <div class=\"stat\"><span class=\"stat-label\">可见角色</span><span class=\"stat-value\">{visible_nodes}</span></div>\n"
        "    </div>\n"
        "    <div class=\"filters\">\n"
        "      <div class=\"filter\"><label for=\"filter-type\">关系类型</label><select id=\"filter-type\"><option value=\"\">全部</option>"
        + "".join(f"<option value=\"{html.escape(item)}\">{html.escape(item)}</option>" for item in relation_types)
        + "</select></div>\n"
        "      <div class=\"filter\"><label for=\"filter-trust\">最低信任值</label><input id=\"filter-trust\" type=\"range\" min=\"0\" max=\"10\" value=\"0\" /></div>\n"
        "      <div class=\"filter\"><label for=\"filter-intensity\">最低关系强度</label><input id=\"filter-intensity\" type=\"range\" min=\"0\" max=\"10\" value=\"0\" /></div>\n"
        "    </div>\n"
        "    <div class=\"grid\">\n"
        "      <div class=\"card\">\n"
        "        <h2>关系网络</h2>\n"
        f"        <div class=\"legend\">{category_legend or '<span class=\"legend-item\">暂无阵营/角色元数据</span>'}</div>\n"
        "        <div class=\"graph-shell\">\n"
        f"          <div id=\"graph-view\" class=\"mermaid\">{embedded_graph_html}</div>\n"
        "        </div>\n"
        "        <div class=\"edge-rule\">\n"
        "          <div><strong>边的颜色</strong><span class=\"muted\">绿色表示信任占优，橙色表示拉扯或竞争，红色表示冲突占优，棕色表示关系偏中性。</span></div>\n"
        "          <div><strong>边的样式</strong><span class=\"muted\">线越粗表示关系越强；虚线表示关系更脆弱，或表面关系与真实态度存在落差。</span></div>\n"
        "        </div>\n"
        "        <details>\n"
        "          <summary>查看 Mermaid 源码</summary>\n"
        f"          <pre id=\"graph-source\">{escaped_mermaid}</pre>\n"
        "        </details>\n"
        "      </div>\n"
        "      <div class=\"card\">\n"
        "        <h2>节点说明</h2>\n"
        "        <ul class=\"node-list\">\n"
        f"          {''.join(node_cards)}\n"
        "        </ul>\n"
        "        <div class=\"note\">颜色来自人物画像中的 `faction_position`、`world_belong` 或 `story_role`。悬停节点说明项可查看更完整信息。</div>\n"
        "      </div>\n"
        "    </div>\n"
        "    <div class=\"stack\" style=\"margin-top:18px;\">\n"
        "      <div class=\"card\">\n"
        "        <h2>关系卡片</h2>\n"
        "        <ul class=\"relation-list\">\n"
        f"          {''.join(relation_cards)}\n"
        "        </ul>\n"
        "      </div>\n"
        "      <div class=\"card\">\n"
        "      <h2>关系明细表</h2>\n"
        "      <div class=\"table-shell\">\n"
        "      <table>\n"
        "        <thead><tr><th>关系对</th><th>关系类型</th><th>信任</th><th>好感</th><th>冲突</th><th>强度</th><th>稳定性</th><th>演变</th><th>冲突焦点</th><th>典型互动</th></tr></thead>\n"
        f"        <tbody>{''.join(table_rows)}</tbody>\n"
        "      </table>\n"
        "      </div>\n"
        "      </div>\n"
        "    </div>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


def _closeness_score(trust: int, affection: int) -> int:
    return max(1, min(5, int(round((trust + affection) / 4))))


def _edge_style(
    trust: int,
    hostility: int,
    closeness: int,
    *,
    relation_type: str,
    intensity: int,
    stability_score: int,
    hidden_attitude: str,
) -> str:
    if hostility >= max(6, trust):
        color = "#c53b30"
    elif trust >= 8:
        color = "#1f8f63"
    elif relation_type in {"拉扯", "竞争"}:
        color = "#d18a1d"
    else:
        color = "#8a5a2b"
    width = max(2, min(7, max(closeness + 1, 1 + round(intensity / 2))))
    parts = [f"stroke:{color}", f"stroke-width:{width}px"]
    if hidden_attitude or stability_score <= 4:
        parts.append("stroke-dasharray:8 4")
    return ",".join(parts)


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _vendored_mermaid_asset_path() -> Path:
    return _skill_root() / "assets" / "vendor" / MERMAID_BUNDLE_NAME


def _load_vendored_mermaid_runtime() -> str:
    asset_path = _vendored_mermaid_asset_path()
    if not asset_path.exists():
        return ""
    return asset_path.read_text(encoding="utf-8")


def _ensure_mermaid_runtime_asset(output_dir: Path) -> str:
    asset_path = _vendored_mermaid_asset_path()
    if not asset_path.exists():
        return ""
    target_path = output_dir / asset_path.name
    if not target_path.exists():
        shutil.copy2(asset_path, target_path)
    return target_path.name


def _type_tone(relation_type: str) -> str:
    if relation_type in {"深厚", "亲近", "协作"}:
        return "warm"
    if relation_type in {"对立", "竞争"}:
        return "danger"
    if relation_type == "拉扯":
        return "mixed"
    return "neutral"


def _metric_badge(value: int, kind: str) -> str:
    return f"<span class=\"metric {kind}\">{value}</span>"


def _graph_id(name: str, index: int) -> str:
    return f"n{index}"


def _mermaid_escape(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
