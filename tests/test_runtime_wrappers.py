#!/usr/bin/env python3

import unittest
from pathlib import Path


class RuntimeWrapperTests(unittest.TestCase):
    def test_root_wrappers_delegate_to_shared_modules(self):
        expectations = {
            Path("src/core/main.py"): "from src.core.cli_app import ChatIntent, ZaomengCLI as _SharedZaomengCLI",
            Path("src/core/runtime_factory.py"): "from src.core.runtime_parts import RuntimeParts, build_runtime_parts",
            Path("src/core/logging_utils.py"): "from src.core.logging_setup import setup_logging",
        }
        for path, needle in expectations.items():
            text = path.read_text(encoding="utf-8")
            self.assertIn(needle, text, msg=f"Expected shared delegation in {path}")
            self.assertLessEqual(len(text.splitlines()), 40, msg=f"Wrapper grew too large: {path}")

    def test_runtime_wrappers_delegate_to_shared_modules(self):
        expectations = {
            Path("clawhub-zaomeng-skill/runtime/src/core/main.py"): "from src.core.cli_app import ChatIntent, ZaomengCLI as _SharedZaomengCLI",
            Path("clawhub-zaomeng-skill/runtime/src/core/runtime_factory.py"): "from src.core.runtime_parts import RuntimeParts, build_runtime_parts",
            Path("clawhub-zaomeng-skill/runtime/src/core/logging_utils.py"): "from src.core.logging_setup import setup_logging",
        }
        for path, needle in expectations.items():
            text = path.read_text(encoding="utf-8")
            self.assertIn(needle, text, msg=f"Expected shared delegation in {path}")
            self.assertLessEqual(len(text.splitlines()), 40, msg=f"Wrapper grew too large: {path}")


if __name__ == "__main__":
    unittest.main()
