from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from src.web.run_ops.state import project_manifest_summary

from .compat import coerce_manifest_path, reconcile_discovered_artifacts, relative_to_run_dir


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
    relation_graph = discover_relation_graph(relations_root, artifact_dir, run_dir)
    updated = reconcile_discovered_artifacts(
        updated,
        character_index=character_index,
        relation_graph=relation_graph,
    )

    updated.setdefault("progress", {}).setdefault(
        "chunking",
        build_progress_chunking_from_artifacts(updated.get("artifacts", {}).get("chunking", {})),
    )
    updated.setdefault("summary", {})["chunking"] = build_summary_chunking(updated.get("progress", {}).get("chunking", {}))
    project_manifest_summary(updated)
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
            path = coerce_manifest_path(value)
            if path is None:
                continue
            relative = relative_to_run_dir(path, run_dir)
            if relative is not None:
                urls[f"payload_{key}"] = file_url(run_id, relative)

    character_items = manifest.get("artifact_index", {}).get("characters", [])
    if isinstance(character_items, list):
        for item in character_items:
            profile = coerce_manifest_path(item.get("profile_file", ""))
            if profile is None:
                continue
            relative = relative_to_run_dir(profile, run_dir)
            if relative is not None:
                urls[f"character_{item.get('name', '')}"] = file_url(run_id, relative)

    relation_graph = manifest.get("artifact_index", {}).get("relation_graph", {})
    if isinstance(relation_graph, dict):
        for key in ("html_path", "svg_path", "mermaid_path", "relations_file"):
            path = coerce_manifest_path(relation_graph.get(key, ""))
            if path is None:
                continue
            relative = relative_to_run_dir(path, run_dir)
            if relative is not None:
                urls[f"graph_{key.replace('_path', '')}"] = file_url(run_id, relative)

    return urls


def file_url(run_id: str, relative_path: Path) -> str:
    return f"/api/web/runs/{run_id}/files/{relative_path.as_posix()}"
