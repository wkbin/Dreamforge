#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SkillVersionSyncTests(unittest.TestCase):
    def test_sync_skill_version_updates_metadata_and_examples(self):
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "sync_skill_version.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            skill_dir = tmp_root / "zaomeng-skill"
            (skill_dir / "examples").mkdir(parents=True, exist_ok=True)

            (skill_dir / ".metadata.json").write_text(
                json.dumps(
                    {"name": "zaomeng-skill", "assetType": "skill", "semver": "1.0.0", "version": "1.0.0"},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: zaomeng-skill\n"
                "description: test skill\n"
                "license: MIT-0\n"
                "metadata:\n"
                "  version: 1.0.0\n"
                "---\n"
                "skill body\n",
                encoding="utf-8",
            )
            (skill_dir / "README.md").write_text("| 版本 | `1.0.0` |\n", encoding="utf-8")
            (skill_dir / "README_EN.md").write_text("| Version | `1.0.0` |\n", encoding="utf-8")
            (skill_dir / "PUBLISH.md").write_text("## 版本说明\n", encoding="utf-8")
            (skill_dir / "examples" / "test-prompts.json").write_text(
                json.dumps({"version": "1.0.0", "cases": []}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--skill-dir",
                    str(skill_dir),
                    "--version",
                    "9.9.9",
                ],
                cwd=repo_root,
                check=True,
                capture_output=True,
            )

            metadata = json.loads((skill_dir / ".metadata.json").read_text(encoding="utf-8"))
            skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            prompts_payload = json.loads((skill_dir / "examples" / "test-prompts.json").read_text(encoding="utf-8"))

            self.assertEqual(metadata["semver"], "9.9.9")
            self.assertEqual(metadata["version"], "9.9.9")
            self.assertIn("version: 9.9.9", skill_text)
            self.assertIn("`1.0.0`", (skill_dir / "README.md").read_text(encoding="utf-8"))
            self.assertIn("`1.0.0`", (skill_dir / "README_EN.md").read_text(encoding="utf-8"))
            self.assertNotIn("- Version: 9.9.9", (skill_dir / "PUBLISH.md").read_text(encoding="utf-8"))
            self.assertEqual(prompts_payload["version"], "9.9.9")


if __name__ == "__main__":
    unittest.main()
