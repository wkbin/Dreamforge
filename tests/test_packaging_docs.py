#!/usr/bin/env python3

import unittest
from pathlib import Path


class PackagingDocsTests(unittest.TestCase):
    def test_manifest_mentions_shared_runtime_core_modules(self):
        manifest_text = Path("clawhub-zaomeng-skill/MANIFEST.md").read_text(encoding="utf-8")
        for entry in (
            "runtime/src/core/cli_app.py",
            "runtime/src/core/runtime_parts.py",
            "runtime/src/core/logging_setup.py",
        ):
            self.assertIn(entry, manifest_text)

    def test_install_and_skill_docs_describe_wrapper_split(self):
        install_text = Path("clawhub-zaomeng-skill/INSTALL.md").read_text(encoding="utf-8")
        skill_text = Path("clawhub-zaomeng-skill/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("runtime/src/core/main.py", install_text)
        self.assertIn("runtime/src/core/runtime_parts.py", install_text)
        self.assertIn("runtime/src/core/logging_setup.py", skill_text)

    def test_readmes_describe_shared_and_wrapper_runtime_layers(self):
        root_readme_en = Path("README.en.md").read_text(encoding="utf-8")
        skill_readme = Path("clawhub-zaomeng-skill/README.md").read_text(encoding="utf-8")
        skill_readme_en = Path("clawhub-zaomeng-skill/README_EN.md").read_text(encoding="utf-8")

        self.assertIn("src/core/runtime_parts.py", root_readme_en)
        self.assertIn("src/core/logging_utils.py", root_readme_en)
        self.assertIn("runtime/src/core/runtime_factory.py", skill_readme)
        self.assertIn("runtime/src/core/logging_setup.py", skill_readme)
        self.assertIn("runtime/src/core/runtime_factory.py", skill_readme_en)
        self.assertIn("runtime/src/core/logging_setup.py", skill_readme_en)


if __name__ == "__main__":
    unittest.main()
