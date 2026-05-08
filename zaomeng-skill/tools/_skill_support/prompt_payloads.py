#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .novel_preparation import build_excerpt_payload, split_sentences
from .persona_bundle import load_existing_persona_bundle

DISTILL_CHUNK_TRIGGER_CHARS = 18_000
DISTILL_CHUNK_TRIGGER_SENTENCES = 180
DISTILL_CHUNK_MAX_CHARS = 9_000
DISTILL_CHUNK_MAX_SENTENCES = 70
RELATION_CHUNK_TRIGGER_CHARS = 9_000
RELATION_CHUNK_TRIGGER_SENTENCES = 110
RELATION_CHUNK_MAX_CHARS = 4_800
RELATION_CHUNK_MAX_SENTENCES = 36


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def build_distill_prompt_payload(
    novel_path: str | Path,
    *,
    characters: list[str] | None = None,
    max_sentences: int = 120,
    max_chars: int = 50_000,
    characters_root: str | Path | None = None,
    manifest_path: str | Path | None = None,
    update_mode: str = "auto",
) -> dict[str, object]:
    skill_root = _skill_root()
    excerpt_payload = build_excerpt_payload(
        novel_path,
        characters=characters,
        max_sentences=max_sentences,
        max_chars=max_chars,
    )
    requested_characters = [str(item).strip() for item in list(characters or []) if str(item).strip()]
    novel_id = Path(novel_path).stem.strip()
    existing_profiles, existing_profile_paths, characters_root_path = _collect_existing_profiles(
        novel_path,
        novel_id=novel_id,
        characters=requested_characters,
        characters_root=characters_root,
        manifest_path=manifest_path,
    )
    resolved_update_mode = _resolve_update_mode(update_mode, existing_profiles)

    payload = {
        "mode": "distill",
        "prompt": _read_utf8(skill_root / "prompts" / "distill_prompt.md"),
        "references": {
            "output_schema": _read_utf8(skill_root / "references" / "output_schema.md"),
            "style_differ": _read_utf8(skill_root / "references" / "style_differ.md"),
            "logic_constraint": _read_utf8(skill_root / "references" / "logic_constraint.md"),
            "validation_policy": _read_utf8(skill_root / "references" / "validation_policy.md"),
        },
        "request": {
            "characters": requested_characters,
            "excerpt": excerpt_payload["excerpt"],
            "excerpt_stages": excerpt_payload["excerpt_stages"],
            "source_name": excerpt_payload["source_name"],
            "excerpt_focus": {
                "requested_characters": excerpt_payload["requested_characters"],
                "matched_characters": excerpt_payload["matched_characters"],
                "missing_characters": excerpt_payload["missing_characters"],
                "strategy": excerpt_payload["excerpt_strategy"],
            },
            "update_mode": resolved_update_mode,
            "existing_profiles": existing_profiles,
            "chunk_mode": "single",
        },
        "meta": {
            "novel_id": novel_id,
            "source_path": excerpt_payload["source_path"],
            "max_sentences": max_sentences,
            "max_chars": max_chars,
            "characters_root": str(characters_root_path) if characters_root_path else "",
            "existing_profile_paths": existing_profile_paths,
            "existing_character_count": len(existing_profiles),
        },
    }
    return _attach_distill_chunk_bundle(payload)


