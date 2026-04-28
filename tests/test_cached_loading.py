#!/usr/bin/env python3

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from src.core.config import Config, clear_config_cache
from src.utils.file_utils import clear_markdown_data_cache, load_markdown_data


class CachedLoadingTests(unittest.TestCase):
    def setUp(self):
        clear_markdown_data_cache()
        clear_config_cache()

    def tearDown(self):
        clear_markdown_data_cache()
        clear_config_cache()

    def test_load_markdown_data_reuses_cache_until_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "profile.md"
            target.write_text("---\nname: Liu Bei\n---\n\n# DATA\n", encoding="utf-8")

            with patch("src.utils.file_utils.yaml.safe_load", wraps=yaml.safe_load) as safe_load:
                first = load_markdown_data(target, default={})
                second = load_markdown_data(target, default={})

                self.assertEqual(first["name"], "Liu Bei")
                self.assertEqual(second["name"], "Liu Bei")
                self.assertEqual(safe_load.call_count, 1)

                first["name"] = "Mutated"
                fresh = load_markdown_data(target, default={})
                self.assertEqual(fresh["name"], "Liu Bei")

                time.sleep(0.01)
                target.write_text("---\nname: Guan Yu\n---\n\n# DATA\n", encoding="utf-8")
                target.touch()
                updated = load_markdown_data(target, default={})
                self.assertEqual(updated["name"], "Guan Yu")
                self.assertEqual(safe_load.call_count, 2)

    def test_config_reuses_cache_until_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.yaml"
            target.write_text("llm:\n  provider: openai\n", encoding="utf-8")

            with patch("src.core.config.yaml.safe_load", wraps=yaml.safe_load) as safe_load:
                first = Config(str(target))
                second = Config(str(target))

                self.assertEqual(first.get("llm.provider"), "openai")
                self.assertEqual(second.get("llm.provider"), "openai")
                self.assertEqual(safe_load.call_count, 1)

                first.set_api_key("changed")
                fresh = Config(str(target))
                self.assertEqual(fresh.get("llm.api_key"), "")

                time.sleep(0.01)
                target.write_text("llm:\n  provider: anthropic\n", encoding="utf-8")
                target.touch()
                updated = Config(str(target))
                self.assertEqual(updated.get("llm.provider"), "anthropic")
                self.assertEqual(safe_load.call_count, 2)


if __name__ == "__main__":
    unittest.main()
