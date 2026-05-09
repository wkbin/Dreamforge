from __future__ import annotations

import re
import unittest
from pathlib import Path


class RuntimeRequirementsTests(unittest.TestCase):
    def test_runtime_requirements_do_not_force_epub_stack(self):
        repo_root = Path(__file__).resolve().parents[1]
        requirements = (repo_root / "requirements.runtime.txt").read_text(encoding="utf-8")

        self.assertIsNone(re.search(r"(?im)^\s*ebooklib(?:\[.*\])?\s*(?:[<>=!~].*)?$", requirements))
        self.assertIsNone(re.search(r"(?im)^\s*tiktoken(?:\[.*\])?\s*(?:[<>=!~].*)?$", requirements))
        self.assertIn("Optional input support", requirements)
        self.assertIn("Optional token tooling", requirements)
        self.assertRegex(requirements, r"(?im)^\s*fastapi>=0\.99\.0,<0\.100\.0\s*$")
        self.assertRegex(requirements, r"(?im)^\s*pydantic>=1\.10\.0,<2\.0\.0\s*$")


if __name__ == "__main__":
    unittest.main()
