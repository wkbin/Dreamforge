from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def coerce_manifest_path(value: Any) -> Path | None:
    if isinstance(value, Path):
        candidate = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        candidate = Path(text)
    else:
        return None
    try:
        if not candidate.exists():
            return None
    except (OSError, ValueError):
        return None
    return candidate


def relative_to_run_dir(path: Path, run_dir: Path) -> Path | None:
    for candidate_path, candidate_run_dir in relative_candidates(path, run_dir):
        try:
            return candidate_path.relative_to(candidate_run_dir)
        except ValueError:
            continue

    path_parts = normalized_parts(path)
    run_parts = normalized_parts(run_dir)
    if len(path_parts) < len(run_parts) or path_parts[: len(run_parts)] != run_parts:
        return None

    actual_path = Path(path).resolve(strict=False)
    actual_parts = actual_path.parts
    if len(actual_parts) < len(run_parts):
        return None
    relative_parts = actual_parts[len(run_parts) :]
    return Path(*relative_parts) if relative_parts else Path()


def rewrite_run_root_paths(value: Any, *, source_root: Path, target_root: Path) -> Any:
    if isinstance(value, dict):
        return {key: rewrite_run_root_paths(item, source_root=source_root, target_root=target_root) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_run_root_paths(item, source_root=source_root, target_root=target_root) for item in value]
    if isinstance(value, str):
        return rewrite_string_path(value, source_root=source_root, target_root=target_root)
    return value


def rewrite_string_path(text: str, *, source_root: Path, target_root: Path) -> str:
    raw = str(text or "")
    candidates = {
        str(source_root),
        str(source_root).replace("\\", "/"),
        str(source_root).replace("/", "\\"),
    }
    for candidate in sorted(candidates, key=len, reverse=True):
        if candidate and raw.startswith(candidate):
            suffix = raw[len(candidate) :].lstrip("\\/")
            if not suffix:
                return str(target_root)
            return str(target_root / Path(*suffix.replace("\\", "/").split("/")))
    return raw


def relative_candidates(path: Path, run_dir: Path) -> list[tuple[Path, Path]]:
    path_obj = Path(path)
    run_dir_obj = Path(run_dir)
    pairs = [
        (path_obj, run_dir_obj),
        (path_obj.resolve(strict=False), run_dir_obj.resolve(strict=False)),
        (Path(os.path.realpath(os.fspath(path_obj))), Path(os.path.realpath(os.fspath(run_dir_obj)))),
    ]
    ordered: list[tuple[Path, Path]] = []
    seen: set[tuple[str, str]] = set()
    for candidate_path, candidate_run_dir in pairs:
        key = (os.fspath(candidate_path), os.fspath(candidate_run_dir))
        if key in seen:
            continue
        seen.add(key)
        ordered.append((candidate_path, candidate_run_dir))
    return ordered


def normalized_parts(path: Path) -> tuple[str, ...]:
    resolved = Path(path).resolve(strict=False)
    return tuple(part.casefold() for part in resolved.parts)