def build_relation_prompt_payload(
    novel_path: str | Path,
    *,
    max_sentences: int = 80,
    max_chars: int = 12_000,
    characters: list[str] | None = None,
) -> dict[str, object]:
    skill_root = _skill_root()
    excerpt_payload = build_excerpt_payload(
        novel_path,
        max_sentences=max_sentences,
        max_chars=max_chars,
        characters=characters,
    )
    payload = {
        "mode": "relation",
        "prompt": _read_utf8(skill_root / "prompts" / "relation_prompt.md"),
        "references": {
            "output_schema": _read_utf8(skill_root / "references" / "output_schema.md"),
            "logic_constraint": _read_utf8(skill_root / "references" / "logic_constraint.md"),
            "validation_policy": _read_utf8(skill_root / "references" / "validation_policy.md"),
        },
        "request": {
            "excerpt": excerpt_payload["excerpt"],
            "excerpt_stages": excerpt_payload["excerpt_stages"],
            "source_name": excerpt_payload["source_name"],
            "characters": excerpt_payload["requested_characters"],
            "excerpt_focus": {
                "requested_characters": excerpt_payload["requested_characters"],
                "matched_characters": excerpt_payload["matched_characters"],
                "missing_characters": excerpt_payload["missing_characters"],
                "strategy": excerpt_payload["excerpt_strategy"],
            },
            "chunk_mode": "single",
        },
        "meta": {
            "source_path": excerpt_payload["source_path"],
            "max_sentences": max_sentences,
            "max_chars": max_chars,
        },
    }
    return _attach_relation_chunk_bundle(payload)


def _attach_distill_chunk_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    request = dict(payload.get("request", {}) or {})
    excerpt = str(request.get("excerpt", "")).strip()
    if not _should_use_chunking(
        excerpt,
        trigger_chars=DISTILL_CHUNK_TRIGGER_CHARS,
        trigger_sentences=DISTILL_CHUNK_TRIGGER_SENTENCES,
    ):
        payload["chunks"] = []
        payload["merge_payload"] = {}
        payload["host_plan"] = _build_host_plan(
            chunk_mode="single",
            merge_mode="none",
            chunk_entries=[],
        )
        payload["meta"] = {
            **dict(payload.get("meta", {}) or {}),
            "chunked": False,
            "chunk_count": 0,
            "merge_required": False,
        }
        return payload

    chunk_entries = _build_distill_chunk_payloads(payload)
    payload["request"] = {
        **request,
        "chunk_mode": "chunked",
    }
    payload["chunks"] = chunk_entries
    payload["merge_payload"] = _build_distill_merge_payload_template(payload, chunk_entries)
    payload["host_plan"] = _build_host_plan(
        chunk_mode="chunked",
        merge_mode="merge_profiles",
        chunk_entries=chunk_entries,
    )
    payload["meta"] = {
        **dict(payload.get("meta", {}) or {}),
        "chunked": True,
        "chunk_count": len(chunk_entries),
        "merge_required": True,
    }
    return payload


def _attach_relation_chunk_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    request = dict(payload.get("request", {}) or {})
    excerpt = str(request.get("excerpt", "")).strip()
    if not _should_use_chunking(
        excerpt,
        trigger_chars=RELATION_CHUNK_TRIGGER_CHARS,
        trigger_sentences=RELATION_CHUNK_TRIGGER_SENTENCES,
    ):
        payload["chunks"] = []
        payload["merge_payload"] = {}
        payload["host_plan"] = _build_host_plan(
            chunk_mode="single",
            merge_mode="none",
            chunk_entries=[],
        )
        payload["meta"] = {
            **dict(payload.get("meta", {}) or {}),
            "chunked": False,
            "chunk_count": 0,
            "merge_required": False,
        }
        return payload

    chunk_entries = _build_relation_chunk_payloads(payload)
    payload["request"] = {
        **request,
        "chunk_mode": "chunked",
    }
    payload["chunks"] = chunk_entries
    payload["merge_payload"] = _build_relation_merge_payload_template(payload, chunk_entries)
    payload["host_plan"] = _build_host_plan(
        chunk_mode="chunked",
        merge_mode="merge_relations",
        chunk_entries=chunk_entries,
    )
    payload["meta"] = {
        **dict(payload.get("meta", {}) or {}),
        "chunked": True,
        "chunk_count": len(chunk_entries),
        "merge_required": True,
    }
    return payload


