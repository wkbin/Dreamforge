#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from src.core.config import Config, clear_config_cache
from src.core.path_provider import PathProvider
from src.core.rulebook import RuleBook
from src.utils.file_utils import clear_markdown_data_cache


class HotReloadTests(unittest.TestCase):
    def setUp(self):
        clear_config_cache()
        clear_markdown_data_cache()

    def tearDown(self):
        clear_config_cache()
        clear_markdown_data_cache()

    def test_config_reload_picks_up_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.yaml"
            config_path.write_text("llm:\n  provider: openai\n", encoding="utf-8")

            config = Config(str(config_path))
            self.assertEqual(config.get("llm.provider"), "openai")

            config_path.write_text("llm:\n  provider: anthropic\n", encoding="utf-8")
            config.reload()
            self.assertEqual(config.get("llm.provider"), "anthropic")

    def test_rulebook_reload_picks_up_rule_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rules_dir = root / "rules"
            rules_dir.mkdir(parents=True, exist_ok=True)
            for filename in RuleBook.FILE_MAP.values():
                (rules_dir / filename).write_text("---\nversion: one\n---\n\n# DATA\n", encoding="utf-8")

            config_path = root / "config.yaml"
            config_path.write_text("paths:\n  rules: rules\n", encoding="utf-8")
            config = Config(str(config_path))
            path_provider = PathProvider(config)
            rulebook = RuleBook(config, path_provider=path_provider)

            self.assertEqual(rulebook.get("distillation", "version"), "one")

            (rules_dir / "distillation_rules.md").write_text("---\nversion: two\n---\n\n# DATA\n", encoding="utf-8")
            rulebook.reload()
            self.assertEqual(rulebook.get("distillation", "version"), "two")


if __name__ == "__main__":
    unittest.main()
