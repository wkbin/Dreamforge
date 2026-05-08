#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.skill_metadata import read_skill_version


class PackageSkillScriptTests(unittest.TestCase):
    def test_package_skill_archive_uses_versioned_filename_and_expected_entries(self):
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "package_skill.py"
        version = read_skill_version(repo_root / "zaomeng-skill")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dist"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--output-dir",
                    str(output_dir),
                    "--no-bump-web-assets",
                ],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )

            archive_path = output_dir / f"zaomeng-{version}.skill.zip"
            self.assertTrue(archive_path.exists())
            self.assertIn("Web static asset version:", result.stdout)

            with ZipFile(archive_path) as zf:
                names = set(zf.namelist())

            self.assertIn("SKILL.md", names)
            self.assertIn("README.md", names)
            self.assertIn("PUBLISH.md", names)
            self.assertIn("requirements.txt", names)
            self.assertIn("assets/vendor/mermaid-11.14.0.min.js", names)
            self.assertIn("tools/prepare_novel_excerpt.py", names)
            self.assertIn("tools/build_prompt_payload.py", names)
            self.assertIn("tools/export_relation_graph.py", names)
            self.assertIn("tools/_skill_support/novel_preparation.py", names)
            self.assertIn("prompts/distill_prompt.md", names)
            self.assertIn("references/output_schema.md", names)
            self.assertIn("examples/sample_character_profile.md", names)
            self.assertIn("examples/chat_session_summary.example.json", names)
            self.assertIn("examples/chat_result_single_turn.example.json", names)
            self.assertIn("examples/chat_status_complete.example.json", names)
            self.assertIn("examples/host_workflow_example.md", names)
            self.assertTrue(all(not name.startswith("zaomeng-skill/") for name in names))

    def test_package_skill_archive_skips_cache_directories(self):
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "package_skill.py"
        version = read_skill_version(repo_root / "zaomeng-skill")
        cache_file = repo_root / "zaomeng-skill" / "tools" / "__pycache__" / "temp.pyc"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"cache")
        self.addCleanup(lambda: cache_file.unlink(missing_ok=True))

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dist"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--output-dir",
                    str(output_dir),
                    "--no-bump-web-assets",
                ],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )

            archive_path = output_dir / f"zaomeng-{version}.skill.zip"
            self.assertIn("Web static asset version:", result.stdout)
            with ZipFile(archive_path) as zf:
                names = set(zf.namelist())

            self.assertNotIn("tools/__pycache__/temp.pyc", names)


if __name__ == "__main__":
    unittest.main()
