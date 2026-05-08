#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

_PACKAGE_PREFIX = f"{__package__}." if __package__ else ""
_skill_metadata = importlib.import_module(f"{_PACKAGE_PREFIX}skill_metadata")


def sync_skill_version(skill_dir: Path, version: str) -> None:
    version = str(version).strip()
    if not version:
        raise ValueError("Version cannot be empty")

    frontmatter = _skill_metadata.read_skill_frontmatter(skill_dir)
    metadata_block = frontmatter.get("metadata", {}) or {}
    if not isinstance(metadata_block, dict):
        raise ValueError("SKILL.md frontmatter metadata must be a mapping")
    metadata_block["version"] = version
    frontmatter["metadata"] = metadata_block
    _skill_metadata.write_skill_frontmatter(skill_dir, frontmatter)

    metadata_path = skill_dir / ".metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["semver"] = version
        metadata["version"] = version
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prompts_path = skill_dir / "examples" / "test-prompts.json"
    prompts_payload = json.loads(prompts_path.read_text(encoding="utf-8"))
    prompts_payload["version"] = version
    prompts_path.write_text(json.dumps(prompts_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync the skill version across SKILL.md metadata and example assets.")
    parser.add_argument("--version", required=True, help="Target skill version.")
    parser.add_argument("--skill-dir", default="zaomeng-skill", help="Skill directory relative to the repo root.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = (repo_root / args.skill_dir).resolve()
    if not skill_dir.exists():
        raise FileNotFoundError(f"Missing skill directory: {skill_dir}")

    sync_skill_version(skill_dir, args.version)
    print(f"Synchronized skill version to {args.version} in {skill_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
