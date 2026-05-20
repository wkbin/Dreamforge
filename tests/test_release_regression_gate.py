#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.release_regression_gate import evaluate_signoff


class ReleaseRegressionGateTests(unittest.TestCase):
    def test_gate_accepts_all_pass_payload(self):
        payload = {
            "release_tag": "v2026.05.16",
            "checked_at": "2026-05-20",
            "checked_by": ["owner"],
            "platforms": {
                "windows": {"install": "pass", "update": "pass", "run": "pass", "import_export": "pass"},
                "wsl": {"install": "pass", "update": "pass", "run": "pass", "import_export": "pass"},
                "linux": {"install": "pass", "update": "pass", "run": "pass", "import_export": "pass"},
                "termux": {"install": "pass", "update": "pass", "run": "pass", "import_export": "pass"},
            },
        }
        errors = evaluate_signoff(payload, expected_release_tag="v2026.05.16")
        self.assertEqual(errors, [])

    def test_gate_rejects_pending_or_missing_fields(self):
        payload = {
            "release_tag": "",
            "checked_at": "",
            "checked_by": [],
            "platforms": {
                "windows": {"install": "pending", "update": "pass", "run": "pass", "import_export": "pass"},
                "wsl": {"install": "pass", "update": "pass", "run": "pass", "import_export": "pass"},
                "linux": {"install": "pass", "update": "pass", "run": "pass", "import_export": "pass"},
                "termux": {"install": "pass", "update": "pass", "run": "pass", "import_export": "pass"},
            },
        }
        errors = evaluate_signoff(payload, expected_release_tag="v2026.05.16")
        self.assertTrue(any("missing release_tag" in item for item in errors))
        self.assertTrue(any("missing checked_at" in item for item in errors))
        self.assertTrue(any("checked_by must contain" in item for item in errors))
        self.assertTrue(any("release_tag mismatch" in item for item in errors))
        self.assertTrue(any("windows.install is 'pending'" in item for item in errors))

    def test_signoff_template_exists(self):
        self.assertTrue(Path("docs/release-regression-signoff.json").exists())


if __name__ == "__main__":
    unittest.main()
