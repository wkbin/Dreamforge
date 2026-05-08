#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


def _split_skill_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    content = str(text or "")
    if not content.startswith("---\n"):
        raise ValueError("SKILL.md is missing YAML frontmatter")

    marker = "\n---\n"
    end = content.find(marker, 4)
    if end == -1:
        raise ValueError("SKILL.md frontmatter is not terminated with ---")

    frontmatter_text = content[4:end]
    body = content[end + len(marker) :]
    payload = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(payload, dict):
        raise ValueError("SKILL.md frontmatter must decode to a mapping")
    return payload, body


def read_skill_frontmatter(skill_dir: Path) -> dict[str, Any]:
    skill_path = skill_dir / "SKILL.md"
    payload, _ = _split_skill_frontmatter(skill_path.read_text(encoding="utf-8"))
    return payload


def write_skill_frontmatter(skill_dir: Path, payload: dict[str, Any]) -> None:
    skill_path = skill_dir / "SKILL.md"
    _, body = _split_skill_frontmatter(skill_path.read_text(encoding="utf-8"))
    rendered = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).strip()
    skill_path.write_text(f"---\n{rendered}\n---\n{body}", encoding="utf-8")


def read_skill_version(skill_dir: Path) -> str:
    frontmatter = read_skill_frontmatter(skill_dir)
    metadata = frontmatter.get("metadata", {}) or {}
    if not isinstance(metadata, dict):
        raise ValueError("SKILL.md frontmatter metadata must be a mapping")

    version = str(metadata.get("version", "")).strip()
    if version:
        return version

    metadata_path = skill_dir / ".metadata.json"
    if metadata_path.exists():
        metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        version = str(metadata_payload.get("semver", "")).strip() or str(metadata_payload.get("version", "")).strip()
        if version:
            return version

    raise ValueError(f"Could not find skill version in {skill_dir / 'SKILL.md'}")
