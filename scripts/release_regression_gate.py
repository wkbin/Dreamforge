#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_PLATFORMS = ("windows", "wsl", "linux", "termux")
REQUIRED_CHECKS = ("install", "update", "run", "import_export")
ALLOWED_STATUS = {"pass", "fail", "pending"}


def load_signoff(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("signoff payload must be a JSON object")
    return payload


def evaluate_signoff(payload: dict, *, expected_release_tag: str = "") -> list[str]:
    errors: list[str] = []
    release_tag = str(payload.get("release_tag", "")).strip()
    checked_at = str(payload.get("checked_at", "")).strip()
    checked_by = payload.get("checked_by")
    platforms = payload.get("platforms")

    if not release_tag:
        errors.append("missing release_tag")
    if expected_release_tag and release_tag != expected_release_tag:
        errors.append(f"release_tag mismatch: expected {expected_release_tag}, got {release_tag or '<empty>'}")
    if not checked_at:
        errors.append("missing checked_at")
    if not isinstance(checked_by, list) or not [item for item in checked_by if str(item).strip()]:
        errors.append("checked_by must contain at least one reviewer")
    if not isinstance(platforms, dict):
        errors.append("platforms must be an object")
        return errors

    for platform in REQUIRED_PLATFORMS:
        checks = platforms.get(platform)
        if not isinstance(checks, dict):
            errors.append(f"platform '{platform}' is missing")
            continue
        for check in REQUIRED_CHECKS:
            value = str(checks.get(check, "")).strip().lower()
            if value not in ALLOWED_STATUS:
                errors.append(f"{platform}.{check} must be one of {sorted(ALLOWED_STATUS)}")
                continue
            if value != "pass":
                errors.append(f"{platform}.{check} is '{value}', expected 'pass'")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate cross-platform release regression signoff.")
    parser.add_argument(
        "--signoff",
        default="docs/release-regression-signoff.json",
        help="Path to release signoff JSON relative to repo root.",
    )
    parser.add_argument(
        "--release-tag",
        default="",
        help="Optional expected release tag, for example v2026.05.16.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    signoff_path = (repo_root / args.signoff).resolve()
    if not signoff_path.exists():
        raise FileNotFoundError(f"missing signoff file: {signoff_path}")

    payload = load_signoff(signoff_path)
    errors = evaluate_signoff(payload, expected_release_tag=str(args.release_tag or "").strip())
    if errors:
        print("[fail] release regression gate is not signed off:")
        for item in errors:
            print(f"- {item}")
        return 1

    print(f"[done] release regression gate passed: {signoff_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
