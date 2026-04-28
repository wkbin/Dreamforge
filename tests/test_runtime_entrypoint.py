#!/usr/bin/env python3

import subprocess
import sys
import unittest
from pathlib import Path


class RuntimeEntrypointTests(unittest.TestCase):
    def test_runtime_cli_help_smoke(self):
        runtime_cli = Path("clawhub-zaomeng-skill/runtime/zaomeng_cli.py")
        result = subprocess.run(
            [sys.executable, str(runtime_cli), "--help"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("zaomeng", result.stdout)
        self.assertIn("distill", result.stdout)
        self.assertIn("chat", result.stdout)


if __name__ == "__main__":
    unittest.main()