def _build_host_plan(*, chunk_mode: str, merge_mode: str, chunk_entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "execution": "sequential_chunks_then_merge" if chunk_entries else "single_pass",
        "chunk_mode": chunk_mode,
        "merge_mode": merge_mode,
        "chunk_count": len(chunk_entries),
        "chunk_labels": [str(item.get("label", "")).strip() for item in chunk_entries],
        "success_marker": "Provide final merged artifact only after chunk merge is complete." if chunk_entries else "Single payload result is final.",
    }


def _build_distill_chunk_payloads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    request = dict(payload.get("request", {}) or {})
    excerpt = str(request.get("excerpt", "")).strip()
    excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
    chunk_entries: list[dict[str, Any]] = []
    for stage_key, stage_label in (("start", "前段"), ("mid", "中段"), ("end", "后段")):
        stage_text = str(excerpt_stages.get(stage_key, "")).strip()
        if not stage_text:
            continue
        stage_chunks = _chunk_text(
            stage_text,
            max_chars=DISTILL_CHUNK_MAX_CHARS,
            max_sentences=DISTILL_CHUNK_MAX_SENTENCES,
        )
        for index, chunk_text in enumerate(stage_chunks, start=1):
            chunk_request = dict(request)
            chunk_request["excerpt"] = chunk_text
            chunk_request["excerpt_stages"] = {"start": "", "mid": "", "end": ""}
            chunk_request["excerpt_stages"][stage_key] = chunk_text
            chunk_request["excerpt_focus"] = {
                **dict(request.get("excerpt_focus", {}) or {}),
                "strategy": "chunked_character_windows",
            }
            chunk_request["chunk_mode"] = "partial"
            chunk_request["chunk_guidance"] = _build_chunk_distill_guidance(
                chunk_label=f"{stage_label}-{index}" if len(stage_chunks) > 1 else stage_label,
                chunk_index=index,
                chunk_total=len(stage_chunks),
            )
            chunk_meta = dict(payload.get("meta", {}) or {})
            chunk_meta["chunk_stage"] = stage_key
            chunk_meta["chunk_index"] = index
            chunk_meta["chunk_total"] = len(stage_chunks)
            chunk_entries.append(
                {
                    "id": f"distill_{stage_key}_{index:02d}",
                    "label": f"{stage_label}-{index}" if len(stage_chunks) > 1 else stage_label,
                    "payload": {
                        **payload,
                        "request": chunk_request,
                        "meta": chunk_meta,
                    },
                }
            )
    if chunk_entries:
        return chunk_entries

    excerpt_chunks = _chunk_text(
        excerpt,
        max_chars=DISTILL_CHUNK_MAX_CHARS,
        max_sentences=DISTILL_CHUNK_MAX_SENTENCES,
    )
    return [
        {
            "id": f"distill_chunk_{index:02d}",
            "label": f"证据块-{index}",
            "payload": {
                **payload,
                "request": {
                    **request,
                    "excerpt": chunk_text,
                    "excerpt_stages": {"start": "", "mid": "", "end": ""},
                    "chunk_mode": "partial",
                    "chunk_guidance": _build_chunk_distill_guidance(
                        chunk_label=f"证据块-{index}",
                        chunk_index=index,
                        chunk_total=len(excerpt_chunks),
                    ),
                },
                "meta": {
                    **dict(payload.get("meta", {}) or {}),
                    "chunk_index": index,
                    "chunk_total": len(excerpt_chunks),
                },
            },
        }
        for index, chunk_text in enumerate(excerpt_chunks, start=1)
    ]


