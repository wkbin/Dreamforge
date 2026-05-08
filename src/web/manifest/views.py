from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable


def serialize_manifest(payload: dict[str, Any], *, run_id: str, file_urls: dict[str, str]) -> dict[str, Any]:
    manifest = dict(payload)
    if run_id:
        manifest["file_urls"] = dict(file_urls)
    return manifest


def discover_artifacts(
    manifest: dict[str, Any],
    *,
    discover_character_cards: Callable[[Path | None], list[dict[str, Any]]],
    discover_relation_graph: Callable[[Path | None, Path | None, Path | None], dict[str, Any] | None],
    build_progress_chunking_from_artifacts: Callable[[dict[str, Any] | None], dict[str, Any]],
    build_summary_chunking: Callable[[dict[str, Any] | None], dict[str, Any]],
) -> dict[str, Any]:
    updated = json.loads(json.dumps(manifest, ensure_ascii=False))
    webui = updated.get("webui", {})
    workspace = webui.get("workspace", {})
    run_dir = Path(str(webui.get("run_dir", ""))).resolve() if webui.get("run_dir") else None
    artifact_dir = Path(str(webui.get("artifact_dir", ""))).resolve() if webui.get("artifact_dir") else None
    characters_root = Path(str(workspace.get("characters_root", ""))).resolve() if workspace.get("characters_root") else None
    relations_root = Path(str(workspace.get("relations_root", ""))).resolve() if workspace.get("relations_root") else None

    character_index = discover_character_cards(characters_root)
    if character_index:
        updated.setdefault("artifacts", {}).setdefault("character_dirs", {})
        updated["artifacts"]["character_dirs"] = {
            item["name"]: item["persona_dir"] for item in character_index
        }
        updated.setdefault("artifact_index", {})["characters"] = character_index
        completed_names = [item["name"] for item in character_index]
        updated.setdefault("progress", {})["completed_characters"] = completed_names
        updated["progress"]["completed_count"] = len(completed_names)
        if updated.get("locked_characters") and len(completed_names) >= len(updated["locked_characters"]):
            if updated["progress"].get("graph_status") == "complete":
                updated["summary"]["status_text"] = "waiting_for_verification"
            else:
                updated["summary"]["status_text"] = "graph_pending"
            updated["progress"]["current_character"] = ""
        updated["summary"]["characters_completed"] = len(completed_names)

    relation_graph = discover_relation_graph(relations_root, artifact_dir, run_dir)
    if relation_graph:
        updated.setdefault("artifacts", {})["relation_graph"] = relation_graph
        updated.setdefault("artifact_index", {})["relation_graph"] = relation_graph
        updated.setdefault("progress", {})["graph_status"] = "complete"
        if updated["summary"].get("status_text") in {"waiting_for_payloads", "waiting_for_host_generation", "graph_pending"}:
            updated["summary"]["status_text"] = "graph_ready"
        updated["summary"]["graph_status"] = "complete"

    updated.setdefault("progress", {}).setdefault(
        "chunking",
        build_progress_chunking_from_artifacts(updated.get("artifacts", {}).get("chunking", {})),
    )
    updated.setdefault("summary", {})["chunking"] = build_summary_chunking(updated.get("progress", {}).get("chunking", {}))
    return updated


def build_file_urls(
    *,
    run_id: str,
    manifest: dict[str, Any],
    manifest_path: Path,
    run_dir: Path,
) -> dict[str, str]:
    urls: dict[str, str] = {}
    manifest_relative = relative_to_run_dir(manifest_path, run_dir)
    if manifest_relative is not None:
        urls["manifest"] = file_url(run_id, manifest_relative)

    payloads = manifest.get("artifacts", {}).get("payloads", {})
    if isinstance(payloads, dict):
        for key, value in payloads.items():
            path = Path(str(value))
            if not path.exists():
                continue
            relative = relative_to_run_dir(path, run_dir)
            if relative is not None:
                urls[f"payload_{key}"] = file_url(run_id, relative)

    character_items = manifest.get("artifact_index", {}).get("characters", [])
    if isinstance(character_items, list):
        for item in character_items:
            profile = Path(str(item.get("profile_file", "")))
            if not profile.exists():
                continue
            relative = relative_to_run_dir(profile, run_dir)
            if relative is not None:
                urls[f"character_{item.get('name', '')}"] = file_url(run_id, relative)

    relation_graph = manifest.get("artifact_index", {}).get("relation_graph", {})
    if isinstance(relation_graph, dict):
        for key in ("html_path", "svg_path", "mermaid_path", "relations_file"):
            value = str(relation_graph.get(key, "")).strip()
            if not value:
                continue
            path = Path(value)
            if not path.exists():
                continue
            relative = relative_to_run_dir(path, run_dir)
            if relative is not None:
                urls[f"graph_{key.replace('_path', '')}"] = file_url(run_id, relative)

    return urls


def file_url(run_id: str, relative_path: Path) -> str:
    return f"/api/web/runs/{run_id}/files/{relative_path.as_posix()}"


def relative_to_run_dir(path: Path, run_dir: Path) -> Path | None:
    path_real = os.path.normcase(os.path.realpath(os.fspath(path)))
    run_real = os.path.normcase(os.path.realpath(os.fspath(run_dir)))
    try:
        common = os.path.commonpath([path_real, run_real])
    except ValueError:
        return None
    if common != run_real:
        return None
    relative_text = os.path.relpath(path_real, run_real)
    if relative_text in {".", ""}:
        return Path()
    return Path(relative_text)
