#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.check_runtime_mirror import sync_mirror, validate_manifest


def main() -> int:
    manifest_errors = validate_manifest()
    if manifest_errors:
        print("Runtime mirror manifest is invalid.")
        for error_message in manifest_errors:
            print(f"  - {error_message}")
        return 1

    result = sync_mirror()
    if not result.changed():
        print("Runtime mirror already up to date.")
        return 0

    if result.copied:
        print("Copied or updated:")
        for path in result.copied:
            print(f"  - {path}")
    if result.removed:
        print("Removed from runtime:")
        for path in result.removed:
            print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
