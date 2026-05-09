from __future__ import annotations

import re
import unittest
from pathlib import Path


class RuntimeRequirementsTests(unittest.TestCase):
    def test_runtime_requirements_do_not_force_epub_stack(self):
        repo_root = Path(__file__).resolve().parents[1]
        requirements = (repo_root / "requirements.runtime.txt").read_text(encoding="utf-8")

        self.assertIsNone(re.search(r"(?im)^\s*ebooklib(?:\[.*\])?\s*(?:[<>=!~].*)?$", requirements))
        self.assertIn("Optional input support", requirements)


if __name__ == "__main__":
    unittest.main()
