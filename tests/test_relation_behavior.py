#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tempfile
import unittest
from pathlib import Path

from src.core.config import Config
from src.modules.chat_engine import ChatEngine
from src.modules.distillation import NovelDistiller
from src.modules.relationships import RelationshipExtractor
from src.utils.file_utils import save_json


class RelationBehaviorTests(unittest.TestCase):
    def make_config(self, root: Path) -> Config:
        config = Config()
        config.update(
            {
                "paths": {
                    "characters": str(root / "characters"),
                    "relations": str(root / "relations"),
                    "sessions": str(root / "sessions"),
                    "corrections": str(root / "corrections"),
                    "logs": str(root / "logs"),
                }
            }
        )
        for folder in ("characters", "relations", "sessions", "corrections", "logs"):
            (root / folder).mkdir(parents=True, exist_ok=True)
        return config

    def test_extract_pair_interactions_requires_same_sentence(self):
        extractor = RelationshipExtractor(Config())
        chunk = (
            "林黛玉看着贾宝玉，没有说话。"
            "薛宝钗这时才进门。"
            "林黛玉又对贾宝玉说，你该回去了。"
        )
        pairs = extractor._extract_pair_interactions(chunk, ["林黛玉", "贾宝玉", "薛宝钗"])

        self.assertIn("林黛玉_贾宝玉", pairs)
        self.assertEqual(len(pairs["林黛玉_贾宝玉"]), 2)
        self.assertNotIn("林黛玉_薛宝钗", pairs)
        self.assertNotIn("薛宝钗_贾宝玉", pairs)

    def test_chat_engine_scopes_profiles_and_relations_by_novel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "novel_a" / "林黛玉.json",
                {"name": "林黛玉", "speech_style": "克制", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "novel_a" / "贾宝玉.json",
                {"name": "贾宝玉", "speech_style": "直白", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "novel_b" / "哈利.json",
                {"name": "哈利", "speech_style": "直接", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "relations" / "novel_a" / "novel_a_relations.json",
                {"林黛玉_贾宝玉": {"trust": 8, "affection": 7, "power_gap": 0}},
            )
            save_json(
                root / "relations" / "novel_b" / "novel_b_relations.json",
                {"哈利_罗恩": {"trust": 2, "affection": 2, "power_gap": 0}},
            )

            engine = ChatEngine(config)
            session = engine.create_session("novel_a.txt", "observe")

            self.assertEqual(session["novel_id"], "novel_a")
            self.assertEqual(session["characters"], ["林黛玉", "贾宝玉"])
            self.assertEqual(session["state"]["relation_matrix"]["林黛玉_贾宝玉"]["trust"], 8)
            self.assertNotIn("哈利", session["characters"])

    def test_distill_with_explicit_characters_uses_two_char_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            novel_path = root / "honglou.txt"
            novel_path.write_text(
                "\u9edb\u7389\u770b\u7740\u5b9d\u7389\uff0c\u6ca1\u6709\u8bf4\u8bdd\u3002"
                "\u5b9d\u7389\u7b11\u9053\uff1a\u201c\u4f60\u53c8\u60f3\u591a\u4e86\u3002\u201d"
                "\u9edb\u7389\u5fc3\u91cc\u4e00\u9178\uff0c\u5374\u8fd8\u662f\u770b\u7740\u4ed6\u3002",
                encoding="utf-8",
            )

            distiller = NovelDistiller(config)
            result = distiller.distill(
                str(novel_path),
                characters=["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"],
            )

            self.assertGreater(result["\u6797\u9edb\u7389"]["evidence"]["description_count"], 0)
            self.assertGreater(result["\u8d3e\u5b9d\u7389"]["evidence"]["dialogue_count"], 0)

    def test_relationship_extractor_matches_two_char_aliases(self):
        extractor = RelationshipExtractor(Config())
        alias_map = {
            "\u6797\u9edb\u7389": ["\u6797\u9edb\u7389", "\u9edb\u7389"],
            "\u8d3e\u5b9d\u7389": ["\u8d3e\u5b9d\u7389", "\u5b9d\u7389"],
            "\u859b\u5b9d\u9497": ["\u859b\u5b9d\u9497", "\u5b9d\u9497"],
        }
        chunk = (
            "\u9edb\u7389\u770b\u7740\u5b9d\u7389\uff0c\u6ca1\u6709\u8bf4\u8bdd\u3002"
            "\u5b9d\u9497\u8fd9\u65f6\u624d\u8fdb\u95e8\u3002"
            "\u9edb\u7389\u53c8\u5bf9\u5b9d\u7389\u8bf4\uff0c\u4f60\u8be5\u56de\u53bb\u4e86\u3002"
        )

        pairs = extractor._extract_pair_interactions(
            chunk,
            ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389", "\u859b\u5b9d\u9497"],
            alias_map=alias_map,
        )

        self.assertIn("\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389", pairs)
        self.assertEqual(len(pairs["\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389"]), 2)
        self.assertNotIn("\u6797\u9edb\u7389_\u859b\u5b9d\u9497", pairs)
        self.assertNotIn("\u859b\u5b9d\u9497_\u8d3e\u5b9d\u7389", pairs)


if __name__ == "__main__":
    unittest.main()
