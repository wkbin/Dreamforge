#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.skill_support.novel_preparation import build_excerpt_payload


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _skill_root() -> Path:
    return _repo_root() / "zaomeng-skill"


def _read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _dedupe_warnings(messages: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in messages:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _build_excerpt_focus_warnings(excerpt_focus: dict[str, Any]) -> list[str]:
    requested = [str(item).strip() for item in list(excerpt_focus.get("requested_characters", [])) if str(item).strip()]
    matched = [str(item).strip() for item in list(excerpt_focus.get("matched_characters", [])) if str(item).strip()]
    missing = [str(item).strip() for item in list(excerpt_focus.get("missing_characters", [])) if str(item).strip()]
    strategy = str(excerpt_focus.get("strategy", "")).strip()

    warnings: list[str] = []
    if requested and not matched:
        warnings.append("未匹配到任何目标角色，excerpt 已回退为开头片段；请检查角色名写法、简繁体或异体字。")
    elif missing:
        warnings.append(f"部分目标角色未匹配到：{'、'.join(missing)}。")
    if strategy == "character_windows_mixed":
        warnings.append("目标角色命中较稀疏，excerpt 已混入时间线/对话补充句来补足上下文。")
    return _dedupe_warnings(warnings)


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

    excerpt_focus = {
        "requested_characters": excerpt_payload["requested_characters"],
        "matched_characters": excerpt_payload["matched_characters"],
        "missing_characters": excerpt_payload["missing_characters"],
        "strategy": excerpt_payload["excerpt_strategy"],
    }
    return {
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
            "excerpt_focus": excerpt_focus,
            "update_mode": resolved_update_mode,
            "existing_profiles": existing_profiles,
        },
        "meta": {
            "novel_id": novel_id,
            "source_path": excerpt_payload["source_path"],
            "max_sentences": max_sentences,
            "max_chars": max_chars,
            "characters_root": str(characters_root_path) if characters_root_path else "",
            "existing_profile_paths": existing_profile_paths,
            "existing_character_count": len(existing_profiles),
            "warnings": _build_excerpt_focus_warnings(excerpt_focus),
        },
    }


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
    excerpt_focus = {
        "requested_characters": excerpt_payload["requested_characters"],
        "matched_characters": excerpt_payload["matched_characters"],
        "missing_characters": excerpt_payload["missing_characters"],
        "strategy": excerpt_payload["excerpt_strategy"],
    }
    return {
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
            "excerpt_focus": excerpt_focus,
        },
        "meta": {
            "source_path": excerpt_payload["source_path"],
            "max_sentences": max_sentences,
            "max_chars": max_chars,
            "warnings": _build_excerpt_focus_warnings(excerpt_focus),
        },
    }


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
        profile = _load_existing_persona_bundle(persona_dir)
        if not profile:
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
        return manifest_file.parent / "data" / "characters" / novel_id

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


def _load_existing_persona_bundle(persona_dir: Path) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for path in _ordered_persona_paths(persona_dir):
        if not path.exists():
            continue
        current = _parse_markdown_profile(path.read_text(encoding="utf-8"))
        raw = _merge_profile_data(raw, current)
    return raw


def _ordered_persona_paths(persona_dir: Path) -> list[Path]:
    base_names = [
        "PROFILE",
        "SOUL",
        "GOALS",
        "STYLE",
        "TRAUMA",
        "IDENTITY",
        "BACKGROUND",
        "CAPABILITY",
        "BONDS",
        "CONFLICTS",
        "ROLE",
        "AGENTS",
        "RELATIONS",
        "MEMORY",
    ]
    paths: list[Path] = []
    for base_name in base_names:
        paths.append(persona_dir / f"{base_name}.generated.md")
        paths.append(persona_dir / f"{base_name}.md")
    return paths


def _parse_markdown_profile(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        key_text = key.strip()
        value_text = value.strip()
        if not key_text:
            continue
        parsed[key_text] = _coerce_value(value_text)
    return parsed


def _coerce_value(value: str) -> Any:
    text = str(value or "").strip()
    if not text:
        return ""
    if "=" in text and "；" in text:
        metric_map: dict[str, Any] = {}
        for part in re.split(r"\s*[；]\s*", text):
            if "=" not in part:
                continue
            key, raw_value = part.split("=", 1)
            key_text = key.strip()
            if not key_text:
                continue
            metric_map[key_text] = _coerce_scalar(raw_value.strip())
        if metric_map:
            return metric_map
    if "；" in text:
        return [item.strip() for item in re.split(r"\s*[；]\s*", text) if item.strip()]
    return _coerce_scalar(text)


def _coerce_scalar(value: str) -> Any:
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    return text


def _merge_profile_data(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    if not base:
        return dict(incoming)
    merged = dict(base)
    for key, value in incoming.items():
        if isinstance(value, list):
            existing = merged.get(key, [])
            if not isinstance(existing, list):
                existing = [existing] if existing else []
            merged[key] = _merge_unique(existing, value)
        elif isinstance(value, dict):
            existing = merged.get(key, {})
            if not isinstance(existing, dict):
                existing = {}
            merged[key] = {**existing, **value}
        elif value not in ("", None):
            merged[key] = value
    return merged


def _merge_unique(base: list[Any], incoming: list[Any]) -> list[Any]:
    merged: list[Any] = []
    seen = set()
    for item in [*base, *incoming]:
        text = str(item).strip()
        if not text or text in seen:
            continue
        merged.append(text)
        seen.add(text)
    return merged

