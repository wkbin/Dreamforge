#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
RUNTIME_ROOT = PROJECT_ROOT / "clawhub-zaomeng-skill" / "runtime" / "src"
MANIFEST_PATH = PROJECT_ROOT / ".runtime-mirror.json"


@dataclass
class MirrorReport:
    missing_in_runtime: List[str]
    missing_in_source: List[str]
    content_mismatches: List[str]

    def is_clean(self) -> bool:
        return not (self.missing_in_runtime or self.missing_in_source or self.content_mismatches)


@dataclass
class MirrorSyncResult:
    copied: List[str]
    removed: List[str]

    def changed(self) -> bool:
        return bool(self.copied or self.removed)


def load_manifest_patterns(manifest_path: Path = MANIFEST_PATH) -> List[str]:
    payload = load_manifest(manifest_path)
    patterns = payload.get("include", [])
    return _normalized_manifest_entries(patterns)


def load_runtime_owned_patterns(manifest_path: Path = MANIFEST_PATH) -> List[str]:
    payload = load_manifest(manifest_path)
    patterns = payload.get("runtime_owned", [])
    return _normalized_manifest_entries(patterns)


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> Dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Runtime mirror manifest must be a JSON object.")
    return payload


def validate_manifest(manifest_path: Path = MANIFEST_PATH) -> List[str]:
    include = load_manifest_patterns(manifest_path)
    runtime_owned = load_runtime_owned_patterns(manifest_path)
    errors: List[str] = []

    if not include:
        errors.append("Manifest must include at least one mirrored file.")
    if any("*" in entry for entry in [*include, *runtime_owned]):
        errors.append("Manifest entries must be explicit file paths without wildcards.")

    include_set = set(include)
    runtime_owned_set = set(runtime_owned)
    overlap = sorted(include_set & runtime_owned_set)
    if overlap:
        errors.append(f"Manifest entries overlap between include and runtime_owned: {', '.join(overlap)}")

    invalid_entries = sorted(
        entry
        for entry in [*include, *runtime_owned]
        if not entry.endswith(".py") and entry != "__init__.py"
    )
    if invalid_entries:
        errors.append(f"Manifest entries must point to Python files: {', '.join(invalid_entries)}")

    return errors


def _normalized_manifest_entries(entries: Any) -> List[str]:
    if not isinstance(entries, list):
        return []
    return [str(pattern).strip() for pattern in entries if str(pattern).strip()]


def _manifest_python_files(root: Path, patterns: Sequence[str]) -> Dict[str, Path]:
    files: Dict[str, Path] = {}
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or path.suffix != ".py":
                continue
            files[path.relative_to(root).as_posix()] = path
    return files


def _normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def build_report(
    source_root: Path = SOURCE_ROOT,
    runtime_root: Path = RUNTIME_ROOT,
    patterns: Sequence[str] | None = None,
) -> MirrorReport:
    patterns = list(patterns or load_manifest_patterns())
    source_files = _manifest_python_files(source_root, patterns)
    runtime_files = _manifest_python_files(runtime_root, patterns)

    source_paths = set(source_files)
    runtime_paths = set(runtime_files)
    shared_paths = sorted(source_paths & runtime_paths)

    missing_in_runtime = sorted(source_paths - runtime_paths)
    missing_in_source = sorted(runtime_paths - source_paths)
    content_mismatches = [
        relative_path
        for relative_path in shared_paths
        if _normalized_text(source_files[relative_path]) != _normalized_text(runtime_files[relative_path])
    ]

    return MirrorReport(
        missing_in_runtime=missing_in_runtime,
        missing_in_source=missing_in_source,
        content_mismatches=content_mismatches,
    )


def sync_mirror(
    source_root: Path = SOURCE_ROOT,
    runtime_root: Path = RUNTIME_ROOT,
    patterns: Sequence[str] | None = None,
) -> MirrorSyncResult:
    source_root = source_root.resolve()
    runtime_root = runtime_root.resolve()
    patterns = list(patterns or load_manifest_patterns())
    source_files = _manifest_python_files(source_root, patterns)
    runtime_files = _manifest_python_files(runtime_root, patterns)

    copied: List[str] = []
    removed: List[str] = []

    for relative_path, source_path in sorted(source_files.items()):
        target_path = runtime_root / Path(relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source_text = _normalized_text(source_path)
        target_text = _normalized_text(target_path) if target_path.exists() else None
        if source_text == target_text:
            continue
        target_path.write_text(source_text, encoding="utf-8", newline="\n")
        copied.append(relative_path)

    for relative_path, runtime_path in sorted(runtime_files.items()):
        if relative_path in source_files:
            continue
        runtime_path.unlink()
        removed.append(relative_path)

    _prune_empty_dirs(runtime_root)
    return MirrorSyncResult(copied=copied, removed=removed)


def _format_lines(title: str, paths: Iterable[str]) -> List[str]:
    items = [f"  - {path}" for path in paths]
    return [title, *items]


def _prune_empty_dirs(root: Path) -> None:
    for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
        try:
            next(directory.iterdir())
        except StopIteration:
            directory.rmdir()


def main() -> int:
    manifest_errors = validate_manifest()
    if manifest_errors:
        print("Runtime mirror manifest is invalid.")
        for error_message in manifest_errors:
            print(f"  - {error_message}")
        return 1

    report = build_report()
    if report.is_clean():
        print("Runtime mirror is in sync with src.")
        return 0

    lines: List[str] = ["Runtime mirror drift detected."]
    if report.missing_in_runtime:
        lines.extend(_format_lines("Missing in runtime:", report.missing_in_runtime))
    if report.missing_in_source:
        lines.extend(_format_lines("Missing in src:", report.missing_in_source))
    if report.content_mismatches:
        lines.extend(_format_lines("Content mismatches:", report.content_mismatches))
    print("\n".join(lines))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
