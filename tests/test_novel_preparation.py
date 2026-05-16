#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from src.skill_support.novel_preparation import (
    build_excerpt_payload,
    build_excerpt_payload_from_text,
    load_prepared_novel_excerpt,
    prepare_novel_excerpt,
)


class NovelPreparationTests(unittest.TestCase):
    def test_prepare_novel_excerpt_limits_sentence_count(self):
        text = "第一句。第二句。第三句。第四句。"
        excerpt = prepare_novel_excerpt(text, max_sentences=2, max_chars=100)
        self.assertEqual(excerpt, "第一句。\n第二句。")

    def test_prepare_novel_excerpt_limits_character_count(self):
        text = "很长的一句没有停顿但是依然需要被截断"
        excerpt = prepare_novel_excerpt(text, max_sentences=5, max_chars=8)
        self.assertEqual(excerpt, text[:8])

    def test_load_prepared_novel_excerpt_reads_text_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text("甲。乙。丙。", encoding="utf-8")
            excerpt = load_prepared_novel_excerpt(novel_path, max_sentences=2, max_chars=100)
            self.assertEqual(excerpt, "甲。\n乙。")

    def test_build_excerpt_payload_includes_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "红楼梦.txt"
            novel_path.write_text("宝玉。黛玉。宝钗。", encoding="utf-8")
            payload = build_excerpt_payload(novel_path, max_sentences=2, max_chars=100)
            self.assertEqual(payload["source_name"], "红楼梦.txt")
            self.assertEqual(payload["max_sentences"], 2)
            self.assertEqual(payload["excerpt"], "宝玉。\n黛玉。")


    def test_prepare_novel_excerpt_prefers_target_character_windows(self):
        text = (
            "第一章都是旁白。"
            "这一段只说甲。"
            "又一段还是甲。"
            "中间过场没有目标。"
            "到了后文，肖冉终于登场。"
            "肖冉看了齐夏一眼，没有急着说话。"
            "章晨泽站在旁边听着。"
        )
        excerpt = prepare_novel_excerpt(
            text,
            characters=["肖冉", "章晨泽"],
            max_sentences=4,
            max_chars=200,
        )
        self.assertIn("肖冉", excerpt)
        self.assertIn("章晨泽", excerpt)
        self.assertNotIn("第一章都是旁白", excerpt)

    def test_build_excerpt_payload_reports_missing_requested_characters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text("齐夏出场了。旁白继续。", encoding="utf-8")
            payload = build_excerpt_payload(
                novel_path,
                characters=["齐夏", "肖冉"],
                max_sentences=4,
                max_chars=200,
            )
            self.assertTrue(str(payload["excerpt_strategy"]).startswith("character_windows"))
            self.assertEqual(payload["matched_characters"], ["齐夏"])
            self.assertEqual(payload["missing_characters"], ["肖冉"])

    def test_build_excerpt_payload_matches_simplified_names_against_traditional_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text("齊夏看了章晨澤一眼。旁人還在說話。", encoding="utf-8")
            payload = build_excerpt_payload(
                novel_path,
                characters=["齐夏", "章晨泽"],
                max_sentences=4,
                max_chars=200,
            )

        self.assertEqual(payload["matched_characters"], ["齐夏", "章晨泽"])
        self.assertEqual(payload["missing_characters"], [])
        self.assertIn("齊夏看了章晨澤一眼", payload["excerpt"])

    def test_prepare_novel_excerpt_spreads_single_character_evidence_across_timeline(self):
        text = (
            "贾宝玉初入大观园。"
            "旁人都在说笑。"
            "贾宝玉只顾看花。"
            "中段贾宝玉为黛玉伤神。"
            "又隔了许多回。"
            "后来贾宝玉渐生倦意。"
            "结尾前贾宝玉看破繁华。"
        )
        excerpt = prepare_novel_excerpt(
            text,
            characters=["贾宝玉"],
            max_sentences=7,
            max_chars=300,
        )

        self.assertIn("贾宝玉初入大观园", excerpt)
        self.assertIn("中段贾宝玉为黛玉伤神", excerpt)
        self.assertIn("结尾前贾宝玉看破繁华", excerpt)

    def test_build_excerpt_payload_emits_stage_blocks_for_character_timeline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text(
                "贾宝玉初入大观园。"
                "旁人都在说笑。"
                "中段贾宝玉为黛玉伤神。"
                "又隔了许多回。"
                "结尾前贾宝玉看破繁华。",
                encoding="utf-8",
            )
            payload = build_excerpt_payload(
                novel_path,
                characters=["贾宝玉"],
                max_sentences=6,
                max_chars=300,
            )

        self.assertIn("贾宝玉初入大观园", payload["excerpt_stages"]["start"])
        self.assertIn("中段贾宝玉为黛玉伤神", payload["excerpt_stages"]["mid"])
        self.assertIn("结尾前贾宝玉看破繁华", payload["excerpt_stages"]["end"])

    def test_prepare_novel_excerpt_uses_mixed_character_strategy_when_window_is_too_thin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            novel_path = Path(tmpdir) / "novel.txt"
            novel_path.write_text(
                (
                    "前段旁白交代旧事。"
                    "魏无羡笑道：“先别慌。”"
                    "蓝忘机没有接话。"
                    "中段众人各怀心事。"
                    "江澄心想此事绝不简单。"
                    "旁人都说魏无羡素来最会惹事。"
                    "结尾余波未散。"
                ),
                encoding="utf-8",
            )
            payload = build_excerpt_payload(
                novel_path,
                characters=["魏无羡"],
                max_sentences=20,
                max_chars=5000,
            )

        self.assertEqual(payload["excerpt_strategy"], "character_windows_mixed")
        self.assertIn("魏无羡笑道", payload["excerpt"])
        self.assertIn("江澄心想此事绝不简单", payload["excerpt"])
        self.assertIn("结尾余波未散", payload["excerpt"])


class AliasKnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "zaomeng-skill" / "tools"))
        from _skill_support.novel_preparation import (
            _load_alias_registry,
            _resolve_character_aliases,
            _ALIAS_REGISTRY_CACHE,
        )
        self._load_alias_registry = _load_alias_registry
        self._resolve_character_aliases = _resolve_character_aliases
        self._cache = _ALIAS_REGISTRY_CACHE
        self._cache.clear()

    def tearDown(self):
        self._cache.clear()

    def _alias_file(self):
        return Path(__file__).resolve().parent.parent / "zaomeng-skill" / "character_aliases.json"

    def test_canonical_name_resolves_all_aliases(self):
        reg = self._load_alias_registry(self._alias_file())
        result = self._resolve_character_aliases(["孙悟空"], reg)
        self.assertEqual(len(result), 1)
        self.assertIn("齐天大圣", result[0])
        self.assertIn("孙行者", result[0])
        self.assertIn("孙猴子", result[0])

    def test_alias_reverse_lookup(self):
        reg = self._load_alias_registry(self._alias_file())
        result = self._resolve_character_aliases(["齐天大圣"], reg)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].startswith("孙悟空|"))

    def test_unknown_name_passes_through(self):
        reg = self._load_alias_registry(self._alias_file())
        result = self._resolve_character_aliases(["张三丰"], reg)
        self.assertEqual(result, ["张三丰"])

    def test_manual_pipe_not_overridden(self):
        reg = self._load_alias_registry(self._alias_file())
        result = self._resolve_character_aliases(["李四|李老四"], reg)
        self.assertEqual(result, ["李四|李老四"])

    def test_missing_file_graceful_degradation(self):
        reg = self._load_alias_registry("/nonexistent/path/aliases.json")
        self.assertTrue(reg.empty)
        result = self._resolve_character_aliases(["孙悟空"], reg)
        self.assertEqual(result, ["孙悟空"])

    def test_alias_matching_in_excerpt(self):
        text = "那齐天大圣一个筋斗翻了十万八千里。唐僧在后面叫道悟空快回来。孙行者笑道师父莫急。"
        payload = build_excerpt_payload_from_text(
            text,
            characters=["孙悟空"],
            max_sentences=10,
            max_chars=500,
            alias_file=self._alias_file(),
        )
        matched = payload["matched_characters"]
        self.assertTrue(any("孙悟空" in m for m in matched))
        self.assertIn("齐天大圣", payload["excerpt"])

    def test_reverse_alias_matching_in_excerpt(self):
        text = "猪八戒扛着钉耙走在前面。天蓬元帅当年何等威风。"
        payload = build_excerpt_payload_from_text(
            text,
            characters=["天蓬元帅"],
            max_sentences=10,
            max_chars=500,
            alias_file=self._alias_file(),
        )
        matched = payload["matched_characters"]
        self.assertTrue(any("猪八戒" in m for m in matched))
        self.assertIn("猪八戒", payload["excerpt"])

    def test_punctuated_alias_resolves_to_canonical_name(self):
        text = "那齐天大圣翻身而去。"
        payload = build_excerpt_payload_from_text(
            text,
            characters=["齐天·大圣"],
            max_sentences=10,
            max_chars=500,
            alias_file=self._alias_file(),
        )
        self.assertEqual(payload["requested_characters"], ["孙悟空"])
        self.assertEqual(payload["matched_characters"], ["孙悟空"])
        self.assertEqual(payload["missing_characters"], [])

    def test_duplicate_alias_inputs_dedupe_by_canonical_name(self):
        text = "旁白继续，没有任何目标角色。"
        payload = build_excerpt_payload_from_text(
            text,
            characters=["孙悟空", "齐天大圣"],
            max_sentences=10,
            max_chars=500,
            alias_file=self._alias_file(),
        )
        self.assertEqual(payload["requested_characters"], ["孙悟空"])
        self.assertEqual(payload["matched_characters"], [])
        self.assertEqual(payload["missing_characters"], ["孙悟空"])

    def test_empty_text_returns_canonical_requested_and_missing(self):
        payload = build_excerpt_payload_from_text(
            "",
            characters=["齐天大圣"],
            max_sentences=10,
            max_chars=500,
            alias_file=self._alias_file(),
        )
        self.assertEqual(payload["requested_characters"], ["孙悟空"])
        self.assertEqual(payload["matched_characters"], [])
        self.assertEqual(payload["missing_characters"], ["孙悟空"])
        self.assertEqual(payload["excerpt_strategy"], "empty")


if __name__ == "__main__":
    unittest.main()
