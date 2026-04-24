#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.config import Config
from src.core.main import ZaomengCLI
from src.modules.chat_engine import ChatEngine
from src.modules.distillation import NovelDistiller
from src.modules.reflection import ReflectionEngine
from src.modules.relationships import RelationshipExtractor
from src.modules.speaker import Speaker
from src.utils.file_utils import load_json, normalize_character_name, normalize_relation_key, save_json


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
            "\u6797\u9edb\u7389\u770b\u7740\u8d3e\u5b9d\u7389\uff0c\u6ca1\u6709\u8bf4\u8bdd\u3002"
            "\u859b\u5b9d\u9497\u8fd9\u65f6\u624d\u8fdb\u95e8\u3002"
            "\u6797\u9edb\u7389\u53c8\u5bf9\u8d3e\u5b9d\u7389\u8bf4\uff0c\u4f60\u8be5\u56de\u53bb\u4e86\u3002"
        )
        pairs = extractor._extract_pair_interactions(
            chunk,
            ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389", "\u859b\u5b9d\u9497"],
        )

        self.assertIn("\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389", pairs)
        self.assertEqual(len(pairs["\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389"]), 2)
        self.assertNotIn("\u6797\u9edb\u7389_\u859b\u5b9d\u9497", pairs)
        self.assertNotIn("\u859b\u5b9d\u9497_\u8d3e\u5b9d\u7389", pairs)

    def test_chat_engine_scopes_profiles_and_relations_by_novel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "novel_a" / "\u6797\u9edb\u7389.json",
                {"name": "\u6797\u9edb\u7389", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "novel_a" / "\u8d3e\u5b9d\u7389.json",
                {"name": "\u8d3e\u5b9d\u7389", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "novel_b" / "\u54c8\u5229.json",
                {"name": "\u54c8\u5229", "speech_style": "\u76f4\u63a5", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "relations" / "novel_a" / "novel_a_relations.json",
                {
                    "\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389": {
                        "trust": 8,
                        "affection": 7,
                        "power_gap": 0,
                        "appellations": {
                            "\u8d3e\u5b9d\u7389->\u6797\u9edb\u7389": "\u59b9\u59b9",
                            "\u6797\u9edb\u7389->\u8d3e\u5b9d\u7389": "\u5b9d\u7389",
                        },
                    }
                },
            )
            save_json(
                root / "relations" / "novel_b" / "novel_b_relations.json",
                {"\u54c8\u5229_\u7f57\u6069": {"trust": 2, "affection": 2, "power_gap": 0}},
            )

            engine = ChatEngine(config)
            session = engine.create_session("novel_a.txt", "observe")

            self.assertEqual(session["novel_id"], "novel_a")
            self.assertEqual(session["characters"], ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"])
            self.assertEqual(session["state"]["relation_matrix"]["\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389"]["trust"], 8)
            self.assertEqual(
                session["state"]["relation_matrix"]["\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389"]["appellations"][
                    "\u8d3e\u5b9d\u7389->\u6797\u9edb\u7389"
                ],
                "\u59b9\u59b9",
            )
            self.assertNotIn("\u54c8\u5229", session["characters"])

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

    def test_act_mode_prefers_explicit_or_strongest_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "hongloumeng" / "\u6797\u9edb\u7389.json",
                {"name": "\u6797\u9edb\u7389", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u8d3e\u5b9d\u7389.json",
                {"name": "\u8d3e\u5b9d\u7389", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u51af\u7d2b\u82f1.json",
                {"name": "\u51af\u7d2b\u82f1", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "relations" / "hongloumeng" / "hongloumeng_relations.json",
                {
                    "\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389": {"trust": 9, "affection": 9, "power_gap": 0},
                    "\u51af\u7d2b\u82f1_\u8d3e\u5b9d\u7389": {"trust": 4, "affection": 3, "power_gap": 0},
                },
            )

            engine = ChatEngine(config)
            session = engine.create_session("hongloumeng.txt", "act")

            responders = engine._active_characters(
                session,
                speaker="\u8d3e\u5b9d\u7389",
                context="\u59b9\u59b9\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f",
            )
            self.assertEqual(responders, ["\u6797\u9edb\u7389"])

            explicit = engine._active_characters(
                session,
                speaker="\u8d3e\u5b9d\u7389",
                context="\u6797\u59b9\u59b9\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f",
            )
            self.assertEqual(explicit, ["\u6797\u9edb\u7389"])

    def test_save_json_replaces_surrogates(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "session.json"
            save_json(target, {"message": "x\udce5y"})
            payload = load_json(target)
            self.assertEqual(payload["message"], "x?y")

    def test_save_correction_returns_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            reflection = ReflectionEngine(config)

            item = reflection.save_correction(
                session_id="abc123",
                character="刘备",
                target="关羽",
                original_message="是否联吴？",
                corrected_message="此事需先审时度势。",
                reason="tone_fix",
            )

            self.assertIn("file_path", item)
            self.assertTrue(Path(item["file_path"]).exists())

    def test_normalize_character_name_maps_common_aliases(self):
        self.assertEqual(normalize_character_name("关公"), "关羽")
        self.assertEqual(normalize_character_name("云长"), "关羽")
        self.assertEqual(normalize_relation_key("关公_刘备"), "关羽_刘备")

    def test_distiller_rejects_name_plus_dialogue_verb_noise(self):
        distiller = NovelDistiller(Config())
        self.assertFalse(distiller._looks_like_name("\u51e4\u59d0\u7b11"))
        self.assertFalse(distiller._looks_like_name("\u51e4\u59d0\u542c"))
        self.assertTrue(distiller._looks_like_name("\u8d3e\u5b9d\u7389"))

    def test_chat_engine_normalizes_legacy_noisy_profile_and_relation_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "hongloumeng" / "\u51e4\u59d0\u7b11.json",
                {"name": "\u51e4\u59d0\u7b11", "speech_style": "\u51cc\u5389", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u8d3e\u5b9d\u7389.json",
                {"name": "\u8d3e\u5b9d\u7389", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "relations" / "hongloumeng" / "hongloumeng_relations.json",
                {"\u51e4\u59d0\u542c_\u8d3e\u5b9d\u7389": {"trust": 6, "affection": 4, "power_gap": 0}},
            )

            engine = ChatEngine(config)
            session = engine.create_session("hongloumeng.txt", "act")

            self.assertIn("\u51e4\u59d0", session["characters"])
            self.assertNotIn("\u51e4\u59d0\u7b11", session["characters"])
            self.assertEqual(session["state"]["relation_matrix"]["\u51e4\u59d0_\u8d3e\u5b9d\u7389"]["trust"], 6)

    def test_chat_engine_merges_canonical_alias_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "sanguo" / "关羽.json",
                {"name": "关羽", "speech_style": "谨慎", "typical_lines": ["大义为先"], "core_traits": ["谨慎"], "values": {}},
            )
            save_json(
                root / "characters" / "sanguo" / "关公.json",
                {"name": "关公", "speech_style": "", "typical_lines": ["忠义不可失"], "core_traits": ["忠诚"], "values": {}},
            )
            save_json(
                root / "characters" / "sanguo" / "刘备.json",
                {"name": "刘备", "speech_style": "克制", "typical_lines": [], "core_traits": ["仁厚"], "values": {}},
            )

            engine = ChatEngine(config)
            session = engine.create_session("sanguo.txt", "observe")

            self.assertIn("关羽", session["characters"])
            self.assertNotIn("关公", session["characters"])
            profile = engine._load_character_profiles("sanguo")["关羽"]
            self.assertIn("大义为先", profile["typical_lines"])
            self.assertIn("忠义不可失", profile["typical_lines"])

    def test_observe_once_runs_single_turn_and_persists_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"chat_engine": {"max_speakers_per_turn": 1}})

            save_json(
                root / "characters" / "hongloumeng" / "\u6797\u9edb\u7389.json",
                {"name": "\u6797\u9edb\u7389", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u8d3e\u5b9d\u7389.json",
                {"name": "\u8d3e\u5b9d\u7389", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )

            engine = ChatEngine(config)
            engine.speaker.generate = Mock(return_value="\u4f60\u8bf4\u5f97\u662f\u3002")
            session = engine.create_session("hongloumeng.txt", "observe")

            replies = engine.observe_once(session, "\u8bf7\u8ba9\u5927\u5bb6\u56f4\u7ed5\u8fd9\u4ef6\u4e8b\u5404\u8bf4\u4e00\u53e5\u3002")

            self.assertEqual(len(replies), 1)
            self.assertEqual(replies[0][1], "\u4f60\u8bf4\u5f97\u662f\u3002")

            restored = engine.restore_session(session["id"])
            self.assertEqual(restored["history"][0]["speaker"], "Narrator")
            self.assertEqual(
                restored["history"][0]["message"],
                "\u8bf7\u8ba9\u5927\u5bb6\u56f4\u7ed5\u8fd9\u4ef6\u4e8b\u5404\u8bf4\u4e00\u53e5\u3002",
            )
            self.assertEqual(len(restored["history"]), 2)

    def test_observe_once_uses_explicit_character_prefix_as_speaker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"chat_engine": {"max_speakers_per_turn": 4}})

            save_json(
                root / "characters" / "sanguo" / "\u5218\u5907.json",
                {"name": "\u5218\u5907", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "sanguo" / "\u5f20\u98de.json",
                {"name": "\u5f20\u98de", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "sanguo" / "\u5173\u7fbd.json",
                {"name": "\u5173\u7fbd", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )

            engine = ChatEngine(config)
            engine.speaker.generate = Mock(side_effect=lambda character_profile, **_: f"{character_profile['name']}\u56de\u5e94")
            session = engine.create_session("sanguo.txt", "observe")

            replies = engine.observe_once(session, "\u5218\u5907\uff1a\u4e8c\u4f4d\u8d24\u5f1f\uff0c\u4eca\u65e5\u603b\u7b97\u5f97\u7247\u523b\u6e05\u95f2\u3002")

            self.assertEqual(sorted(name for name, _ in replies), ["\u5173\u7fbd", "\u5f20\u98de"])
            restored = engine.restore_session(session["id"])
            self.assertEqual(restored["history"][0]["speaker"], "\u5218\u5907")
            self.assertEqual(restored["history"][0]["message"], "\u4e8c\u4f4d\u8d24\u5f1f\uff0c\u4eca\u65e5\u603b\u7b97\u5f97\u7247\u523b\u6e05\u95f2\u3002")

    def test_act_once_requires_identifiable_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "hongloumeng" / "\u6797\u9edb\u7389.json",
                {"name": "\u6797\u9edb\u7389", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u8d3e\u5b9d\u7389.json",
                {"name": "\u8d3e\u5b9d\u7389", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )

            engine = ChatEngine(config)
            session = engine.create_session("hongloumeng.txt", "act")

            with self.assertRaisesRegex(ValueError, "\u672a\u8bc6\u522b\u5230\u660e\u786e\u5bf9\u8bdd\u5bf9\u8c61"):
                engine.act_once(session, "\u8d3e\u5b9d\u7389", "\u4eca\u65e5\u5929\u6c14\u5012\u8fd8\u4e0d\u9519\u3002")

    def test_act_once_supports_alias_target_in_single_turn_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "hongloumeng" / "\u6797\u9edb\u7389.json",
                {"name": "\u6797\u9edb\u7389", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u8d3e\u5b9d\u7389.json",
                {"name": "\u8d3e\u5b9d\u7389", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "relations" / "hongloumeng" / "hongloumeng_relations.json",
                {"\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389": {"trust": 9, "affection": 9, "power_gap": 0}},
            )

            engine = ChatEngine(config)
            engine.speaker.generate = Mock(return_value="\u4e0d\u52b3\u6302\u5ff5\uff0c\u6211\u4eca\u65e5\u8fd8\u597d\u3002")
            session = engine.create_session("hongloumeng.txt", "act")

            replies = engine.act_once(session, "\u8d3e\u5b9d\u7389", "\u59b9\u59b9\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f")

            self.assertEqual(replies, [("\u6797\u9edb\u7389", "\u4e0d\u52b3\u6302\u5ff5\uff0c\u6211\u4eca\u65e5\u8fd8\u597d\u3002")])

    def test_act_mode_supports_honorific_alias_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "hongloumeng" / "\u6797\u9edb\u7389.json",
                {"name": "\u6797\u9edb\u7389", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u8d3e\u5b9d\u7389.json",
                {"name": "\u8d3e\u5b9d\u7389", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )

            engine = ChatEngine(config)
            session = engine.create_session("hongloumeng.txt", "act")

            responders = engine._active_characters(
                session,
                speaker="\u6797\u9edb\u7389",
                context="\u5b9d\u54e5\u54e5\uff0c\u4eca\u5929\u600e\u4e48\u6765\u8fd9\u4e48\u665a\uff1f",
            )

            self.assertEqual(responders, ["\u8d3e\u5b9d\u7389"])

    def test_act_mode_remembers_last_explicit_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "hongloumeng" / "\u6797\u9edb\u7389.json",
                {"name": "\u6797\u9edb\u7389", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u8d3e\u5b9d\u7389.json",
                {"name": "\u8d3e\u5b9d\u7389", "speech_style": "\u76f4\u767d", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "hongloumeng" / "\u859b\u5b9d\u9497.json",
                {"name": "\u859b\u5b9d\u9497", "speech_style": "\u5e73\u7a33", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "relations" / "hongloumeng" / "hongloumeng_relations.json",
                {
                    "\u6797\u9edb\u7389_\u8d3e\u5b9d\u7389": {"trust": 9, "affection": 9, "power_gap": 0},
                    "\u859b\u5b9d\u9497_\u8d3e\u5b9d\u7389": {"trust": 8, "affection": 8, "power_gap": 0},
                },
            )

            engine = ChatEngine(config)
            engine.speaker.generate = Mock(return_value="\u56de\u5e94")
            session = engine.create_session("hongloumeng.txt", "act")

            first = engine.act_once(session, "\u8d3e\u5b9d\u7389", "\u6797\u59b9\u59b9\uff0c\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f")
            second = engine.act_once(session, "\u8d3e\u5b9d\u7389", "\u6211\u53ea\u662f\u60f3\u518d\u95ee\u4f60\u4e00\u53e5\u3002")

            self.assertEqual(first, [("\u6797\u9edb\u7389", "\u56de\u5e94")])
            self.assertEqual(second, [("\u6797\u9edb\u7389", "\u56de\u5e94")])
            self.assertEqual(session["state"]["focus_targets"]["\u8d3e\u5b9d\u7389"], "\u6797\u9edb\u7389")

    def test_speaker_avoids_dumping_typical_line_as_reply(self):
        speaker = Speaker(Config())
        profile = {
            "name": "\u8d3e\u5b9d\u7389",
            "core_traits": ["\u654f\u611f"],
            "speech_style": "\u76f4\u767d",
            "typical_lines": [
                "\u58eb\u9690\u63a5\u4e86\u770b\u65f6\uff0c\u539f\u6765\u662f\u5757\u9c9c\u660e\u7f8e\u7389\uff0c\u4e0a\u9762\u5b57\u8ff9\u5206\u660e\uff0c\u954c\u7740\u201c\u901a\u7075\u5b9d\u7389\u201d\u56db\u5b57\u3002"
            ],
            "values": {},
        }

        reply = speaker.generate(
            character_profile=profile,
            context="\u9edb\u7389\u5728\u95ee\u4f60\u4eca\u65e5\u4e3a\u4f55\u6765\u665a\u4e86\u3002",
            history=[],
            target_name="\u6797\u9edb\u7389",
            relation_state={"affection": 8, "trust": 8, "hostility": 0, "ambiguity": 2},
        )

        self.assertNotIn("\u58eb\u9690\u63a5\u4e86\u770b\u65f6", reply)
        self.assertNotIn("\u901a\u7075\u5b9d\u7389", reply)
        self.assertIn("\u6797\u9edb\u7389", reply)

    def test_speaker_answers_decision_question_with_a_stance(self):
        speaker = Speaker(Config())
        profile = {
            "name": "关羽",
            "core_traits": ["谨慎"],
            "speech_style": "克制",
            "typical_lines": [],
            "values": {},
        }

        reply = speaker.generate(
            character_profile=profile,
            context="二位贤弟，我们是否应该联合孙权对抗曹操？",
            history=[],
            target_name="刘备",
            relation_state={"affection": 7, "trust": 8, "hostility": 0, "ambiguity": 4},
        )

        self.assertIn("依我看", reply)
        self.assertTrue("定夺" in reply or "留" in reply or "能做" in reply)

    def test_speaker_prefers_relation_specific_appellation(self):
        speaker = Speaker(Config())
        profile = {
            "name": "刘备",
            "core_traits": ["仁厚"],
            "speech_style": "克制",
            "typical_lines": [],
            "values": {},
        }

        reply = speaker.generate(
            character_profile=profile,
            context="今日难得清闲。",
            history=[],
            target_name="关羽",
            relation_state={
                "affection": 8,
                "trust": 8,
                "hostility": 0,
                "ambiguity": 3,
                "appellations": {"刘备->关羽": "二弟"},
            },
        )

        self.assertIn("二弟", reply)
        self.assertNotIn("关羽，", reply)

    def test_speaker_profiles_produce_distinct_voices(self):
        speaker = Speaker(Config())
        context = "\u4e8c\u4f4d\u8d24\u5f1f\uff0c\u6211\u4eec\u662f\u5426\u5e94\u5f53\u8054\u5408\u5b59\u6743\uff1f"

        liubei_reply = speaker.generate(
            character_profile={
                "name": "\u5218\u5907",
                "core_traits": ["\u4ec1\u539a", "\u514b\u5236"],
                "speech_style": "\u8bed\u8a00\u94fa\u9648\uff0c\u6574\u4f53\u514b\u5236\u3002",
                "typical_lines": ["\u767e\u59d3\u6d41\u79bb\u5931\u6240\uff0c\u624d\u662f\u6211\u6700\u4e0d\u613f\u89c1\u4e4b\u4e8b\u3002"],
                "decision_rules": ["\u540c\u4f34\u53d7\u538b\u2192\u503e\u5411\u4e3b\u52a8\u4ecb\u5165"],
                "values": {"\u8d23\u4efb": 9, "\u5584\u826f": 8, "\u5fe0\u8bda": 8, "\u667a\u6167": 7},
            },
            context=context,
            history=[],
            target_name="\u5173\u7fbd",
            relation_state={"affection": 8, "trust": 8, "hostility": 0, "ambiguity": 3},
        )

        zhangfei_reply = speaker.generate(
            character_profile={
                "name": "\u5f20\u98de",
                "core_traits": ["\u8c6a\u723d", "\u52c7\u6562"],
                "speech_style": "\u8bed\u8a00\u76f4\u767d\uff0c\u60c5\u7eea\u5916\u9732\u3002",
                "typical_lines": ["\u54e5\u54e5\u82e5\u6709\u53f7\u4ee4\uff0c\u6211\u5148\u4e0a\u524d\u3002"],
                "decision_rules": ["\u540c\u4f34\u53d7\u538b\u2192\u503e\u5411\u4e3b\u52a8\u4ecb\u5165"],
                "values": {"\u52c7\u6c14": 9, "\u5fe0\u8bda": 8, "\u8d23\u4efb": 6, "\u667a\u6167": 4},
            },
            context=context,
            history=[],
            target_name="\u5218\u5907",
            relation_state={"affection": 8, "trust": 8, "hostility": 0, "ambiguity": 3},
        )

        self.assertNotEqual(liubei_reply, zhangfei_reply)
        self.assertTrue(any(token in liubei_reply for token in ("\u9000\u8def", "\u4f17\u4eba", "\u767e\u59d3", "\u7740\u843d")))
        self.assertTrue(any(token in zhangfei_reply for token in ("\u4e0d\u8eb2", "\u5411\u524d", "\u5144\u5f1f", "\u81ea\u5df1\u4eba")))

    def test_speaker_reacts_to_taboo_topic(self):
        speaker = Speaker(Config())
        reply = speaker.generate(
            character_profile={
                "name": "\u5173\u7fbd",
                "core_traits": ["\u5fe0\u8bda", "\u8c28\u614e"],
                "speech_style": "\u514b\u5236",
                "typical_lines": [],
                "decision_rules": [],
                "values": {"\u5fe0\u8bda": 9, "\u6b63\u4e49": 8},
                "taboo_topics": ["\u80cc\u53db", "\u5931\u4fe1"],
            },
            context="\u82e5\u4e3a\u4fdd\u5168\u81ea\u8eab\uff0c\u80cc\u53db\u4e00\u6b21\u53c8\u4f55\u59a8\uff1f",
            history=[],
            target_name="\u5218\u5907",
            relation_state={"affection": 7, "trust": 8, "hostility": 0, "ambiguity": 3},
        )

        self.assertTrue(any(token in reply for token in ("\u80cc\u53db", "\u754c\u7ebf", "\u4e0d\u80fd\u5f53\u4f5c\u5bfb\u5e38\u8bdd")))

    def test_distiller_profiles_include_voice_and_boundary_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            novel_path = root / "mini.txt"
            novel_path.write_text(
                "\u5218\u5907\u8bf4\uff1a\u201c\u767e\u59d3\u672a\u5b89\uff0c\u6211\u4e0d\u80fd\u5148\u56fe\u81ea\u4fbf\u3002\u201d"
                "\u5173\u7fbd\u9053\uff1a\u201c\u5927\u4e49\u5f53\u524d\uff0c\u5931\u4fe1\u4e4b\u4e8b\u4e0d\u53ef\u4e3a\u3002\u201d",
                encoding="utf-8",
            )

            distiller = NovelDistiller(config)
            result = distiller.distill(str(novel_path), characters=["\u5218\u5907", "\u5173\u7fbd"])
            liubei = result["\u5218\u5907"]

            self.assertIn("worldview", liubei)
            self.assertIn("thinking_style", liubei)
            self.assertIn("speech_habits", liubei)
            self.assertIn("emotion_profile", liubei)
            self.assertIn("taboo_topics", liubei)
            self.assertIn("forbidden_behaviors", liubei)

    def test_distiller_exports_persona_bundle_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            novel_path = root / "mini.txt"
            novel_path.write_text(
                "\u5218\u5907\u8bf4\uff1a\u201c\u767e\u59d3\u672a\u5b89\uff0c\u6211\u4e0d\u80fd\u5148\u56fe\u81ea\u4fbf\u3002\u201d",
                encoding="utf-8",
            )

            distiller = NovelDistiller(config)
            distiller.distill(str(novel_path), characters=["\u5218\u5907"])

            persona_dir = root / "characters" / "mini" / "\u5218\u5907"
            self.assertTrue((persona_dir / "SOUL.generated.md").exists())
            self.assertTrue((persona_dir / "IDENTITY.generated.md").exists())
            self.assertTrue((persona_dir / "AGENTS.generated.md").exists())
            self.assertTrue((persona_dir / "MEMORY.generated.md").exists())
            self.assertTrue((persona_dir / "NAVIGATION.generated.md").exists())
            self.assertTrue((persona_dir / "NAVIGATION.md").exists())
            self.assertTrue((persona_dir / "SOUL.md").exists())

    def test_relationship_extractor_exports_relation_markdown_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            extractor = RelationshipExtractor(config)
            extractor._export_relation_bundle(
                {
                    "\u5218\u5907_\u5173\u7fbd": {
                        "trust": 8,
                        "affection": 7,
                        "power_gap": 0,
                        "conflict_point": "\u540c\u76df\u53d6\u820d",
                        "typical_interaction": "\u5148\u8bae\u8f7b\u91cd\uff0c\u518d\u5b9a\u8fdb\u9000",
                        "appellations": {"\u5218\u5907->\u5173\u7fbd": "\u4e8c\u5f1f"},
                    }
                },
                "mini",
            )

            self.assertTrue((root / "characters" / "mini" / "\u5218\u5907" / "RELATIONS.generated.md").exists())
            self.assertTrue((root / "characters" / "mini" / "\u5218\u5907" / "RELATIONS.md").exists())
            nav_text = (root / "characters" / "mini" / "\u5218\u5907" / "NAVIGATION.generated.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## RELATIONS", nav_text)
            self.assertIn("- status: active", nav_text)

    def test_relation_markdown_override_changes_runtime_relation_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "sanguo" / "\u5218\u5907.json",
                {"name": "\u5218\u5907", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u4ec1\u539a"], "values": {}},
            )
            save_json(
                root / "characters" / "sanguo" / "\u5173\u7fbd.json",
                {"name": "\u5173\u7fbd", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u5fe0\u8bda"], "values": {}},
            )
            save_json(
                root / "relations" / "sanguo" / "sanguo_relations.json",
                {
                    "\u5218\u5907_\u5173\u7fbd": {
                        "trust": 5,
                        "affection": 5,
                        "power_gap": 0,
                        "appellations": {"\u5218\u5907->\u5173\u7fbd": "\u5173\u7fbd"},
                    }
                },
            )
            relation_dir = root / "characters" / "sanguo" / "\u5218\u5907"
            relation_dir.mkdir(parents=True, exist_ok=True)
            (relation_dir / "RELATIONS.md").write_text(
                "# RELATIONS\n\n"
                "## \u5173\u7fbd\n"
                "- trust: 9\n"
                "- affection: 8\n"
                "- appellation_to_target: \u4e8c\u5f1f\n",
                encoding="utf-8",
            )

            engine = ChatEngine(config)
            state = engine._get_relation_state_from_disk("\u5218\u5907", "\u5173\u7fbd", "sanguo")

            self.assertEqual(state["trust"], 9)
            self.assertEqual(state["affection"], 8)
            self.assertEqual(state["appellations"]["\u5218\u5907->\u5173\u7fbd"], "\u4e8c\u5f1f")

    def test_navigation_load_order_controls_persona_override_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "sanguo" / "\u5218\u5907.json",
                {"name": "\u5218\u5907", "speech_style": "\u57fa\u7ebf", "typical_lines": [], "core_traits": ["\u4ec1\u539a"], "values": {}},
            )
            persona_dir = root / "characters" / "sanguo" / "\u5218\u5907"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "NAVIGATION.md").write_text(
                "# NAVIGATION\n\n"
                "## Runtime\n"
                "- load_order: SOUL -> STYLE -> MEMORY\n",
                encoding="utf-8",
            )
            (persona_dir / "SOUL.md").write_text("# SOUL\n\n- speech_style: \u514b\u5236\n", encoding="utf-8")
            (persona_dir / "STYLE.md").write_text("# STYLE\n\n- speech_style: \u76f4\u767d\n", encoding="utf-8")
            (persona_dir / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")

            engine = ChatEngine(config)
            profile = engine._load_character_profiles("sanguo")["\u5218\u5907"]

            self.assertEqual(profile["speech_style"], "\u76f4\u767d")

    def test_navigation_can_disable_optional_persona_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "sanguo" / "\u5173\u7fbd.json",
                {"name": "\u5173\u7fbd", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u5fe0\u8bda"], "values": {}},
            )
            persona_dir = root / "characters" / "sanguo" / "\u5173\u7fbd"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "NAVIGATION.md").write_text(
                "# NAVIGATION\n\n"
                "## Runtime\n"
                "- load_order: STYLE -> SOUL -> MEMORY\n\n"
                "## STYLE\n"
                "- status: inactive\n",
                encoding="utf-8",
            )
            (persona_dir / "STYLE.md").write_text("# STYLE\n\n- speech_style: \u76f4\u767d\n", encoding="utf-8")
            (persona_dir / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")

            engine = ChatEngine(config)
            profile = engine._load_character_profiles("sanguo")["\u5173\u7fbd"]

            self.assertEqual(profile["speech_style"], "\u514b\u5236")

    def test_navigation_can_link_relation_overlay_to_custom_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "sanguo" / "\u5218\u5907.json",
                {"name": "\u5218\u5907", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u4ec1\u539a"], "values": {}},
            )
            save_json(
                root / "characters" / "sanguo" / "\u5173\u7fbd.json",
                {"name": "\u5173\u7fbd", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u5fe0\u8bda"], "values": {}},
            )
            save_json(
                root / "relations" / "sanguo" / "sanguo_relations.json",
                {"\u5218\u5907_\u5173\u7fbd": {"trust": 5, "affection": 5, "power_gap": 0}},
            )
            persona_dir = root / "characters" / "sanguo" / "\u5218\u5907"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "NAVIGATION.md").write_text(
                "# NAVIGATION\n\n"
                "## RELATIONS\n"
                "- status: active\n"
                "- file: CUSTOM_RELATIONS.md\n",
                encoding="utf-8",
            )
            (persona_dir / "CUSTOM_RELATIONS.md").write_text(
                "# RELATIONS\n\n"
                "## \u5173\u7fbd\n"
                "- trust: 9\n"
                "- affection: 8\n"
                "- appellation_to_target: \u4e8c\u5f1f\n",
                encoding="utf-8",
            )

            engine = ChatEngine(config)
            state = engine._get_relation_state_from_disk("\u5218\u5907", "\u5173\u7fbd", "sanguo")

            self.assertEqual(state["trust"], 9)
            self.assertEqual(state["affection"], 8)
            self.assertEqual(state["appellations"]["\u5218\u5907->\u5173\u7fbd"], "\u4e8c\u5f1f")

    def test_chat_engine_prefers_editable_persona_bundle_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "sanguo" / "\u5218\u5907.json",
                {
                    "name": "\u5218\u5907",
                    "speech_style": "\u514b\u5236",
                    "typical_lines": [],
                    "core_traits": ["\u4ec1\u539a"],
                    "values": {"\u8d23\u4efb": 8},
                },
            )
            persona_dir = root / "characters" / "sanguo" / "\u5218\u5907"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "SOUL.md").write_text(
                "# SOUL\n\n"
                "- soul_goal: \u66ff\u5929\u4e0b\u4eba\u5b88\u4f4f\u5b89\u8eab\u7acb\u547d\u4e4b\u6240\n"
                "- taboo_topics: \u5f03\u6c11\uff1b\u80cc\u4fe1\n",
                encoding="utf-8",
            )

            engine = ChatEngine(config)
            profile = engine._load_character_profiles("sanguo")["\u5218\u5907"]

            self.assertEqual(profile["soul_goal"], "\u66ff\u5929\u4e0b\u4eba\u5b88\u4f4f\u5b89\u8eab\u7acb\u547d\u4e4b\u6240")
            self.assertEqual(profile["taboo_topics"], ["\u5f03\u6c11", "\u80cc\u4fe1"])

    def test_runtime_guidance_prompt_persists_into_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"chat_engine": {"max_speakers_per_turn": 1}})

            save_json(
                root / "characters" / "sanguo" / "\u5173\u7fbd.json",
                {"name": "\u5173\u7fbd", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u5fe0\u8bda"], "values": {}},
            )
            save_json(
                root / "characters" / "sanguo" / "\u5218\u5907.json",
                {"name": "\u5218\u5907", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u4ec1\u539a"], "values": {}},
            )

            engine = ChatEngine(config)
            engine.speaker.generate = Mock(return_value="\u56de\u5e94")
            session = engine.create_session("sanguo.txt", "observe")

            engine.observe_once(session, "\u8bb0\u4f4f\uff1a\u5173\u7fbd\u8bf4\u8bdd\u8981\u66f4\u77ed\uff0c\u4e0d\u8981\u8f7b\u4f7b\u3002")

            profile = engine._load_character_profiles("sanguo")["\u5173\u7fbd"]
            self.assertTrue(any("\u8bb0\u4f4f" in item for item in profile.get("user_edits", [])))

    def test_inline_correction_persists_into_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "sanguo" / "\u5173\u7fbd.json",
                {"name": "\u5173\u7fbd", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u5fe0\u8bda"], "values": {}},
            )
            save_json(
                root / "characters" / "sanguo" / "\u5218\u5907.json",
                {"name": "\u5218\u5907", "speech_style": "\u514b\u5236", "typical_lines": [], "core_traits": ["\u4ec1\u539a"], "values": {}},
            )

            engine = ChatEngine(config)
            session = engine.create_session("sanguo.txt", "observe")

            handled = engine._handle_inline_command(
                session,
                "/correct \u5173\u7fbd|\u5218\u5907|\u5bb9\u6211\u518d\u60f3\u60f3|\u5927\u4e49\u5f53\u524d\uff0c\u4e0d\u53ef\u8f7b\u6613\u80cc\u4fe1|tone_fix",
            )

            self.assertTrue(handled)
            profile = engine._load_character_profiles("sanguo")["\u5173\u7fbd"]
            self.assertTrue(any("\u7ea0\u6b63" in item for item in profile.get("user_edits", [])))

    def test_user_edits_can_change_voice_constraints(self):
        speaker = Speaker(Config())
        profile = {
            "name": "\u5173\u7fbd",
            "core_traits": ["\u5fe0\u8bda", "\u8c28\u614e"],
            "speech_style": "\u514b\u5236",
            "typical_lines": [],
            "decision_rules": [],
            "values": {"\u5fe0\u8bda": 9},
            "user_edits": ["\u8bb0\u4f4f\uff1a\u5173\u7fbd\u8bf4\u8bdd\u8981\u66f4\u77ed\uff0c\u4e0d\u8981\u8f7b\u4f7b\uff0c\u8981\u66f4\u91cd\u4fe1\u4e49\u3002"],
        }

        voice = speaker._build_voice(profile)

        self.assertEqual(voice["speech_habits"]["cadence"], "short")
        self.assertIn("\u4e0d\u4f1a\u8f7b\u4f7b\u8c03\u7b11", voice["forbidden_behaviors"])

    def test_cli_chat_message_uses_single_turn_path(self):
        argv = [
            "zaomeng",
            "chat",
            "--novel",
            "hongloumeng.txt",
            "--mode",
            "act",
            "--character",
            "\u8d3e\u5b9d\u7389",
            "--message",
            "\u59b9\u59b9\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f",
        ]

        with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print"):
            engine = engine_cls.return_value
            session = {"id": "testsession", "title": "test", "characters": ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389"]}
            engine.create_session.return_value = session
            engine.act_once.return_value = [("\u6797\u9edb\u7389", "\u4e0d\u52b3\u6302\u5ff5\uff0c\u6211\u4eca\u65e5\u8fd8\u597d\u3002")]

            ZaomengCLI().run()

            engine.create_session.assert_called_once_with("hongloumeng.txt", "act")
            engine.act_once.assert_called_once_with(
                session,
                "\u8d3e\u5b9d\u7389",
                "\u59b9\u59b9\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f",
            )
            engine.act_mode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