def _build_relation_chunk_payloads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    request = dict(payload.get("request", {}) or {})
    excerpt = str(request.get("excerpt", "")).strip()
    excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
    chunk_entries: list[dict[str, Any]] = []
    for stage_key, stage_label in (("start", "前段"), ("mid", "中段"), ("end", "后段")):
        stage_text = str(excerpt_stages.get(stage_key, "")).strip()
        if not stage_text:
            continue
        stage_chunks = _chunk_text(
            stage_text,
            max_chars=RELATION_CHUNK_MAX_CHARS,
            max_sentences=RELATION_CHUNK_MAX_SENTENCES,
        )
        for index, chunk_text in enumerate(stage_chunks, start=1):
            chunk_request = dict(request)
            chunk_request["excerpt"] = chunk_text
            chunk_request["excerpt_stages"] = {"start": "", "mid": "", "end": ""}
            chunk_request["excerpt_stages"][stage_key] = chunk_text
            chunk_request["excerpt_focus"] = {
                **dict(request.get("excerpt_focus", {}) or {}),
                "strategy": "chunked_relation_windows",
            }
            chunk_request["chunk_mode"] = "partial"
            chunk_request["chunk_guidance"] = _build_relation_chunk_guidance(
                chunk_label=f"{stage_label}-{index}" if len(stage_chunks) > 1 else stage_label,
                chunk_index=index,
                chunk_total=len(stage_chunks),
            )
            chunk_entries.append(
                {
                    "id": f"relation_{stage_key}_{index:02d}",
                    "label": f"{stage_label}-{index}" if len(stage_chunks) > 1 else stage_label,
                    "payload": {
                        **payload,
                        "request": chunk_request,
                        "meta": {
                            **dict(payload.get("meta", {}) or {}),
                            "chunk_stage": stage_key,
                            "chunk_index": index,
                            "chunk_total": len(stage_chunks),
                        },
                    },
                }
            )
    if chunk_entries:
        return chunk_entries

    excerpt_chunks = _chunk_text(
        excerpt,
        max_chars=RELATION_CHUNK_MAX_CHARS,
        max_sentences=RELATION_CHUNK_MAX_SENTENCES,
    )
    return [
        {
            "id": f"relation_chunk_{index:02d}",
            "label": f"关系块-{index}",
            "payload": {
                **payload,
                "request": {
                    **request,
                    "excerpt": chunk_text,
                    "excerpt_stages": {"start": "", "mid": "", "end": ""},
                    "chunk_mode": "partial",
                    "chunk_guidance": _build_relation_chunk_guidance(
                        chunk_label=f"关系块-{index}",
                        chunk_index=index,
                        chunk_total=len(excerpt_chunks),
                    ),
                },
                "meta": {
                    **dict(payload.get("meta", {}) or {}),
                    "chunk_index": index,
                    "chunk_total": len(excerpt_chunks),
                },
            },
        }
        for index, chunk_text in enumerate(excerpt_chunks, start=1)
    ]


def _build_distill_merge_payload_template(payload: dict[str, Any], chunk_entries: list[dict[str, Any]]) -> dict[str, Any]:
    request = dict(payload.get("request", {}) or {})
    return {
        "mode": "distill_merge",
        "prompt": _build_distill_merge_prompt(),
        "references": dict(payload.get("references", {}) or {}),
        "request": {
            "characters": list(request.get("characters", [])),
            "source_name": str(request.get("source_name", "")).strip(),
            "update_mode": str(request.get("update_mode", "")).strip(),
            "existing_profiles": dict(request.get("existing_profiles", {}) or {}),
            "chunk_drafts": [],
            "expected_chunk_labels": [str(item.get("label", "")).strip() for item in chunk_entries],
            "merge_guidance": (
                "请把多个局部 PROFILE.generated.md 草稿合并成最终 PROFILE.generated.md。"
                "优先保留跨块一致、长期稳定、与已有增量档案兼容的人格字段；"
                "如果字段仅由单个局部桥段支撑，宁可写“证据不足”，不要把剧情碎句直接抄成稳定人格。"
            ),
        },
        "meta": {
            **dict(payload.get("meta", {}) or {}),
            "merge_required": True,
            "chunk_count": len(chunk_entries),
        },
    }


