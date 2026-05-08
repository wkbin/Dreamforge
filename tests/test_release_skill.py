#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.release_skill import release_skill


class ReleaseSkillScriptTests(unittest.TestCase):
    def test_release_skill_packages_archive_from_metadata_version_without_checks(self):
        repo_root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            skill_dir = tmp_root / "zaomeng-skill"
            output_dir = tmp_root / "dist"
            (skill_dir / "examples").mkdir(parents=True, exist_ok=True)

            (skill_dir / ".metadata.json").write_text(
                json.dumps({"name": "zaomeng-skill", "version": "7.7.7"}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: zaomeng-skill\n"
                "description: test skill\n"
                "license: MIT-0\n"
                "metadata:\n"
                "  version: 7.7.7\n"
                "---\n"
                "skill\n",
                encoding="utf-8",
            )
            (skill_dir / "README.md").write_text("readme\n", encoding="utf-8")
            (skill_dir / "README_EN.md").write_text("readme en\n", encoding="utf-8")
            (skill_dir / "PUBLISH.md").write_text("- Version: 7.7.7\n", encoding="utf-8")
            (skill_dir / "MANIFEST.md").write_text("manifest\n", encoding="utf-8")
            (skill_dir / "INSTALL.md").write_text("install\n", encoding="utf-8")
            (skill_dir / "requirements.txt").write_text("PyYAML>=6.0,<7.0\n", encoding="utf-8")
            (skill_dir / "examples" / "test-prompts.json").write_text(
                json.dumps({"version": "7.7.7", "cases": []}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            archive_path = release_skill(
                repo_root,
                skill_dir=skill_dir,
                output_dir=output_dir,
                skip_checks=True,
            )

            self.assertEqual(archive_path.name, "zaomeng-7.7.7.skill.zip")
            self.assertTrue(archive_path.exists())

            with ZipFile(archive_path) as zf:
                names = set(zf.namelist())

            self.assertIn("zaomeng-skill/.metadata.json", names)
            self.assertIn("zaomeng-skill/SKILL.md", names)
            self.assertIn("zaomeng-skill/README.md", names)
            self.assertIn("zaomeng-skill/PUBLISH.md", names)


if __name__ == "__main__":
    unittest.main()
