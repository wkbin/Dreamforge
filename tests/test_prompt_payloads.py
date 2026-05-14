#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from src.skill_support.prompt_payloads import build_distill_prompt_payload, build_relation_prompt_payload
from src.skill_support.scene_recommendations import build_scene_recommendation_bundle


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

    def test_build_distill_prompt_payload_emits_warning_when_no_requested_character_is_matched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text("前文只有旁白。没有目标角色出场。", encoding="utf-8")
            payload = build_distill_prompt_payload(
                novel_path,
                characters=["齐夏"],
                max_sentences=4,
                max_chars=200,
            )

        self.assertEqual(payload["request"]["excerpt_focus"]["matched_characters"], [])
        self.assertEqual(payload["request"]["excerpt_focus"]["missing_characters"], ["齐夏"])
        self.assertTrue(payload["meta"]["warnings"])
        self.assertIn("未匹配到任何目标角色", payload["meta"]["warnings"][0])

    def test_build_scene_recommendation_bundle_prefers_shifted_scene_when_current_beat_is_mature(self):
        bundle = build_scene_recommendation_bundle(
            {
                "mode": "observe",
                "participants": ["魏无羡", "蓝忘机", "江澄"],
                "current_scene_card_id": "scene-garden",
                "current_scene": {
                    "title": "园中僵持",
                    "location": "后园",
                    "time_hint": "傍晚",
                    "atmosphere": "气氛发紧",
                },
                "runtime_state_overview": {
                    "location": "后园",
                    "time_hint": "傍晚",
                    "beat_maturity": 78,
                    "should_offer_scene_shift": True,
                    "scene_shift_reason": "这边该说的话已经说到头了",
                    "tension": "僵着的一口气",
                },
                "transcript": [
                    {"message": "魏无羡笑意收了，没再接话。"},
                    {"message": "江澄看了他一眼，气口越发僵。"},
                ],
                "scene_cards": [
                    {
                        "card_id": "scene-garden",
                        "fields": {
                            "title": "园中僵持",
                            "location": "后园",
                            "time_hint": "傍晚",
                            "atmosphere": "气氛发紧",
                            "opening_situation": "几个人都还站在原地，谁也不肯先退。",
                            "scene_drive": "继续僵住，看谁先摊牌",
                        },
                    },
                    {
                        "card_id": "scene-hall",
                        "fields": {
                            "title": "回厅再坐",
                            "location": "前厅",
                            "time_hint": "入夜",
                            "atmosphere": "表面平静，底下还压着火",
                            "opening_situation": "人都重新入席，话题却没人肯先挑明。",
                            "scene_drive": "借换场把话逼到桌面上",
                        },
                    },
                ],
            }
        )

        payload = bundle["payload"]
        self.assertEqual(bundle["kind"], "dialogue_scene_recommendation_bundle")
        self.assertEqual(payload["recommended_card_id"], "scene-hall")
        self.assertIn("后园", payload["recommended_transition_message"])
        self.assertTrue(payload["recommended_auto_continue_message"])

    def test_build_scene_recommendation_bundle_uses_self_insert_identity_for_opening_hint(self):
        bundle = build_scene_recommendation_bundle(
            {
                "mode": "insert",
                "participants": ["林黛玉", "贾宝玉"],
                "self_profile": {
                    "display_name": "沈拂衣",
                    "scene_identity": "初到贾府的借宿客",
                },
                "scene_cards": [
                    {
                        "card_id": "scene-arrival",
                        "fields": {
                            "title": "初见偏厅",
                            "location": "偏厅",
                            "atmosphere": "初见微妙",
                            "opening_situation": "你刚被丫鬟领进门，众人的目光都落过来。",
                            "scene_drive": "先试探来意，再看彼此反应",
                        },
                    }
                ],
            }
        )

        opening = bundle["payload"]["recommended_auto_continue_message"]
        self.assertIn("沈拂衣", opening)
        self.assertIn("初到贾府的借宿客", opening)


if __name__ == "__main__":
    unittest.main()