def _build_relation_merge_payload_template(payload: dict[str, Any], chunk_entries: list[dict[str, Any]]) -> dict[str, Any]:
    request = dict(payload.get("request", {}) or {})
    return {
        "mode": "relation_merge",
        "prompt": _build_relation_merge_prompt(),
        "references": dict(payload.get("references", {}) or {}),
        "request": {
            "source_name": str(request.get("source_name", "")).strip(),
            "characters": list(request.get("characters", [])),
            "chunk_drafts": [],
            "expected_chunk_labels": [str(item.get("label", "")).strip() for item in chunk_entries],
            "merge_guidance": (
                "请把多个局部 RELATION_GRAPH 草稿合并成最终关系图。"
                "只保留有明确证据支撑的人物关系，不要因为某些角色在局部块里没有出现，就删除他们在其他块里已成立的关系。"
            ),
        },
        "meta": {
            **dict(payload.get("meta", {}) or {}),
            "merge_required": True,
            "chunk_count": len(chunk_entries),
        },
    }


def _build_distill_merge_prompt() -> str:
    return "\n".join(
        [
            "你现在要做的是多块人物蒸馏草稿的合并，不是再次重写小说。",
            "输入会给出多个 PROFILE.generated.md 局部草稿。",
            "请把它们合并成一个最终的 PROFILE.generated.md。",
            "要求：",
            "1. 只保留稳定、长期、可复用的人格信息。",
            "2. 冲突字段优先采用跨块重复出现或更符合全局弧线的一方。",
            "3. 不要把剧情原句、临时桥段、旁枝角色的台词误写进目标角色字段。",
            "4. 如证据不够，允许写“证据不足”，不要虚构。",
            "5. 输出必须仍然是完整的 PROFILE.generated.md 结构化 Markdown。",
        ]
    ).strip()


def _build_relation_merge_prompt() -> str:
    return "\n".join(
        [
            "你现在要做的是多块关系抽取草稿的合并。",
            "输入会给出多个 RELATION_GRAPH 局部草稿。",
            "请把它们合并成一个最终关系图 Markdown。",
            "要求：",
            "1. 只保留有证据支撑的关系。",
            "2. 如果同一对人物在不同块里有不同判断，优先保留更稳定、更可解释的版本。",
            "3. 不要因为某块缺席就抹掉其他块里已成立的关系。",
            "4. 输出必须仍然是完整 RELATION_GRAPH Markdown。",
        ]
    ).strip()


def _should_use_chunking(excerpt: str, *, trigger_chars: int, trigger_sentences: int) -> bool:
    clean = str(excerpt or "").strip()
    if not clean:
        return False
    sentence_count = len(split_sentences(clean))
    return len(clean) > trigger_chars or sentence_count > trigger_sentences


def _chunk_text(text: str, *, max_chars: int, max_sentences: int) -> list[str]:
    clean = str(text or "").strip()
    if not clean:
        return []
    sentences = [item.strip() for item in split_sentences(clean) if item.strip()]
    if not sentences:
        sentences = [item.strip() for item in clean.splitlines() if item.strip()] or [clean]
    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0
    for sentence in sentences:
        units = [sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars)] or [sentence]
        for unit in units:
            item = unit.strip()
            if not item:
                continue
            projected = current_chars + len(item) + (1 if current else 0)
            if current and (len(current) >= max_sentences or projected > max_chars):
                chunks.append("\n".join(current).strip())
                current = []
                current_chars = 0
            current.append(item)
            current_chars += len(item) + (1 if len(current) > 1 else 0)
    if current:
        chunks.append("\n".join(current).strip())
    return [item for item in chunks if item]


