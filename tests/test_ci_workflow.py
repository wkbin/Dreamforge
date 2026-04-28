#!/usr/bin/env python3

import unittest
from pathlib import Path


class CIWorkflowTests(unittest.TestCase):
    def test_workflow_runs_dev_checks_on_linux_and_windows(self):
        workflow_text = Path(".github/workflows/tests.yml").read_text(encoding="utf-8")
        self.assertIn("ubuntu-latest", workflow_text)
        self.assertIn("windows-latest", workflow_text)
        self.assertIn("python scripts/dev_checks.py", workflow_text)

    def test_dev_checks_exposes_smoke_mode_and_guardrail_suite(self):
        script_text = Path("scripts/dev_checks.py").read_text(encoding="utf-8")
        self.assertIn("--smoke-only", script_text)
        self.assertIn("tests.test_runtime_mirror", script_text)
        self.assertIn("tests.test_runtime_entrypoint", script_text)
        self.assertIn("tests.test_runtime_wrappers", script_text)
        self.assertIn("tests.test_packaging_docs", script_text)


if __name__ == "__main__":
    unittest.main()
