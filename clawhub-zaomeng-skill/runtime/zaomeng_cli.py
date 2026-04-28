#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parent
PROJECT_SRC_ROOT = RUNTIME_ROOT.parent.parent / "src"

os.chdir(RUNTIME_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

preferred_roots = []
if PROJECT_SRC_ROOT.exists():
    preferred_roots.append(PROJECT_SRC_ROOT.parent)
preferred_roots.append(RUNTIME_ROOT)

for root in reversed(preferred_roots):
    root_text = str(root)
    if root_text in sys.path:
        sys.path.remove(root_text)
    sys.path.insert(0, root_text)

from src.core.main import main


if __name__ == "__main__":
    main()
