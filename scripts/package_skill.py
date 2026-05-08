#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

_PACKAGE_PREFIX = f"{__package__}." if __package__ else ""
_install_skill = importlib.import_module(f"{_PACKAGE_PREFIX}install_skill")
_skill_metadata = importlib.import_module(f"{_PACKAGE_PREFIX}skill_metadata")
_web_asset_version = importlib.import_module(f"{_PACKAGE_PREFIX}web_asset_version")
_IGNORED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache"}


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part in _IGNORED_DIR_NAMES for part in path.parts):
            yield path


def build_archive(
    skill_dir: Path,
    output_dir: Path,
    *,
    version: str,
    package_name: str = "zaomeng",
    archive_root: str = "",
) -> Path:
    archive_name = f"{package_name}-{version}.skill.zip"
    archive_path = output_dir / archive_name
    output_dir.mkdir(parents=True, exist_ok=True)

    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as zf:
        for entry_name in _install_skill.iter_skill_entries():
            source = skill_dir / entry_name
            if not source.exists():
                continue

            if source.is_dir():
                for file_path in iter_files(source):
                    relative = file_path.relative_to(skill_dir)
                    archive_relative = relative if not archive_root else Path(archive_root) / relative
                    zf.write(file_path, archive_relative)
            else:
                archive_relative = Path(entry_name) if not archive_root else Path(archive_root) / entry_name
                zf.write(source, archive_relative)

    return archive_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package zaomeng-skill into a versioned .skill.zip archive."
    )
    parser.add_argument(
        "--skill-dir",
        default="zaomeng-skill",
        help="Skill source directory relative to the repo root.",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Directory where the packaged .skill.zip archive will be written.",
    )
    parser.add_argument(
        "--version",
        help="Optional version override. Defaults to metadata.version in SKILL.md.",
    )
    parser.add_argument(
        "--package-name",
        default="zaomeng",
        help="Archive filename prefix. Default: zaomeng",
    )
    parser.add_argument(
        "--archive-root",
        default="",
        help="Optional top-level folder name inside the zip archive. Default: pack skill files at archive root",
    )
    parser.add_argument(
        "--no-bump-web-assets",
        action="store_true",
        help="Skip refreshing the web static asset version before packaging.",
    )
    parser.add_argument(
        "--static-version",
        default="",
        help="Optional explicit web static asset version. Implies bumping web assets before packaging.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = (repo_root / args.skill_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()

    if not skill_dir.exists():
        raise FileNotFoundError(f"Missing skill directory: {skill_dir}")

    if args.static_version:
        _web_asset_version.sync_web_asset_version(repo_root, args.static_version)
    elif not args.no_bump_web_assets:
        _web_asset_version.bump_web_asset_version(repo_root)

    resolved_static_version = _web_asset_version.read_web_asset_version(repo_root)
    version = args.version or _skill_metadata.read_skill_version(skill_dir)
    archive_path = build_archive(
        skill_dir,
        output_dir,
        version=version,
        package_name=args.package_name,
        archive_root=args.archive_root,
    )
    print(f"Web static asset version: {resolved_static_version}")
    print(f"Packaged skill archive: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
