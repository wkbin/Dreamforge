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
        self.assertIn("--release-tag", script_text)
        self.assertIn("tests.test_cli_structure", script_text)
        self.assertIn("tests.test_package_skill_script", script_text)
        self.assertIn("tests.test_release_skill", script_text)
        self.assertIn("tests.test_skill_version_sync", script_text)
        self.assertIn("tests.test_install_skill", script_text)
        self.assertIn("tests.test_novel_preparation", script_text)
        self.assertIn("tests.test_prompt_payloads", script_text)
        self.assertIn("tests.test_packaging_docs", script_text)
        self.assertIn('"run mypy"', script_text)
        self.assertIn('"mypy.ini"', script_text)
        self.assertIn('"run release regression gate"', script_text)
        self.assertIn('scripts/release_regression_gate.py', script_text)

    def test_mypy_config_targets_guardrail_modules(self):
        config_text = Path("mypy.ini").read_text(encoding="utf-8")
        self.assertIn("tests/test_packaging_docs.py", config_text)
        self.assertIn("tests/test_ci_workflow.py", config_text)
        self.assertIn("tests/test_package_skill_script.py", config_text)
        self.assertIn("tests/test_release_skill.py", config_text)
        self.assertIn("tests/test_skill_version_sync.py", config_text)
        self.assertIn("scripts/package_skill.py", config_text)
        self.assertIn("scripts/release_skill.py", config_text)
        self.assertIn("scripts/skill_metadata.py", config_text)
        self.assertIn("scripts/sync_skill_version.py", config_text)
        self.assertIn("src/core/contracts.py", config_text)


if __name__ == "__main__":
    unittest.main()