def _build_chunk_distill_guidance(*, chunk_label: str = "", chunk_index: int = 0, chunk_total: int = 0) -> str:
    if not chunk_total:
        return ""
    lines = [
        "## CHUNK_MODE",
        f"- 当前是证据块 {chunk_index}/{chunk_total}：{chunk_label or '未命名证据块'}",
        "- 这是分批蒸馏中的局部草稿，请尽量完整，但允许写“证据不足”。",
        "- 不要因为当前块缺少信息，就虚构角色稳定特征。",
        "- 输出仍然必须是 PROFILE.generated.md 格式，但这是局部草案，后续还会汇总。",
    ]
    return "\n".join(lines).strip()


def _build_relation_chunk_guidance(*, chunk_label: str = "", chunk_index: int = 0, chunk_total: int = 0) -> str:
    if not chunk_total:
        return ""
    lines = [
        "## CHUNK_MODE",
        f"- 当前是关系证据块 {chunk_index}/{chunk_total}：{chunk_label or '未命名关系块'}",
        "- 这是分批关系抽取中的局部草稿，请只保留当前证据块里能站得住的关系。",
        "- 不要为了凑完整图谱而硬补没有证据的人物关系。",
        "- 输出仍然必须是完整 RELATION_GRAPH Markdown，但这是局部草案，后续还会汇总。",
    ]
    return "\n".join(lines).strip()


def _collect_existing_profiles(
    novel_path: str | Path,
    *,
    novel_id: str,
    characters: list[str],
    characters_root: str | Path | None,
    manifest_path: str | Path | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, str], Path | None]:
    root = _resolve_characters_root(novel_path, novel_id=novel_id, characters_root=characters_root, manifest_path=manifest_path)
    if root is None:
        return {}, {}, None

    existing_profiles: dict[str, dict[str, Any]] = {}
    existing_profile_paths: dict[str, str] = {}
    for name in characters:
        persona_dir = root / name
        if not persona_dir.exists():
            continue
        try:
            profile = load_existing_persona_bundle(persona_dir)
        except FileNotFoundError:
            continue
        existing_profiles[name] = profile
        existing_profile_paths[name] = str(persona_dir.resolve())
    return existing_profiles, existing_profile_paths, root


def _resolve_characters_root(
    novel_path: str | Path,
    *,
    novel_id: str,
    characters_root: str | Path | None,
    manifest_path: str | Path | None,
) -> Path | None:
    explicit = _normalize_characters_root(characters_root, novel_id) if characters_root else None
    if explicit and explicit.exists():
        return explicit

    manifest_candidate = _characters_root_from_manifest(manifest_path, novel_id)
    if manifest_candidate and manifest_candidate.exists():
        return manifest_candidate

    novel_parent_candidate = Path(novel_path).resolve().parent / "data" / "characters" / novel_id
    if novel_parent_candidate.exists():
        return novel_parent_candidate

    cwd_candidate = Path.cwd() / "data" / "characters" / novel_id
    if cwd_candidate.exists():
        return cwd_candidate
    return explicit


def _normalize_characters_root(value: str | Path, novel_id: str) -> Path:
    root = Path(value).resolve()
    nested = root / novel_id
    if root.name != novel_id and nested.exists():
        return nested
    return root


def _characters_root_from_manifest(manifest_path: str | Path | None, novel_id: str) -> Path | None:
    if not manifest_path:
        return None
    manifest_file = Path(manifest_path).resolve()
    if not manifest_file.exists():
        candidate = manifest_file.parent / "data" / "characters" / novel_id
        return candidate

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    character_dirs = payload.get("artifacts", {}).get("character_dirs", {})
    if isinstance(character_dirs, dict) and character_dirs:
        first_dir = next(iter(character_dirs.values()), "")
        if first_dir:
            return Path(first_dir).resolve().parent
    return manifest_file.parent / "data" / "characters" / novel_id


def _resolve_update_mode(update_mode: str, existing_profiles: dict[str, dict[str, Any]]) -> str:
    mode = str(update_mode or "auto").strip().lower()
    if mode == "auto":
        return "incremental" if existing_profiles else "create"
    if mode == "incremental":
        return "incremental"
    return "create"
