#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def sync_skill_version(skill_dir: Path, version: str) -> None:
    version = str(version).strip()
    if not version:
        raise ValueError("Version cannot be empty")

    metadata_path = skill_dir / ".metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["semver"] = version
    metadata["version"] = version
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prompts_path = skill_dir / "examples" / "test-prompts.json"
    prompts_payload = json.loads(prompts_path.read_text(encoding="utf-8"))
    prompts_payload["version"] = version
    prompts_path.write_text(json.dumps(prompts_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync the skill version across metadata, docs, and example assets.")
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
