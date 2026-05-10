from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict

from src.utils.file_utils import safe_filename
from src.web.artifacts.ingest import decode_text_content


def ingest_character_result(
    *,
    run_id: str,
    runs_root: Path,
    manifest: dict[str, Any],
    character: str,
    content_base64: str,
    filename: str,
    materialize_profile_source: Callable[[Path, Path], dict[str, Any]],
    discover_artifacts: Callable[[dict[str, Any]], dict[str, Any]],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    run_dir = runs_root / run_id
    novel_id = str(manifest.get("novel_id", "")).strip() or run_id
    safe_character = safe_filename(character)
    host_output_dir = run_dir / "host_output" / novel_id / safe_character
    host_output_dir.mkdir(parents=True, exist_ok=True)
    source_path = host_output_dir / safe_filename(filename or "PROFILE.generated.md")
    source_text = decode_text_content(content_base64)
    source_path.write_text(source_text, encoding="utf-8")

    persona_dir = run_dir / "artifacts" / "characters" / novel_id / safe_character
    payload = materialize_profile_source(source_path, persona_dir)

    manifest.setdefault("capabilities", {})["materialize"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": f"{payload['character']} materialized",
    }
    manifest.setdefault("artifacts", {}).setdefault("character_dirs", {})
    manifest["artifacts"]["character_dirs"][payload["character"]] = payload["persona_dir"]
    manifest.setdefault("events", []).append(
        {
            "stage": "character_completed",
            "status": "running",
            "message": f"{payload['character']} 人物包已生成",
            "character": payload["character"],
            "capability": "materialize",
            "timestamp": utc_now(),
        }
    )
    refreshed = discover_artifacts(manifest)
    refreshed["updated_at"] = utc_now()
    return refreshed


def ingest_relation_result(
    *,
    run_id: str,
    runs_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    content_base64: str,
    filename: str,
    export_relations_source: Callable[[Path], dict[str, Any]],
    discover_artifacts: Callable[[dict[str, Any]], dict[str, Any]],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    run_dir = runs_root / run_id
    novel_id = str(manifest.get("novel_id", "")).strip() or run_id
    relations_dir = run_dir / "artifacts" / "relations"
    relations_dir.mkdir(parents=True, exist_ok=True)
    relation_source = relations_dir / safe_filename(filename or f"{novel_id}_relations.md")
    relation_source.write_text(decode_text_content(content_base64), encoding="utf-8")
    graph_payload = export_relations_source(relation_source)

    manifest.setdefault("capabilities", {})["export_graph"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": "relation graph exported",
    }
    manifest.setdefault("events", []).append(
        {
            "stage": "graph_export_completed",
            "status": "running",
            "message": "人物关系图谱已生成",
            "character": "",
            "capability": "export_graph",
            "timestamp": utc_now(),
        }
    )
    manifest.setdefault("artifacts", {})["relation_graph"] = dict(graph_payload)
    refreshed = discover_artifacts(manifest)
    refreshed["updated_at"] = utc_now()
    return refreshed


def list_relation_details(
    *,
    run_id: str,
    manifest: dict[str, Any],
    relations_file: Path,
    payload: dict[str, Any],
    split_relation_pair: Callable[[str], tuple[str, str]],
    relation_type_label: Callable[[dict[str, Any]], str],
    coerce_relation_evidence: Callable[[dict[str, Any]], list[str]],
) -> dict[str, Any]:
    relations = dict(payload.get("relations", {}) or {})
    conflicts = list(payload.get("conflicts", []) or [])
    items: list[dict[str, Any]] = []
    for pair_key, relation in sorted(relations.items()):
        if not isinstance(relation, dict):
            continue
        left, right = split_relation_pair(pair_key)
        items.append(
            {
                "pair_key": pair_key,
                "characters": [left, right],
                "trust": int(relation.get("trust", 0) or 0),
                "affection": int(relation.get("affection", 0) or 0),
                "hostility": int(relation.get("hostility", 0) or 0),
                "relationship_type": relation_type_label(relation),
                "relation_change": str(relation.get("relation_change", "")).strip(),
                "conflict_point": str(relation.get("conflict_point", "")).strip(),
                "typical_interaction": str(relation.get("typical_interaction", "")).strip(),
                "ambiguity": int(relation.get("ambiguity", 3) or 3),
                "evidence_lines": coerce_relation_evidence(relation),
            }
        )
    conflict_map = {}
    for item in conflicts:
        if not isinstance(item, dict):
            continue
        key = str(item.get("pair_key", "")).strip()
        if not key:
            continue
        conflict_map[key] = item
    return {
        "run_id": run_id,
        "novel_id": str(manifest.get("novel_id", "")).strip(),
        "relations_file": str(relations_file.resolve()),
        "relation_count": len(items),
        "conflict_count": len(conflict_map),
        "conflicts": list(conflict_map.values()),
        "items": items,
    }


def update_relation_detail(
    *,
    run_id: str,
    manifest: dict[str, Any],
    relations_file: Path,
    payload: dict[str, Any],
    pair_key: str,
    updates: dict[str, Any],
    save_relations: Callable[[Path, dict[str, Any]], None],
    detect_conflicts: Callable[[Dict[str, Dict[str, Any]]], list[Dict[str, Any]]],
) -> dict[str, Any]:
    novel_id = str(manifest.get("novel_id", "")).strip() or run_id
    relations = dict(payload.get("relations", {}) or {})
    if pair_key not in relations or not isinstance(relations.get(pair_key), dict):
        raise FileNotFoundError(pair_key)

    relation = dict(relations[pair_key])
    metric_fields = ("trust", "affection", "hostility", "ambiguity")
    text_fields = ("relationship_type", "relation_change", "conflict_point", "typical_interaction")
    for field in metric_fields:
        if field not in updates:
            continue
        try:
            relation[field] = max(0, min(10, int(updates.get(field, relation.get(field, 0)))))
        except (TypeError, ValueError):
            continue
    for field in text_fields:
        if field not in updates:
            continue
        relation[field] = str(updates.get(field, relation.get(field, "")) or "").strip()
    relation["updated_at"] = int(time.time())
    relations[pair_key] = relation

    updated_payload = dict(payload)
    updated_payload["novel_id"] = novel_id
    updated_payload["relations"] = relations
    updated_payload["conflicts"] = detect_conflicts(relations)
    save_relations(relations_file, updated_payload)
    return updated_payload


def resolve_run_file(*, runs_root: Path, run_id: str, relative_path: str) -> Path:
    run_dir = runs_root / run_id
    if not run_dir.exists():
        raise FileNotFoundError(run_id)
    candidate = (run_dir / relative_path).resolve()
    if run_dir.resolve() not in candidate.parents and candidate != run_dir.resolve():
        raise ValueError("Path escapes run directory.")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate
