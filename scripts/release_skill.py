#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from pathlib import Path


_PACKAGE_PREFIX = f"{__package__}." if __package__ else ""
_package_skill = importlib.import_module(f"{_PACKAGE_PREFIX}package_skill")
_skill_metadata = importlib.import_module(f"{_PACKAGE_PREFIX}skill_metadata")
_sync_skill_version = importlib.import_module(f"{_PACKAGE_PREFIX}sync_skill_version")
_web_asset_version = importlib.import_module(f"{_PACKAGE_PREFIX}web_asset_version")


def release_skill(
    repo_root: Path,
    *,
    skill_dir: Path,
    output_dir: Path,
    version: str = "",
    package_name: str = "zaomeng",
    archive_root: str = "zaomeng-skill",
    skip_checks: bool = False,
    smoke_only: bool = False,
    bump_web_assets: bool = False,
    static_version: str = "",
) -> Path:
    if version:
        _sync_skill_version.sync_skill_version(skill_dir, version)

    if static_version:
        _web_asset_version.sync_web_asset_version(repo_root, static_version)
    elif bump_web_assets:
        _web_asset_version.bump_web_asset_version(repo_root)

    resolved_version = _skill_metadata.read_skill_version(skill_dir)

    if not skip_checks:
        command = [sys.executable, str(repo_root / "scripts" / "dev_checks.py")]
        if smoke_only:
            command.append("--smoke-only")
        subprocess.run(command, cwd=repo_root, check=True)

    return _package_skill.build_archive(
        skill_dir,
        output_dir,
        version=resolved_version,
        package_name=package_name,
        archive_root=archive_root,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync version, run checks, and package zaomeng-skill in one step."
    )
    parser.add_argument("--skill-dir", default="zaomeng-skill", help="Skill source directory relative to the repo root.")
    parser.add_argument("--output-dir", default="dist", help="Directory where the packaged .skill.zip archive will be written.")
    parser.add_argument("--version", help="Optional version override. If provided, version sync runs first.")
    parser.add_argument("--package-name", default="zaomeng", help="Archive filename prefix. Default: zaomeng")
    parser.add_argument("--archive-root", default="zaomeng-skill", help="Top-level folder name inside the zip archive.")
    parser.add_argument("--skip-checks", action="store_true", help="Skip dev_checks before packaging.")
    parser.add_argument("--smoke-only", action="store_true", help="Run dev_checks in smoke-only mode before packaging.")
    parser.add_argument(
        "--no-bump-web-assets",
        action="store_true",
        help="Skip refreshing the web static asset version before release packaging.",
    )
    parser.add_argument(
        "--static-version",
        default="",
        help="Optional explicit web static asset version. Implies refreshing web assets before release packaging.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = (repo_root / args.skill_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()

    if not skill_dir.exists():
        raise FileNotFoundError(f"Missing skill directory: {skill_dir}")

    archive_path = release_skill(
        repo_root,
        skill_dir=skill_dir,
        output_dir=output_dir,
        version=str(args.version or "").strip(),
        package_name=args.package_name,
        archive_root=args.archive_root,
        skip_checks=bool(args.skip_checks),
        smoke_only=bool(args.smoke_only),
        bump_web_assets=not bool(args.no_bump_web_assets) and not bool(str(args.static_version or "").strip()),
        static_version=str(args.static_version or "").strip(),
    )
    resolved_static_version = _web_asset_version.read_web_asset_version(repo_root)
    print(f"Web static asset version: {resolved_static_version}")
    print(f"Released skill archive: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
