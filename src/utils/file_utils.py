#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

NOISE_NAME_SUFFIXES = {"说", "道", "笑", "听", "问", "看", "想", "叫", "喊", "答", "哭"}
CANONICAL_NAME_ALIASES = {
    "关公": "关羽",
    "云长": "关羽",
    "玄德": "刘备",
    "翼德": "张飞",
    "孔明": "诸葛亮",
    "卧龙": "诸葛亮",
    "孟德": "曹操",
}
CANONICAL_TO_ALIASES: dict[str, list[str]] = {}
for alias_name, canonical_name in CANONICAL_NAME_ALIASES.items():
    CANONICAL_TO_ALIASES.setdefault(canonical_name, []).append(alias_name)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {_sanitize_json_value(key): _sanitize_json_value(item) for key, item in value.items()}
    return value

def load_markdown_data(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    text = p.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return default
    parts = text.split("---", 2)
    if len(parts) < 3:
        return default
    payload = yaml.safe_load(parts[1]) or {}
    return payload


def save_markdown_data(
    path: str | Path,
    data: Dict[str, Any],
    *,
    title: str = "DATA",
    summary: Optional[list[str]] = None,
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    sanitized = _sanitize_json_value(data)
    frontmatter = yaml.safe_dump(sanitized, allow_unicode=True, sort_keys=False).strip()
    body_lines = [f"# {title}", ""]
    if summary:
        body_lines.extend(summary)
        body_lines.append("")
    content = f"---\n{frontmatter}\n---\n\n" + "\n".join(body_lines).rstrip() + "\n"
    p.write_text(content, encoding="utf-8")


def safe_filename(name: str) -> str:
    clean = re.sub(r"[\\/:*?\"<>|]", "_", name).strip()
    return clean or "unnamed"


def normalize_character_name(name: str) -> str:
    clean = str(name or "").strip()
    if len(clean) >= 3 and clean[-1] in NOISE_NAME_SUFFIXES:
        clean = clean[:-1]
    return CANONICAL_NAME_ALIASES.get(clean, clean)


def canonical_aliases(name: str) -> list[str]:
    canonical = normalize_character_name(name)
    aliases = CANONICAL_TO_ALIASES.get(canonical, [])
    return [alias for alias in aliases if alias != canonical]


def normalize_relation_key(key: str) -> str:
    parts = [normalize_character_name(part) for part in str(key).split("_") if part]
    if len(parts) != 2:
        return str(key)
    return "_".join(sorted(parts))


def novel_id_from_input(novel: str) -> str:
    raw = Path(novel).stem if Path(novel).suffix else Path(novel).name
    if not raw:
        raw = novel
    return safe_filename(raw)


def find_character_file(
    base_dir: str | Path,
    character_name: str,
    novel_id: Optional[str] = None,
) -> list[Path]:
    root = Path(base_dir)
    normalized = normalize_character_name(character_name)
    candidate_names = [character_name]
    if normalized != character_name:
        candidate_names.append(normalized)
    dirnames = [safe_filename(name) for name in candidate_names]

    if novel_id:
        matches = [root / novel_id / dirname / "PROFILE.md" for dirname in dirnames]
        return [path for path in matches if path.exists()]

    matches = []
    for dirname in dirnames:
        matches.extend(root.glob(f"{dirname}/PROFILE.md"))
        matches.extend(root.glob(f"*/{dirname}/PROFILE.md"))
    return sorted({path.resolve() for path in matches})
