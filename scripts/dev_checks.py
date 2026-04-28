#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_TEST_MODULES = [
    "tests.test_runtime_mirror",
    "tests.test_runtime_entrypoint",
    "tests.test_runtime_wrappers",
    "tests.test_packaging_docs",
]


def run_step(title: str, command: list[str]) -> None:
    print(f"[step] {title}")
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local development checks.")
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Run mirror checks and fast guardrail tests without the full test suite.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_step("sync runtime mirror", [sys.executable, "scripts/sync_runtime_mirror.py"])
    run_step("check runtime mirror", [sys.executable, "scripts/check_runtime_mirror.py"])
    run_step("run smoke guardrails", [sys.executable, "-m", "unittest", *SMOKE_TEST_MODULES])
    if args.smoke_only:
        print("[done] smoke checks passed")
        return 0

    run_step("run unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    print("[done] development checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
