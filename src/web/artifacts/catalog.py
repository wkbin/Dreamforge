from __future__ import annotations

from pathlib import Path
from typing import Any


def read_preview_fields(profile_path: Path) -> dict[str, str]:
    preview: dict[str, str] = {}
    wanted = {"name", "core_identity", "story_role", "soul_goal", "speech_style", "temperament_type"}
    for raw_line in profile_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        key = key.strip()
        if key in wanted and value.strip():
            preview[key] = value.strip()
    return preview


def discover_character_cards(characters_root: Path | None) -> list[dict[str, Any]]:
    if not characters_root or not characters_root.exists():
        return []
    cards: list[dict[str, Any]] = []
    for persona_dir in sorted(path for path in characters_root.iterdir() if path.is_dir()):
        profile_file = None
        for candidate_name in ("PROFILE.md", "PROFILE.generated.md"):
            candidate = persona_dir / candidate_name
            if candidate.exists():
                profile_file = candidate
                break
        if profile_file is None:
            continue
        preview = read_preview_fields(profile_file)
        cards.append(
            {
                "name": persona_dir.name,
                "persona_dir": str(persona_dir.resolve()),
                "profile_file": str(profile_file.resolve()),
                "generated_files": sorted(path.name for path in persona_dir.glob("*.generated.md")),
                "editable_files": sorted(
                    path.name for path in persona_dir.glob("*.md") if not path.name.endswith(".generated.md")
                ),
                "preview": {
                    "core_identity": preview.get("core_identity", ""),
                    "story_role": preview.get("story_role", ""),
                    "soul_goal": preview.get("soul_goal", ""),
                    "speech_style": preview.get("speech_style", ""),
                    "temperament_type": preview.get("temperament_type", ""),
                },
            }
        )
    return cards


def split_relation_pair(pair_key: str) -> tuple[str, str]:
    parts = [str(item).strip() for item in str(pair_key or "").split("_") if str(item).strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if parts:
        return parts[0], ""
    return "", ""


def coerce_relation_evidence(relation: dict[str, Any]) -> list[str]:
    raw = relation.get("evidence_lines", [])
    if isinstance(raw, list):
        lines = [str(item).strip() for item in raw if str(item).strip()]
    else:
        lines = []
    if lines:
        return lines[:3]
    fallback = [
        str(relation.get("typical_interaction", "")).strip(),
        str(relation.get("conflict_point", "")).strip(),
    ]
    return [item for item in fallback if item][:2]


def relation_type_label(relation: dict[str, Any]) -> str:
    configured = str(relation.get("relationship_type", "")).strip()
    if configured:
        return configured
    trust = int(relation.get("trust", 0) or 0)
    affection = int(relation.get("affection", 0) or 0)
    hostility = int(relation.get("hostility", 0) or 0)
    if hostility >= max(trust, affection) and hostility >= 6:
        return "对立"
    if affection >= 8 and trust >= 7:
        return "深情"
    if trust >= 7:
        return "亲近"
    if hostility >= 4:
        return "拉扯"
    return "牵连"


def resolve_persona_dir(manifest: dict[str, Any], character: str) -> Path:
    name = str(character or "").strip()
    if not name:
        raise ValueError("Character is required.")
    character_dirs = dict(manifest.get("artifacts", {}).get("character_dirs", {}) or {})
    direct = str(character_dirs.get(name, "")).strip()
    if direct:
        path = Path(direct)
        if path.exists():
            return path
    for item in manifest.get("artifact_index", {}).get("characters", []) or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("name", "")).strip() != name:
            continue
        persona_dir = Path(str(item.get("persona_dir", "")).strip())
        if persona_dir.exists():
            return persona_dir
    raise FileNotFoundError(name)


def resolve_relations_file(manifest: dict[str, Any]) -> Path:
    relation_graph = dict(manifest.get("artifact_index", {}).get("relation_graph", {}) or {})
    relation_path = Path(str(relation_graph.get("relations_file", "")).strip())
    if relation_path.exists():
        return relation_path
    raise FileNotFoundError("relations")


def discover_relation_graph(
    relations_root: Path | None,
    artifact_dir: Path | None,
    run_dir: Path | None,
) -> dict[str, str]:
    search_roots = [root for root in (relations_root, artifact_dir, run_dir) if root and root.exists()]
    candidates: dict[str, Path] = {}
    for root in search_roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if name.endswith(".html") and "relation" in name:
                candidates.setdefault("html_path", path)
            elif name.endswith(".svg") and "relation" in name:
                candidates.setdefault("svg_path", path)
            elif name.endswith(".mermaid.md"):
                candidates.setdefault("mermaid_path", path)
            elif name.endswith(".status.json") and "relation" in name:
                candidates.setdefault("relation_status_path", path)
            elif name.endswith(".md") and "relation" in name and not name.endswith(".mermaid.md"):
                candidates.setdefault("relations_file", path)
    return {key: str(path.resolve()) for key, path in candidates.items()}
