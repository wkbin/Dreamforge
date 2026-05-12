from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from src.utils.file_utils import safe_filename
from src.skill_support.prompt_payloads import build_distill_prompt_payload
from src.skill_support.prompt_payloads import build_relation_prompt_payload
from src.web.artifacts import load_profile_source
from src.web.review import read_persona_review_fields, resolve_persona_review_source, summarize_redistill_character_change


def process_distill_character(
    *,
    character: str,
    locked_characters: list[str],
    novel_path: Path,
    characters_root: Path,
    manifest_path: Path,
    payload_dir: Path,
    host_output_root: Path,
    run_dir: Path,
    novel_id: str,
    parts: Any,
    config: Any,
    max_sentences: int,
    max_chars: int,
    on_distill: Callable[[str, dict[str, Any]], None],
    assert_run_not_stopped: Callable[..., None],
    write_json: Callable[[Path, dict[str, Any]], None],
    update_manifest: Callable[[Path, Callable[[dict[str, Any]], dict[str, Any] | None]], dict[str, Any]],
    generate_character_profile_markdown: Callable[..., tuple[str, dict[str, Any]]],
    maybe_repair_generated_profile: Callable[..., str | None],
    finalize_generated_profile_source: Callable[..., None],
    materialize_profile_source: Callable[[Path, Path], dict[str, Any]],
    update_manifest_chunk_progress: Callable[..., None],
    build_quality_snapshot: Callable[..., dict[str, Any]],
    utc_now: Callable[[], str],
    stage_presence: Callable[[dict[str, Any] | None], list[str]],
    relation_repairs_getter: Callable[[dict[str, Any]], dict[str, Any]],
    aggregates: dict[str, Any],
) -> None:
    previous_review_fields: dict[str, str] = {}
    persona_dir = run_dir / "artifacts" / "characters" / novel_id / safe_filename(character)
    if persona_dir.exists():
        try:
            _, _, previous_source_path = resolve_persona_review_source(persona_dir)
            if previous_source_path.exists():
                previous_review_fields = read_persona_review_fields(load_profile_source(previous_source_path))
        except Exception:
            previous_review_fields = {}

    assert_run_not_stopped(manifest_path, current_character=character)
    on_distill("drafting_character", {"character": character})
    character_payload = build_distill_prompt_payload(
        novel_path,
        characters=[character],
        max_sentences=max_sentences,
        max_chars=max_chars,
        characters_root=characters_root,
        manifest_path=manifest_path,
        update_mode="auto",
    )
    payload_path = payload_dir / f"distill_{safe_filename(character)}.json"
    write_json(payload_path, character_payload)
    aggregates["distill_payload_paths"][character] = str(payload_path.resolve())

    excerpt_focus = dict(character_payload.get("request", {}).get("excerpt_focus", {}) or {})
    stage_presence_values = stage_presence(character_payload.get("request", {}).get("excerpt_stages", {}))
    matched = character in excerpt_focus.get("matched_characters", [])
    missing = character in excerpt_focus.get("missing_characters", [])
    if matched:
        aggregates["quality_matched"].add(character)
    if missing:
        aggregates["quality_missing"].add(character)
    aggregates["quality_stage_presence"].update(stage_presence_values)

    assert_run_not_stopped(manifest_path, current_character=character)
    content, chunk_meta = generate_character_profile_markdown(
        parts=parts,
        config=config,
        manifest_path=manifest_path,
        payload=character_payload,
        character=character,
        peer_characters=locked_characters,
        progress_hook=on_distill,
    )
    aggregates["quality_focus"][character] = {
        "matched": matched,
        "missing": missing,
        "stage_presence": stage_presence_values,
        "chunk_count": int(chunk_meta.get("chunk_count", 1) or 1),
        "chunked": bool(chunk_meta.get("chunked", False)),
    }
    aggregates["distill_chunk_by_character"][character] = {
        "chunk_count": int(chunk_meta.get("chunk_count", 1) or 1),
        "chunked": bool(chunk_meta.get("chunked", False)),
    }
    if not content.strip():
        raise ValueError(f"{character} 的人物档案生成为空。")

    host_output_dir = host_output_root / safe_filename(character)
    host_output_dir.mkdir(parents=True, exist_ok=True)
    source_path = host_output_dir / "PROFILE.generated.md"
    source_path.write_text(content.strip() + "\n", encoding="utf-8")

    assert_run_not_stopped(manifest_path, current_character=character)
    repaired_text = maybe_repair_generated_profile(
        parts=parts,
        config=config,
        payload=character_payload,
        character=character,
        peer_characters=locked_characters,
        source_path=source_path,
    )
    if repaired_text is not None:
        source_path.write_text(repaired_text.strip() + "\n", encoding="utf-8")
        if character not in aggregates["profile_repair_characters"]:
            aggregates["profile_repair_characters"].append(character)

    finalize_generated_profile_source(
        source_path,
        payload=character_payload,
        chunk_count=int(chunk_meta.get("chunk_count", 1) or 1),
    )

    assert_run_not_stopped(manifest_path, current_character=character)
    on_distill("materializing_character", {"character": character})
    current_review_fields = read_persona_review_fields(load_profile_source(source_path))
    change_summary = summarize_redistill_character_change(
        character=character,
        previous_fields=previous_review_fields,
        next_fields=current_review_fields,
    )
    materialized = materialize_profile_source(
        source_path,
        run_dir / "artifacts" / "characters" / novel_id / safe_filename(character),
    )
    aggregates["character_dirs"][materialized["character"]] = materialized["persona_dir"]

    distill_total_chunks = sum(
        int(item.get("chunk_count", 1) or 1) for item in aggregates["distill_chunk_by_character"].values()
    )
    distill_any_chunked = any(bool(item.get("chunked", False)) for item in aggregates["distill_chunk_by_character"].values())

    def _update_distill_manifest(current: dict[str, Any]) -> dict[str, Any]:
        current.setdefault("artifacts", {}).setdefault("character_dirs", {}).update(aggregates["character_dirs"])
        current.setdefault("artifacts", {}).setdefault("payloads", {})["distill_characters"] = aggregates[
            "distill_payload_paths"
        ]
        update_manifest_chunk_progress(
            current,
            capability="distill",
            mode="chunked" if distill_any_chunked else "single",
            chunk_count=distill_total_chunks,
            current_chunk=distill_total_chunks if distill_any_chunked else 0,
            current_label="人物蒸馏完成" if distill_any_chunked else "",
            status="complete",
            merge_required=distill_any_chunked,
            merge_status="complete" if distill_any_chunked else "pending",
            extras={"by_character": aggregates["distill_chunk_by_character"]},
        )
        current.setdefault("capabilities", {})["materialize"] = {
            "status": "running",
            "success": False,
            "updated_at": utc_now(),
            "message": f"{character} persona bundle materialized",
        }
        current["quality"] = build_quality_snapshot(
            matched_characters=list(aggregates["quality_matched"]),
            missing_characters=list(aggregates["quality_missing"]),
            strategy="character_windows",
            excerpt_stages={
                "start": "yes" if "前段" in aggregates["quality_stage_presence"] else "",
                "mid": "yes" if "中段" in aggregates["quality_stage_presence"] else "",
                "end": "yes" if "后段" in aggregates["quality_stage_presence"] else "",
            },
            character_focus=aggregates["quality_focus"],
            profile_repairs={
                "count": len(aggregates["profile_repair_characters"]),
                "characters": aggregates["profile_repair_characters"],
            },
            relation_repairs=relation_repairs_getter(current),
        )
        current["updated_at"] = utc_now()
        if change_summary is not None:
            change_summary["timestamp"] = current["updated_at"]
            redistill_state = current.setdefault("redistill", {})
            recent_changes = list(redistill_state.get("recent_changes", []) or [])
            recent_changes = [
                item for item in recent_changes if str(item.get("character", "")).strip() != materialized["character"]
            ]
            recent_changes.insert(0, change_summary)
            redistill_state["recent_changes"] = recent_changes[:6]
            current.setdefault("events", []).append(
                {
                    "stage": "redistill_character_updated",
                    "status": "running",
                    "message": str(change_summary.get("summary", "")).strip() or f"{materialized['character']} 已完成增量补稳",
                    "character": materialized["character"],
                    "capability": "distill",
                    "timestamp": current["updated_at"],
                    "changed_fields": list(change_summary.get("changed_fields", []) or []),
                }
            )
        return current

    update_manifest(manifest_path, _update_distill_manifest)
    on_distill("character_done", {"character": materialized["character"]})


