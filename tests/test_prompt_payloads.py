#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from src.skill_support.prompt_payloads import build_distill_prompt_payload, build_relation_prompt_payload


class PromptPayloadTests(unittest.TestCase):
    def test_build_distill_prompt_payload_contains_prompt_references_and_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text("甲。乙。丙。", encoding="utf-8")
            payload = build_distill_prompt_payload(
                novel_path,
                characters=["甲", "乙"],
                max_sentences=2,
                max_chars=100,
            )

        self.assertEqual(payload["mode"], "distill")
        self.assertIn("人物档案蒸馏提示词", str(payload["prompt"]))
        self.assertIn("output_schema", payload["references"])
        self.assertEqual(payload["request"]["characters"], ["甲", "乙"])
        self.assertEqual(payload["request"]["excerpt"], "甲。\n乙。")
        self.assertEqual(payload["request"]["update_mode"], "create")
        self.assertIn("excerpt_stages", payload["request"])

    def test_build_relation_prompt_payload_contains_excerpt_and_relation_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text("宝玉。黛玉。宝钗。", encoding="utf-8")
            payload = build_relation_prompt_payload(
                novel_path,
                max_sentences=2,
                max_chars=100,
            )

        self.assertEqual(payload["mode"], "relation")
        self.assertIn("双人关系抽取提示词", str(payload["prompt"]))
        self.assertEqual(payload["request"]["excerpt"], "宝玉。\n黛玉。")
        self.assertIn("logic_constraint", payload["references"])
        self.assertIn("excerpt_stages", payload["request"])

    def test_build_relation_prompt_payload_can_focus_on_requested_characters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text("前文无关。很久以后肖冉登场。肖冉与齐夏对话。", encoding="utf-8")
            payload = build_relation_prompt_payload(
                novel_path,
                characters=["肖冉", "齐夏"],
                max_sentences=4,
                max_chars=200,
            )

        self.assertIn("肖冉", payload["request"]["excerpt"])
        self.assertEqual(payload["request"]["characters"], ["肖冉", "齐夏"])
        self.assertEqual(payload["request"]["excerpt_focus"]["matched_characters"], ["肖冉", "齐夏"])

    def test_build_distill_prompt_payload_reuses_existing_persona_as_incremental_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            novel_path = root / "hongloumeng.txt"
            novel_path.write_text("林黛玉与贾宝玉再遇。", encoding="utf-8")
            persona_dir = root / "data" / "characters" / "hongloumeng" / "林黛玉"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "PROFILE.generated.md").write_text(
                "# PROFILE\n"
                "- name: 林黛玉\n"
                "- novel_id: hongloumeng\n"
                "- identity_anchor: 真心与自尊都很重\n"
                "- soul_goal: 守住真情\n"
                "- speech_style: 轻声细语\n",
                encoding="utf-8",
            )
            (persona_dir / "MEMORY.md").write_text(
                "# MEMORY\n"
                "- user_edits: 说话更短，不要说教\n",
                encoding="utf-8",
            )

            payload = build_distill_prompt_payload(
                novel_path,
                characters=["林黛玉"],
                characters_root=root / "data" / "characters",
                update_mode="auto",
            )

        self.assertEqual(payload["request"]["update_mode"], "incremental")
        self.assertIn("林黛玉", payload["request"]["existing_profiles"])
        existing = payload["request"]["existing_profiles"]["林黛玉"]
        self.assertEqual(existing["identity_anchor"], "真心与自尊都很重")
        self.assertEqual(existing["soul_goal"], "守住真情")
        self.assertIn("说话更短，不要说教", existing["user_edits"])
        self.assertEqual(payload["meta"]["existing_character_count"], 1)


    def test_build_distill_prompt_payload_includes_excerpt_focus(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text("甲。乙。丙。", encoding="utf-8")
            payload = build_distill_prompt_payload(
                novel_path,
                characters=["甲", "乙"],
                max_sentences=2,
                max_chars=100,
            )

        self.assertEqual(payload["request"]["excerpt_focus"]["requested_characters"], ["甲", "乙"])

    def test_build_distill_prompt_payload_focuses_excerpt_on_requested_late_character(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text(
                "前文都在写旁人。前文还没有目标。很久以后肖冉才出现。肖冉终于与齐夏对话。",
                encoding="utf-8",
            )
            payload = build_distill_prompt_payload(
                novel_path,
                characters=["肖冉"],
                max_sentences=4,
                max_chars=200,
            )

        self.assertIn("肖冉", payload["request"]["excerpt"])
        self.assertEqual(payload["request"]["excerpt_focus"]["matched_characters"], ["肖冉"])
        self.assertEqual(payload["request"]["excerpt_focus"]["missing_characters"], [])


if __name__ == "__main__":
    unittest.main()
