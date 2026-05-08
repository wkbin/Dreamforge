#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


def read_skill_version(skill_dir: Path) -> str:
    metadata_path = skill_dir / ".metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    version = str(metadata.get("semver", "")).strip() or str(metadata.get("version", "")).strip()
    if not version:
        raise ValueError(f"Could not find skill version in {metadata_path}")
    return version