def process_relation_graph(
    *,
    novel_path: Path,
    graph_cast: list[str],
    max_sentences: int,
    max_chars: int,
    manifest_path: Path,
    payload_dir: Path,
    novel_id: str,
    parts: Any,
    config: Any,
    on_relation: Callable[[str, dict[str, Any]], None],
    assert_run_not_stopped: Callable[..., None],
    write_json: Callable[[Path, dict[str, Any]], None],
    update_manifest: Callable[[Path, Callable[[dict[str, Any]], dict[str, Any] | None]], dict[str, Any]],
    build_quality_snapshot: Callable[..., dict[str, Any]],
    update_manifest_chunk_progress: Callable[..., None],
    generate_relation_markdown: Callable[..., tuple[str, dict[str, Any]]],
    maybe_repair_generated_relations: Callable[..., str | None],
    load_relations_source: Callable[[Path], dict[str, Any]],
    export_relations_source: Callable[..., dict[str, Any]],
    utc_now: Callable[[], str],
    relation_repairs_getter: Callable[[dict[str, Any]], dict[str, Any]],
    quality_matched: set[str],
    quality_missing: set[str],
    quality_focus: dict[str, Any],
    profile_repair_characters: list[str],
) -> None:
    assert_run_not_stopped(manifest_path, message="这次蒸馏已停止。")
    relation_payload = build_relation_prompt_payload(
        novel_path,
        max_sentences=min(max_sentences, 80),
        max_chars=min(max_chars, 12_000),
        characters=graph_cast,
    )
    relation_payload_path = payload_dir / "relation_payload.auto.json"
    write_json(relation_payload_path, relation_payload)

    def _update_relation_prepare_manifest(current: dict[str, Any]) -> dict[str, Any]:
        current.setdefault("artifacts", {}).setdefault("payloads", {})["relation"] = str(relation_payload_path.resolve())
        update_manifest_chunk_progress(
            current,
            capability="relation",
            mode=str(relation_payload.get("request", {}).get("chunk_mode", "single")).strip() or "single",
            chunk_count=int(relation_payload.get("meta", {}).get("chunk_count", 0) or 0),
            current_chunk=0,
            current_label="",
            status="pending",
            merge_required=bool(relation_payload.get("meta", {}).get("merge_required", False)),
            merge_status="pending",
        )
        current["quality"] = build_quality_snapshot(
            matched_characters=list(quality_matched),
            missing_characters=list(quality_missing),
            strategy=str(relation_payload.get("request", {}).get("excerpt_focus", {}).get("strategy", "character_windows")),
            excerpt_stages=relation_payload.get("request", {}).get("excerpt_stages", {}),
            character_focus=quality_focus,
            profile_repairs={"count": len(profile_repair_characters), "characters": profile_repair_characters},
            relation_repairs=relation_repairs_getter(current),
        )
        current["updated_at"] = utc_now()
        return current

    update_manifest(manifest_path, _update_relation_prepare_manifest)

    assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
    on_relation("rendering_graph", {})
    assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
    relation_markdown, relation_chunk_meta = generate_relation_markdown(
        parts=parts,
        config=config,
        manifest_path=manifest_path,
        payload=relation_payload,
        characters=graph_cast,
        progress_hook=on_relation,
    )
    if not relation_markdown.strip():
        raise ValueError("人物关系图谱结果为空。")

    relations_file = parts.path_provider.relations_file(novel_id)
    relations_file.parent.mkdir(parents=True, exist_ok=True)
    relations_file.write_text(relation_markdown.strip() + "\n", encoding="utf-8")
    repaired_relations = maybe_repair_generated_relations(
        parts=parts,
        config=config,
        payload=relation_payload,
        characters=graph_cast,
        relations_file=relations_file,
        relation_markdown=relation_markdown,
    )
    relation_repair_pairs: list[str] = []
    if repaired_relations is not None:
        relations_file.write_text(repaired_relations.strip() + "\n", encoding="utf-8")
        try:
            repaired_payload = load_relations_source(relations_file)
            relation_repair_pairs = [
                str(key).strip()
                for key in dict(repaired_payload.get("relations", {}) or {}).keys()
                if str(key).strip()
            ]
        except Exception:
            relation_repair_pairs = []

    assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续落盘。")
    graph_payload = export_relations_source(relations_file, novel_id=novel_id, manifest_path=manifest_path)

    def _update_relation_complete_manifest(current: dict[str, Any]) -> dict[str, Any]:
        current.setdefault("artifacts", {})["relation_graph"] = dict(graph_payload)
        update_manifest_chunk_progress(
            current,
            capability="relation",
            mode="chunked" if bool(relation_chunk_meta.get("chunked", False)) else "single",
            chunk_count=int(relation_chunk_meta.get("chunk_count", 1) or 1),
            current_chunk=int(relation_chunk_meta.get("chunk_count", 1) or 1)
            if bool(relation_chunk_meta.get("chunked", False))
            else 0,
            current_label="关系图谱完成" if bool(relation_chunk_meta.get("chunked", False)) else "",
            status="complete",
            merge_required=bool(relation_chunk_meta.get("chunked", False)),
            merge_status="complete" if bool(relation_chunk_meta.get("chunked", False)) else "pending",
        )
        current["quality"] = build_quality_snapshot(
            matched_characters=list(quality_matched),
            missing_characters=list(quality_missing),
            strategy=str(relation_payload.get("request", {}).get("excerpt_focus", {}).get("strategy", "character_windows")),
            excerpt_stages=relation_payload.get("request", {}).get("excerpt_stages", {}),
            character_focus=quality_focus,
            profile_repairs={"count": len(profile_repair_characters), "characters": profile_repair_characters},
            relation_repairs={
                "count": 1 if repaired_relations is not None else 0,
                "pairs": relation_repair_pairs,
                "chunked": bool(relation_chunk_meta.get("chunked", False)),
                "chunk_count": int(relation_chunk_meta.get("chunk_count", 1) or 1),
            },
        )
        current["updated_at"] = utc_now()
        return current

    update_manifest(manifest_path, _update_relation_complete_manifest)
    on_relation("graph_done", {})
