#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from src.core.config import Config
from src.core.path_provider import PathProvider
from src.core.relation_store import MarkdownRelationStore
from src.utils.file_utils import load_markdown_data


class RelationStoreTests(unittest.TestCase):
    def test_markdown_relation_store_persists_default_and_explicit_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config()
            config.update({"paths": {"relations": str(root / "relations")}})
            store = MarkdownRelationStore(PathProvider(config))
            relations = {
                "刘备_关羽": {
                    "trust": 9,
                    "affection": 8,
                    "power_gap": 0,
                    "conflict_point": "取舍先后",
                }
            }

            store.save_relations("sanguo", relations)
            store.save_relations("sanguo", relations, output_path=str(root / "exports"))

            default_payload = store.load_relations("sanguo", default=None)
            exported_payload = load_markdown_data(root / "exports" / "sanguo_relations.md", default=None)

            self.assertEqual(default_payload["novel_id"], "sanguo")
            self.assertEqual(default_payload["relations"]["刘备_关羽"]["trust"], 9)
            self.assertEqual(exported_payload["relations"]["刘备_关羽"]["affection"], 8)

    def test_relation_store_supports_dynamic_update_and_conflict_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config()
            config.update({"paths": {"relations": str(root / "relations")}})
            store = MarkdownRelationStore(PathProvider(config))
            relations = {
                "林黛玉_贾宝玉": {
                    "trust": 8,
                    "affection": 8,
                    "hostility": 2,
                    "ambiguity": 3,
                }
            }
            store.save_relations("hongloumeng", relations)

            updated = store.apply_dialogue_update(
                "hongloumeng",
                pair_key="林黛玉_贾宝玉",
                message="我理解你，但我也恨你这么轻慢。",
                speaker="林黛玉",
                target="贾宝玉",
            )
            self.assertIn("trust", updated)
            self.assertIn("hostility", updated)

            payload = store.load_relations("hongloumeng", default={})
            self.assertIn("conflicts", payload)
            self.assertIsInstance(payload.get("conflicts", []), list)


if __name__ == "__main__":
    unittest.main()
