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
