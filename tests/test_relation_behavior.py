#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.core.config import Config
from src.core.main import ZaomengCLI
from src.core.relation_store import MarkdownRelationStore
from src.core.relation_visualization_exporter import MermaidRelationVisualizationExporter
from src.core.runtime_factory import RuntimeDependencyOverrides, build_runtime_parts
from src.core.session_store import MarkdownSessionStore
from src.modules.distillation import NovelDistiller
from src.utils.text_parser import load_novel_text
from src.utils.file_utils import load_markdown_data, normalize_character_name, normalize_relation_key, save_markdown_data


_PROFILE_RENDERER: NovelDistiller | None = None


def render_profile_markdown(profile: dict) -> str:
    global _PROFILE_RENDERER
    if _PROFILE_RENDERER is None:
        _PROFILE_RENDERER = build_runtime_parts(Config()).distiller
    return _PROFILE_RENDERER._render_profile_md(profile)


def save_json(path: Path, data: dict) -> None:
    p = Path(path)
    if "characters" in p.parts and p.suffix == ".json":
        persona_dir = p.parent / p.stem
        persona_dir.mkdir(parents=True, exist_ok=True)
        profile = {
            "name": data.get("name", p.stem),
            "novel_id": p.parent.name,
            "source_path": "",
            "core_traits": data.get("core_traits", []),
            "values": data.get("values", {}),
            "speech_style": data.get("speech_style", ""),
            "identity_anchor": data.get("identity_anchor", ""),
            "soul_goal": data.get("soul_goal", ""),
            "worldview": data.get("worldview", ""),
            "thinking_style": data.get("thinking_style", ""),
            "temperament_type": data.get("temperament_type", ""),
            "trauma_scar": data.get("trauma_scar", ""),
            "moral_bottom_line": data.get("moral_bottom_line", ""),
            "self_cognition": data.get("self_cognition", ""),
            "stress_response": data.get("stress_response", ""),
            "others_impression": data.get("others_impression", ""),
            "restraint_threshold": data.get("restraint_threshold", ""),
            "typical_lines": data.get("typical_lines", []),
            "decision_rules": data.get("decision_rules", []),
            "life_experience": data.get("life_experience", []),
            "taboo_topics": data.get("taboo_topics", []),
            "forbidden_behaviors": data.get("forbidden_behaviors", []),
            "speech_habits": data.get("speech_habits", {"cadence": "", "signature_phrases": [], "forbidden_fillers": []}),
            "emotion_profile": data.get("emotion_profile", {"anger_style": "", "joy_style": "", "grievance_style": ""}),
            "arc": data.get("arc", {"start": {}, "mid": {}, "end": {}}),
            "evidence": data.get("evidence", {"description_count": 0, "dialogue_count": 0, "thought_count": 0, "chunk_count": 0}),
        }
        content = render_profile_markdown(profile)
        (persona_dir / "PROFILE.md").write_text(content, encoding="utf-8")
        if not (persona_dir / "MEMORY.md").exists():
            (persona_dir / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
        return
    if "relations" in p.parts and p.suffix == ".json":
        save_markdown_data(
            p.with_suffix(".md"),
            {"novel_id": p.parent.name, "relations": data},
            title="RELATION_GRAPH",
        )
        return
    save_markdown_data(p.with_suffix(".md"), data, title="DATA")


def load_json(path: Path, default=None):
    p = Path(path)
    target = p.with_suffix(".md") if p.suffix == ".json" else p
    return load_markdown_data(target, default=default)


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
                    "rules": str(root / "rules"),
                }
            }
        )
        for folder in ("characters", "relations", "sessions", "corrections", "logs", "rules"):
            (root / folder).mkdir(parents=True, exist_ok=True)
        return config

    def make_runtime_parts(self, config: Config) -> dict:
        parts = build_runtime_parts(config)
        return {
            "path_provider": parts.path_provider,
            "rulebook": parts.rulebook,
            "llm": parts.llm,
            "token_counter": parts.token_counter,
            "session_store": parts.session_store,
            "relation_store": parts.relation_store,
            "relation_visualization_exporter": parts.relation_visualization_exporter,
            "reflection": parts.reflection,
            "distiller": parts.distiller,
            "speaker": parts.speaker,
            "chat_engine": parts.chat_engine,
            "extractor": parts.extractor,
        }

    def write_profile(self, root: Path, novel_id: str, name: str, **overrides) -> Path:
        persona_dir = root / "characters" / novel_id / name
        persona_dir.mkdir(parents=True, exist_ok=True)
        profile = {
            "name": name,
            "novel_id": novel_id,
            "source_path": "",
            "core_traits": [],
            "values": {},
            "speech_style": "",
            "identity_anchor": "",
            "soul_goal": "",
            "worldview": "",
            "thinking_style": "",
            "temperament_type": "",
            "trauma_scar": "",
            "moral_bottom_line": "",
            "self_cognition": "",
            "stress_response": "",
            "others_impression": "",
            "restraint_threshold": "",
            "typical_lines": [],
            "decision_rules": [],
            "life_experience": [],
            "taboo_topics": [],
            "forbidden_behaviors": [],
            "speech_habits": {"cadence": "", "signature_phrases": [], "forbidden_fillers": []},
            "emotion_profile": {"anger_style": "", "joy_style": "", "grievance_style": ""},
            "arc": {"start": {}, "mid": {}, "end": {}},
            "evidence": {"description_count": 0, "dialogue_count": 0, "thought_count": 0, "chunk_count": 0},
        }
        profile.update(overrides)
        content = render_profile_markdown(profile)
        (persona_dir / "PROFILE.md").write_text(content, encoding="utf-8")
        if not (persona_dir / "MEMORY.md").exists():
            (persona_dir / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
        return persona_dir

    def write_relations(self, root: Path, novel_id: str, relations: dict) -> Path:
        relation_dir = root / "relations" / novel_id
        relation_dir.mkdir(parents=True, exist_ok=True)
        path = relation_dir / f"{novel_id}_relations.md"
        save_markdown_data(
            path,
            {"novel_id": novel_id, "relations": relations},
            title="RELATION_GRAPH",
        )
        return path

    def test_extract_pair_interactions_requires_same_sentence(self):
        extractor = self.make_runtime_parts(Config())["extractor"]
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

    def test_config_resolves_relative_paths_from_config_dir_not_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.yaml"
            config_path.write_text("paths:\n  characters: data/characters\n", encoding="utf-8")

            config = Config(str(config_path))

            self.assertEqual(
                Path(config.get_path("characters")).resolve(),
                (root / "data" / "characters").resolve(),
            )

    def test_cli_accepts_injected_runtime_parts_builder(self):
        parts = build_runtime_parts(Config())
        seen = {"count": 0}

        def builder(config: Config | None):
            seen["count"] += 1
            self.assertIsNotNone(config)
            return parts

        cli = ZaomengCLI(runtime_parts_builder=builder)

        self.assertIs(cli.config, parts.config)
        self.assertEqual(seen["count"], 1)

    def test_distiller_emits_progress_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            distiller = self.make_runtime_parts(config)["distiller"]
            novel_path = root / "mini.txt"
            novel_path.write_text("刘备看着关羽道：此事须从长计议。关羽答道：但凭兄长吩咐。", encoding="utf-8")

            events: list[tuple[str, dict]] = []
            result = distiller.distill(
                str(novel_path),
                characters=["刘备", "关羽"],
                progress_callback=lambda stage, payload: events.append((stage, dict(payload))),
            )

            self.assertEqual(sorted(result.keys()), ["关羽", "刘备"])
            stages = [stage for stage, _ in events]
            self.assertIn("text_loaded", stages)
            self.assertIn("characters_ready", stages)
            self.assertIn("drafting_character", stages)
            self.assertIn("refining_character", stages)
            self.assertIn("character_done", stages)
            self.assertIn("distill_done", stages)
            completed = [payload["character"] for stage, payload in events if stage == "character_done"]
            self.assertEqual(sorted(completed), ["关羽", "刘备"])

    def test_relationship_extractor_emits_graph_progress_and_exports_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            extractor = self.make_runtime_parts(config)["extractor"]
            novel_path = root / "mini.txt"
            novel_path.write_text("刘备对关羽道：贤弟且宽心。关羽答道：大哥放心。", encoding="utf-8")
            self.write_profile(root, "mini", "刘备", faction_position="蜀汉")
            self.write_profile(root, "mini", "关羽", story_role="先锋")

            events: list[tuple[str, dict]] = []
            relations = extractor.extract(
                str(novel_path),
                characters=["刘备", "关羽"],
                progress_callback=lambda stage, payload: events.append((stage, dict(payload))),
            )

            self.assertIn("_".join(sorted(["刘备", "关羽"])), relations)
            stages = [stage for stage, _ in events]
            self.assertIn("rendering_graph", stages)
            self.assertIn("graph_done", stages)
            graph_done = next(payload for stage, payload in events if stage == "graph_done")
            self.assertTrue(Path(graph_done["html_path"]).exists())
            self.assertTrue(Path(graph_done["mermaid_path"]).exists())

    def test_cli_distill_reports_progress_and_relation_graph_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            base_parts = build_runtime_parts(config)
            llm = Mock()
            llm.is_generation_enabled.return_value = True
            distiller = Mock()
            extractor = Mock()
            fake_parts = SimpleNamespace(
                config=base_parts.config,
                path_provider=base_parts.path_provider,
                rulebook=base_parts.rulebook,
                llm=llm,
                distiller=distiller,
                extractor=extractor,
            )

            novel_path = root / "mini.txt"
            novel_path.write_text("刘备与关羽同行。", encoding="utf-8")
            graph_path = base_parts.path_provider.visualization_file("mini", ".html")

            def fake_distill(novel, characters=None, output_dir=None, progress_callback=None):
                if progress_callback:
                    progress_callback("text_loaded", {"chunk_count": 3})
                    progress_callback("characters_ready", {"characters": ["刘备", "关羽"], "total": 2})
                    progress_callback("refining_character", {"character": "刘备", "index": 1, "total": 2})
                    progress_callback("character_done", {"character": "刘备", "index": 1, "total": 2})
                    progress_callback("refining_character", {"character": "关羽", "index": 2, "total": 2})
                    progress_callback("character_done", {"character": "关羽", "index": 2, "total": 2})
                    progress_callback("distill_done", {"total": 2})
                return {"刘备": {}, "关羽": {}}

            def fake_extract(novel, output_path=None, characters=None, progress_callback=None):
                graph_path.write_text("<html>graph</html>", encoding="utf-8")
                if progress_callback:
                    progress_callback("rendering_graph", {"relation_count": 1})
                    progress_callback("graph_done", {"html_path": str(graph_path)})
                return {"刘备_关羽": {"trust": 9}}

            distiller.distill.side_effect = fake_distill
            extractor.extract.side_effect = fake_extract

            cli = ZaomengCLI(runtime_parts_builder=lambda _: fake_parts)
            args = argparse.Namespace(
                force=True,
                novel=str(novel_path),
                characters="刘备,关羽",
                characters_file=None,
                output=None,
            )

            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cli._handle_distill(args)

            rendered = stdout.getvalue()
            self.assertIn("正在蒸馏角色 1/2：刘备", rendered)
            self.assertIn("已完成 2/2：关羽", rendered)
            self.assertIn("正在生成人物关系图谱", rendered)
            self.assertIn("图谱链接:", rendered)
            self.assertIn(str(graph_path), rendered)
            self.assertIn("act 模式 / observe 模式", rendered)

    def test_runtime_parts_chat_engine_factory_reuses_shared_dependencies(self):
        parts = build_runtime_parts(Config())
        engine = parts.create_chat_engine()

        self.assertIs(engine.llm, parts.llm)
        self.assertIs(engine.reflection, parts.reflection)
        self.assertIs(engine.speaker, parts.speaker)
        self.assertIs(engine.distiller, parts.distiller)
        self.assertIs(engine.rulebook, parts.rulebook)
        self.assertIs(engine.path_provider, parts.path_provider)
        self.assertIs(engine.session_store, parts.session_store)
        self.assertIs(engine.relation_store, parts.relation_store)

    def test_runtime_parts_build_chat_engine_supports_custom_patch_target(self):
        parts = build_runtime_parts(Config())
        custom_engine = Mock(name="custom_engine")
        custom_chat_engine_cls = Mock(return_value=custom_engine)

        built = parts.build_chat_engine(custom_chat_engine_cls)

        self.assertIs(built, custom_engine)
        custom_chat_engine_cls.assert_called_once_with(
            parts.config,
            llm=parts.llm,
            reflection=parts.reflection,
            speaker=parts.speaker,
            distiller=parts.distiller,
            rulebook=parts.rulebook,
            path_provider=parts.path_provider,
            session_store=parts.session_store,
            relation_store=parts.relation_store,
        )

    def test_runtime_parts_module_factories_reuse_shared_dependencies(self):
        parts = build_runtime_parts(Config())
        self.assertIs(parts.speaker.correction_service, parts.reflection)
        self.assertIs(parts.speaker.rulebook, parts.rulebook)
        self.assertIs(parts.distiller.llm_client, parts.llm)
        self.assertIs(parts.distiller.token_counter, parts.token_counter)
        self.assertIs(parts.extractor.distiller, parts.distiller)
        self.assertIs(parts.extractor.llm_client, parts.llm)
        self.assertIsInstance(parts.session_store, MarkdownSessionStore)
        self.assertIsInstance(parts.relation_store, MarkdownRelationStore)
        self.assertIsInstance(parts.relation_visualization_exporter, MermaidRelationVisualizationExporter)
        self.assertIs(parts.extractor.relation_store, parts.relation_store)
        self.assertIs(parts.extractor.relation_visualization_exporter, parts.relation_visualization_exporter)

    def test_runtime_parts_accept_dependency_overrides(self):
        config = Config()
        base_parts = build_runtime_parts(config)
        overrides = RuntimeDependencyOverrides(
            reflection=base_parts.reflection,
            speaker=base_parts.speaker,
        )

        overridden_parts = build_runtime_parts(config, overrides=overrides)

        self.assertIs(overridden_parts.reflection, base_parts.reflection)
        self.assertIs(overridden_parts.speaker, base_parts.speaker)
        self.assertIsNotNone(overridden_parts.distiller)
        self.assertIsNotNone(overridden_parts.extractor)

    def test_runtime_parts_construct_modules_lazily(self):
        with (
            patch("src.core.runtime_parts.ReflectionEngine.from_runtime_parts") as reflection_factory,
            patch("src.core.runtime_parts.NovelDistiller.from_runtime_parts") as distiller_factory,
            patch("src.core.runtime_parts.Speaker.from_runtime_parts") as speaker_factory,
            patch("src.core.runtime_parts.RelationshipExtractor.from_runtime_parts") as extractor_factory,
            patch("src.core.runtime_parts.RuntimeParts.build_chat_engine") as chat_engine_factory,
        ):
            reflection_factory.return_value = Mock(name="reflection")
            distiller_factory.return_value = Mock(name="distiller")
            speaker_factory.return_value = Mock(name="speaker")
            extractor_factory.return_value = Mock(name="extractor")
            chat_engine_factory.return_value = Mock(name="chat_engine")

            parts = build_runtime_parts(Config())

            reflection_factory.assert_not_called()
            distiller_factory.assert_not_called()
            speaker_factory.assert_not_called()
            extractor_factory.assert_not_called()
            chat_engine_factory.assert_not_called()

            self.assertIs(parts.reflection, reflection_factory.return_value)
            self.assertIs(parts.distiller, distiller_factory.return_value)
            self.assertIs(parts.speaker, speaker_factory.return_value)
            self.assertIs(parts.extractor, extractor_factory.return_value)
            self.assertIs(parts.chat_engine, chat_engine_factory.return_value)

            self.assertEqual(reflection_factory.call_count, 1)
            self.assertEqual(distiller_factory.call_count, 1)
            self.assertEqual(speaker_factory.call_count, 1)
            self.assertEqual(extractor_factory.call_count, 1)
            self.assertEqual(chat_engine_factory.call_count, 1)

    def test_runtime_parts_fork_reuses_foundational_dependencies(self):
        parts = build_runtime_parts(Config())

        forked = parts.fork()

        self.assertIs(forked.config, parts.config)
        self.assertIs(forked.path_provider, parts.path_provider)
        self.assertIs(forked.rulebook, parts.rulebook)
        self.assertIs(forked.llm, parts.llm)
        self.assertIs(forked.token_counter, parts.token_counter)
        self.assertIs(forked.session_store, parts.session_store)
        self.assertIs(forked.relation_store, parts.relation_store)
        self.assertIs(forked.relation_visualization_exporter, parts.relation_visualization_exporter)
        self.assertIsNot(forked, parts)
        self.assertIsNot(forked.reflection, parts.reflection)
        self.assertIsNot(forked.distiller, parts.distiller)
        self.assertIsNot(forked.speaker, parts.speaker)
        self.assertIsNot(forked.extractor, parts.extractor)

    def test_runtime_parts_fork_accepts_incremental_overrides(self):
        parts = build_runtime_parts(Config())
        custom_reflection = Mock(name="custom_reflection")
        custom_speaker = Mock(name="custom_speaker")

        forked = parts.fork(
            RuntimeDependencyOverrides(
                reflection=custom_reflection,
                speaker=custom_speaker,
            )
        )

        self.assertIs(forked.path_provider, parts.path_provider)
        self.assertIs(forked.rulebook, parts.rulebook)
        self.assertIs(forked.llm, parts.llm)
        self.assertIs(forked.token_counter, parts.token_counter)
        self.assertIs(forked.session_store, parts.session_store)
        self.assertIs(forked.relation_store, parts.relation_store)
        self.assertIs(forked.relation_visualization_exporter, parts.relation_visualization_exporter)
        self.assertIs(forked.reflection, custom_reflection)
        self.assertIs(forked.speaker, custom_speaker)
        self.assertIsNot(forked.distiller, parts.distiller)
        self.assertIsNot(forked.extractor, parts.extractor)

    def test_cli_fresh_runtime_parts_forks_default_runtime_parts(self):
        cli = ZaomengCLI()

        fresh = cli._fresh_runtime_parts()

        self.assertIsNot(fresh, cli.parts)
        self.assertIs(fresh.path_provider, cli.parts.path_provider)
        self.assertIs(fresh.rulebook, cli.parts.rulebook)
        self.assertIs(fresh.llm, cli.parts.llm)
        self.assertIs(fresh.token_counter, cli.parts.token_counter)
        self.assertIs(fresh.session_store, cli.parts.session_store)
        self.assertIs(fresh.relation_store, cli.parts.relation_store)
        self.assertIs(fresh.relation_visualization_exporter, cli.parts.relation_visualization_exporter)
        self.assertIsNot(fresh.chat_engine, cli.parts.chat_engine)

    def test_runtime_dependency_overrides_merge_prefers_explicit_values(self):
        base = RuntimeDependencyOverrides(
            path_provider=Mock(name="base_path_provider"),
            llm=Mock(name="base_llm"),
        )
        incoming = RuntimeDependencyOverrides(
            llm=Mock(name="incoming_llm"),
            speaker=Mock(name="incoming_speaker"),
        )

        merged = base.merged_with(incoming)

        self.assertIs(merged.path_provider, base.path_provider)
        self.assertIs(merged.llm, incoming.llm)
        self.assertIs(merged.speaker, incoming.speaker)

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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            distiller = self.make_runtime_parts(config)["distiller"]
            result = distiller.distill(
                str(novel_path),
                characters=["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"],
            )

            self.assertGreater(result["\u6797\u9edb\u7389"]["evidence"]["description_count"], 0)
            self.assertGreater(result["\u8d3e\u5b9d\u7389"]["evidence"]["dialogue_count"], 0)

    def test_relationship_extractor_matches_two_char_aliases(self):
        extractor = self.make_runtime_parts(Config())["extractor"]
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

    def test_profile_markdown_round_trips_extended_persona_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            persona_dir = self.write_profile(
                root,
                "mini",
                "\u6797\u9edb\u7389",
                timeline_stage="\u524d\u671f",
                role_tags=["\u6838\u5fc3\u4e3b\u89d2", "\u60b2\u5267\u578b"],
                world_belong="\u8d3e\u5e9c\u5185\u5b85",
                rule_view="\u8868\u9762\u987a\u7740\u95fa\u9601\u79e9\u5e8f\uff0c\u5b9e\u5219\u5bf9\u4eba\u60c5\u51b7\u6696\u66f4\u654f\u611f",
                appearance_feature="\u8eab\u5f62\u7626\u524a\uff0c\u7709\u76ee\u95f4\u5e38\u5e26\u75c5\u610f\u4e0e\u51b7\u610f\u3002",
                habit_action="\u8bdd\u5230\u5fc3\u4e8b\u65f6\u5148\u987f\u4e00\u987f\uff0c\u518d\u8f7b\u8f7b\u53cd\u95ee\u3002",
                interest_claim="\u5b88\u4f4f\u81ea\u5c0a\u3001\u771f\u5fc3\u4e0e\u5c11\u6570\u91cd\u8981\u5173\u7cfb",
                carry_style="\u5bf9\u5916\u4eba\u5148\u51b7\u7740\uff0c\u5bf9\u5728\u610f\u4e4b\u4eba\u53cd\u800c\u66f4\u5bb9\u6613\u9732\u51fa\u5c16\u9510",
                emotion_model="\u60c5\u7eea\u6765\u5f97\u7ec6\u5bc6\uff0c\u591a\u85cf\u5728\u8bed\u6c14\u548c\u8ddd\u79bb\u91cc\u3002",
                ooc_redline="\u4e0d\u4f1a\u65e0\u7f18\u65e0\u6545\u5730\u8f7b\u8d31\u771f\u5fc3\uff0c\u4e5f\u4e0d\u4f1a\u7a81\u7136\u53d8\u6210\u70ed\u70c8\u5f20\u626c\u7684\u4eba\u3002",
                evidence_source="chunk_01\uff1bchunk_03",
                contradiction_note="\u524d\u671f\u66f4\u504f\u8bd5\u63a2\uff0c\u60c5\u611f\u88ab\u523a\u4e2d\u65f6\u8bdd\u4f1a\u66f4\u9510\u3002",
                temperament_type="\u9ad8\u654f\u611f\u3001\u5916\u51b7\u5185\u70ed\u578b",
                trauma_scar="\u5bc4\u5c45\u4e0e\u5931\u6043\u7559\u4e0b\u7684\u65e7\u4f24\uff0c\u5728\u88ab\u8f7b\u6162\u65f6\u4f1a\u660e\u663e\u53d1\u4f5c\u3002",
                moral_bottom_line="\u4e0d\u80fd\u62ff\u771f\u5fc3\u4e0e\u65e0\u8f9c\u8005\u5f53\u7b79\u7801\u3002",
                self_cognition="\u77e5\u9053\u81ea\u5df1\u654f\u611f\uff0c\u4e5f\u77e5\u9053\u81ea\u5df1\u4e0d\u4f1a\u8f7b\u6613\u793a\u5f31\u3002",
                stress_response="\u8d8a\u5230\u9ad8\u538b\u65f6\u8d8a\u4f1a\u628a\u60c5\u7eea\u538b\u4f4e\uff0c\u8bdd\u66f4\u8f7b\u4e5f\u66f4\u950b\u5229\u3002",
                others_impression="\u65c1\u4eba\u591a\u534a\u5148\u89c9\u5f97\u5979\u6e05\u51b7\u96be\u8fd1\uff0c\u719f\u4e86\u624d\u77e5\u5176\u771f\u60c5\u5f88\u6df1\u3002",
                restraint_threshold="\u5e73\u65f6\u6781\u80fd\u514b\u5236\uff0c\u552f\u72ec\u81ea\u5c0a\u4e0e\u771f\u5fc3\u88ab\u8e29\u65f6\u4f1a\u5931\u63a7\u3002",
            )

            engine = self.make_runtime_parts(config)["chat_engine"]
            loaded = engine._load_profile_markdown(persona_dir / "PROFILE.md")

            self.assertEqual(loaded["temperament_type"], "\u9ad8\u654f\u611f\u3001\u5916\u51b7\u5185\u70ed\u578b")
            self.assertEqual(loaded["timeline_stage"], "\u524d\u671f")
            self.assertIn("\u60b2\u5267\u578b", loaded["role_tags"])
            self.assertIn("\u8d3e\u5e9c", loaded["world_belong"])
            self.assertIn("\u987a\u7740", loaded["rule_view"])
            self.assertIn("\u7626\u524a", loaded["appearance_feature"])
            self.assertIn("\u53cd\u95ee", loaded["habit_action"])
            self.assertIn("\u771f\u5fc3", loaded["interest_claim"])
            self.assertIn("\u5916\u4eba", loaded["carry_style"])
            self.assertIn("\u8bed\u6c14", loaded["emotion_model"])
            self.assertIn("\u8f7b\u8d31", loaded["ooc_redline"])
            self.assertIn("chunk_01", loaded["evidence_source"])
            self.assertIn("\u524d\u671f", loaded["contradiction_note"])
            self.assertIn("\u65e7\u4f24", loaded["trauma_scar"])
            self.assertIn("\u65e0\u8f9c\u8005", loaded["moral_bottom_line"])
            self.assertIn("\u81ea\u5df1\u654f\u611f", loaded["self_cognition"])
            self.assertIn("\u9ad8\u538b", loaded["stress_response"])
            self.assertIn("\u6e05\u51b7\u96be\u8fd1", loaded["others_impression"])
            self.assertIn("\u81ea\u5c0a", loaded["restraint_threshold"])

    def test_distiller_filters_shared_scene_evidence_toward_centered_character(self):
        distiller = self.make_runtime_parts(Config())["distiller"]
        alias_map = {
            "\u9f50\u590f": ["\u9f50\u590f"],
            "\u4e54\u5bb6\u52b2": ["\u4e54\u5bb6\u52b2"],
            "\u5730\u9f20": ["\u5730\u9f20"],
        }

        evidence_map, _ = distiller._extract_from_chunk(
            "\u9f50\u590f\u770b\u4e86\u4e54\u5bb6\u52b2\u4e00\u773c\uff0c\u5730\u9f20\u4ecd\u7136\u5b88\u5728\u89c4\u5219\u724c\u524d\u3002"
            "\u4e54\u5bb6\u52b2\u51b7\u7b11\u4e86\u4e00\u58f0\uff0c\u62ac\u624b\u5c31\u8981\u9876\u56de\u53bb\u3002"
            "\u5730\u9f20\u5fc3\u91cc\u5374\u628a\u6bcf\u4e00\u6761\u7ec6\u5219\u90fd\u8fc7\u4e86\u4e00\u904d\u3002",
            alias_map,
        )

        self.assertTrue(any("\u9f50\u590f" in line for line in evidence_map["\u9f50\u590f"]["descriptions"]))
        self.assertFalse(any("\u9f50\u590f" in line for line in evidence_map["\u4e54\u5bb6\u52b2"]["descriptions"]))
        self.assertTrue(any("\u4e54\u5bb6\u52b2" in line for line in evidence_map["\u4e54\u5bb6\u52b2"]["descriptions"]))
        self.assertTrue(any("\u5730\u9f20" in line for line in evidence_map["\u5730\u9f20"]["thoughts"]))

    def test_distiller_builds_evidence_first_profile_scaffold(self):
        distiller = self.make_runtime_parts(Config())["distiller"]

        with patch.object(distiller, "_infer_archetype", return_value="steady_supporter"):
            profile = distiller._build_profile(
                "\u5173\u7fbd",
                {
                    "descriptions": ["\u5173\u7fbd\u7a33\u7a33\u5730\u5361\u5728\u540e\u8def\uff0c\u5148\u628a\u4eba\u90fd\u63a5\u5e94\u4f4f\u3002"],
                    "dialogues": ["\u524d\u9762\u4f60\u53ea\u7ba1\u5f80\u524d\uff0c\u540e\u8def\u6211\u66ff\u4f60\u770b\u4f4f\u3002"],
                    "thoughts": ["\u4ed6\u6700\u600e\u4e48\u90fd\u4e0d\u80fd\u8ba9\u540c\u884c\u7684\u4eba\u65ad\u5728\u8fd9\u91cc\u3002"],
                    "timeline": [],
                },
                arc_values=[],
            )

        self.assertEqual(profile["archetype"], "steady_supporter")
        self.assertTrue(profile["core_traits"])
        self.assertTrue(profile["decision_rules"])
        self.assertTrue(profile["life_experience"])
        self.assertTrue(profile["background_imprint"])
        self.assertTrue(profile["arc_summary"].strip())
        self.assertIn("\u5173\u7fbd", "".join(profile["life_experience"]))

    def test_distiller_avoids_narrative_fragments_in_core_worldview_fields(self):
        distiller = self.make_runtime_parts(Config())["distiller"]

        with (
            patch.object(distiller, "_infer_archetype", return_value="steady_supporter"),
            patch.object(distiller, "_infer_worldview", return_value="人情比功名更重，真心不能拿来铺垫场面。"),
            patch.object(distiller, "_infer_belief_anchor", return_value="真心不可轻负。"),
            patch.object(distiller, "_infer_moral_bottom_line", return_value="决不会主动拿真情去换世俗体面。"),
            patch.object(distiller, "_infer_restraint_threshold", return_value="平时压得住，唯独真心与自尊同时受损时会明显失控。"),
        ):
            profile = distiller._build_profile(
                "\u8d3e\u5b9d\u7389",
                {
                    "descriptions": ["大家想着，宝玉却等不得了，也不等贾政的命，便说道：“旧诗有云："],
                    "dialogues": [],
                    "thoughts": [
                        "转过大厅，宝玉心里还自狐疑，只听墙角边一阵呵呵大笑，回头只见薛蟠拍着手笑了出来，笑道：“要不说姨夫叫你，你那里出来的这么快！"
                    ],
                    "timeline": [],
                },
                arc_values=[],
            )

        self.assertEqual(profile["worldview"], "人情比功名更重，真心不能拿来铺垫场面。")
        self.assertEqual(profile["belief_anchor"], "真心不可轻负。")
        self.assertEqual(profile["moral_bottom_line"], "决不会主动拿真情去换世俗体面。")
        self.assertEqual(profile["restraint_threshold"], "平时压得住，唯独真心与自尊同时受损时会明显失控。")
        self.assertNotIn("旧诗有云", profile["worldview"])
        self.assertNotIn("薛蟠", profile["restraint_threshold"])

    def test_distiller_loads_character_hints_from_novel_specific_rules_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            hint_dir = root / "rules" / "character_hints"
            hint_dir.mkdir(parents=True, exist_ok=True)
            (hint_dir / "shirizhongyan.md").write_text(
                "---\n"
                "character_hints:\n"
                "  齐夏:\n"
                "    aliases: [齐夏]\n"
                "    temperament_type: 冷静拆局、控盘压场型\n"
                "    stress_response: 压力越大越会先拆规则再找破口。\n"
                "    others_impression: 外人会先觉得他过于冷静，像在算人。\n"
                "---\n\n"
                "# CHARACTER_HINTS\n",
                encoding="utf-8",
            )

            distiller = self.make_runtime_parts(config)["distiller"]
            distiller._active_character_hints = distiller._load_novel_character_hints("shirizhongyan")
            profile = distiller._apply_character_hint({"name": "齐夏"}, distiller._resolve_character_hint("齐夏"))

            self.assertEqual(profile["temperament_type"], "冷静拆局、控盘压场型")
            self.assertIn("拆规则", profile["stress_response"])
            self.assertIn("冷静", profile["others_impression"])

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

            engine = self.make_runtime_parts(config)["chat_engine"]
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
            reflection = self.make_runtime_parts(config)["reflection"]

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
        distiller = self.make_runtime_parts(Config())["distiller"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
            engine._generate_reply = Mock(return_value="\u4f60\u8bf4\u5f97\u662f\u3002")
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

            engine = self.make_runtime_parts(config)["chat_engine"]
            engine._generate_reply = Mock(side_effect=lambda **kwargs: f"{kwargs['responder']}\u56de\u5e94")
            session = engine.create_session("sanguo.txt", "observe")

            replies = engine.observe_once(session, "\u5218\u5907\uff1a\u4e8c\u4f4d\u8d24\u5f1f\uff0c\u4eca\u65e5\u603b\u7b97\u5f97\u7247\u523b\u6e05\u95f2\u3002")

            self.assertEqual(sorted(name for name, _ in replies), ["\u5173\u7fbd", "\u5f20\u98de"])
            restored = engine.restore_session(session["id"])
            self.assertEqual(restored["history"][0]["speaker"], "\u5218\u5907")
            self.assertEqual(restored["history"][0]["message"], "\u4e8c\u4f4d\u8d24\u5f1f\uff0c\u4eca\u65e5\u603b\u7b97\u5f97\u7247\u523b\u6e05\u95f2\u3002")

    def test_insert_once_uses_self_identity_and_returns_character_replies(self):
        class CaptureLLM:
            def __init__(self):
                self.calls = []

            def chat_completion(self, messages, model=None, temperature=None, max_tokens=None, stream=False):
                self.calls.append(messages)
                return {"content": "姑娘既来了，便坐下说话。"}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"chat_engine": {"generation_mode": "llm-only", "max_speakers_per_turn": 1}})

            self.write_profile(root, "hongloumeng", "\u6797\u9edb\u7389", speech_style="\u514b\u5236", values={"\u5584\u826f": 8})
            self.write_profile(root, "hongloumeng", "\u8d3e\u5b9d\u7389", speech_style="\u76f4\u767d", values={"\u81ea\u7531": 8})

            engine = self.make_runtime_parts(config)["chat_engine"]
            capture_llm = CaptureLLM()
            engine.llm = capture_llm
            session = engine.create_session("hongloumeng.txt", "insert")
            session["state"]["self_insert"] = {
                "display_name": "\u963f\u9752",
                "scene_identity": "\u521d\u5230\u8d3e\u5e9c\u7684\u65b0\u5ba2",
                "interaction_style": "immersive",
                "plot_agency": "scene",
            }

            replies = engine.insert_once(session, "\u9edb\u7389\u59d1\u5a18\uff0c\u6211\u521d\u6765\u6b64\u5904\uff0c\u80fd\u5426\u8bf7\u4f60\u6307\u4e2a\u8def\uff1f")

            self.assertEqual(replies, [("\u6797\u9edb\u7389", "姑娘既来了，便坐下说话。")])
            self.assertEqual(len(capture_llm.calls), 1)
            system_prompt = capture_llm.calls[0][0]["content"]
            user_prompt = capture_llm.calls[0][1]["content"]
            self.assertIn("\u81ea\u6211\u4ee3\u5165\u7528\u6237\u6863\u6848", user_prompt)
            self.assertIn("\u79f0\u547c: \u963f\u9752", user_prompt)
            self.assertIn("\u573a\u666f\u8eab\u4efd: \u521d\u5230\u8d3e\u5e9c\u7684\u65b0\u5ba2", user_prompt)
            self.assertIn("\u5267\u60c5\u5f71\u54cd\u8303\u56f4: scene", user_prompt)
            self.assertIn("\u5f53\u524d\u4e3b\u8981\u56de\u5e94\u5bf9\u8c61: \u963f\u9752", user_prompt)
            self.assertIn("\u4f1a\u8bdd\u6a21\u5f0f: insert", user_prompt)
            self.assertIn("\u4f60\u73b0\u5728\u53ea\u626e\u6f14 \u6797\u9edb\u7389", system_prompt)

    def test_insert_once_updates_self_insert_card_from_first_message(self):
        class CaptureLLM:
            def __init__(self):
                self.calls = []

            def chat_completion(self, messages, model=None, temperature=None, max_tokens=None, stream=False):
                self.calls.append(messages)
                return {"content": "既然是新客，先进来坐吧。"}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"chat_engine": {"generation_mode": "llm-only", "max_speakers_per_turn": 1}})

            self.write_profile(root, "hongloumeng", "\u6797\u9edb\u7389", speech_style="\u514b\u5236", values={"\u5584\u826f": 8})

            engine = self.make_runtime_parts(config)["chat_engine"]
            capture_llm = CaptureLLM()
            engine.llm = capture_llm
            session = engine.create_session("hongloumeng.txt", "insert")

            replies = engine.insert_once(session, "\u6211\u53eb\u963f\u9752\uff0c\u6211\u662f\u521d\u5230\u8d3e\u5e9c\u7684\u65b0\u5ba2\uff0c\u60f3\u5148\u62dc\u4f1a\u9edb\u7389\u59d1\u5a18\u3002")

            self.assertEqual(replies, [("\u6797\u9edb\u7389", "既然是新客，先进来坐吧。")])
            self.assertEqual(session["state"]["self_insert"]["display_name"], "\u963f\u9752")
            self.assertEqual(session["state"]["self_insert"]["scene_identity"], "\u521d\u5230\u8d3e\u5e9c\u7684\u65b0\u5ba2")
            user_prompt = capture_llm.calls[0][1]["content"]
            self.assertIn("\u79f0\u547c: \u963f\u9752", user_prompt)
            self.assertIn("\u573a\u666f\u8eab\u4efd: \u521d\u5230\u8d3e\u5e9c\u7684\u65b0\u5ba2", user_prompt)

    def test_build_session_summary_includes_insert_state_and_latest_responses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            self.write_profile(root, "hongloumeng", "\u6797\u9edb\u7389", speech_style="\u514b\u5236", values={"\u5584\u826f": 8})
            self.write_profile(root, "hongloumeng", "\u8d3e\u5b9d\u7389", speech_style="\u76f4\u767d", values={"\u81ea\u7531": 8})

            engine = self.make_runtime_parts(config)["chat_engine"]
            session = engine.create_session("hongloumeng.txt", "insert")
            session["state"]["selected_characters"] = ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"]
            session["state"]["self_insert"] = {
                "display_name": "\u963f\u9752",
                "scene_identity": "\u8d3e\u5e9c\u65b0\u5ba2",
                "interaction_style": "immersive",
                "plot_agency": "light",
            }
            session["history"] = [
                {"speaker": "\u963f\u9752", "message": "\u521d\u6765\u8d35\u5e9c\uff0c\u8fd8\u8bf7\u591a\u591a\u6307\u6559\u3002", "ts": 1},
                {"speaker": "\u6797\u9edb\u7389", "target": "\u963f\u9752", "message": "\u4e0d\u5fc5\u62d8\u793c\u3002", "ts": 2},
            ]

            summary = engine.build_session_summary(
                session,
                latest_responses=[("\u6797\u9edb\u7389", "\u4e0d\u5fc5\u62d8\u793c\u3002")],
            )

            self.assertEqual(summary["mode"], "insert")
            self.assertEqual(summary["participants"], ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"])
            self.assertEqual(summary["self_insert"]["display_name"], "\u963f\u9752")
            self.assertEqual(summary["history_count"], 2)
            self.assertEqual(summary["last_entry"]["speaker"], "\u6797\u9edb\u7389")
            self.assertEqual(summary["latest_responses"][0]["speaker"], "\u6797\u9edb\u7389")
            self.assertTrue(summary["artifacts"]["session_file"].endswith(f"{session['id']}.md"))

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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
            engine._generate_reply = Mock(return_value="\u4e0d\u52b3\u6302\u5ff5\uff0c\u6211\u4eca\u65e5\u8fd8\u597d\u3002")
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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
            engine._generate_reply = Mock(return_value="\u56de\u5e94")
            session = engine.create_session("hongloumeng.txt", "act")

            first = engine.act_once(session, "\u8d3e\u5b9d\u7389", "\u6797\u59b9\u59b9\uff0c\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f")
            second = engine.act_once(session, "\u8d3e\u5b9d\u7389", "\u6211\u53ea\u662f\u60f3\u518d\u95ee\u4f60\u4e00\u53e5\u3002")

            self.assertEqual(first, [("\u6797\u9edb\u7389", "\u56de\u5e94")])
            self.assertEqual(second, [("\u6797\u9edb\u7389", "\u56de\u5e94")])
            self.assertEqual(session["state"]["focus_targets"]["\u8d3e\u5b9d\u7389"], "\u6797\u9edb\u7389")

    def test_act_once_supports_group_participation_with_multiple_replies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"chat_engine": {"max_speakers_per_turn": 4}})

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

            engine = self.make_runtime_parts(config)["chat_engine"]
            engine._generate_reply = Mock(side_effect=lambda **kwargs: f"{kwargs['responder']}\u56de\u5e94")
            session = engine.create_session("hongloumeng.txt", "act")
            session["state"]["controlled_character"] = "\u8d3e\u5b9d\u7389"
            session["state"]["selected_characters"] = ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389", "\u859b\u5b9d\u9497"]

            replies = engine.act_once(session, "\u8d3e\u5b9d\u7389", "\u4eca\u65e5\u98ce\u597d\uff0c\u6211\u4eec\u5c31\u5728\u8fd9\u91cc\u5750\u5750\u8bf4\u8bdd\u3002")

            self.assertEqual(len(replies), 2)
            self.assertEqual({name for name, _ in replies}, {"\u6797\u9edb\u7389", "\u859b\u5b9d\u9497"})

    def test_act_once_passes_persona_bundle_and_relation_overlay_into_llm_messages(self):
        class CaptureLLM:
            def __init__(self):
                self.calls = []

            def chat_completion(self, messages, model=None, temperature=None, max_tokens=None, stream=False):
                self.calls.append(messages)
                return {"content": "宝玉，我今日还好。"}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"chat_engine": {"generation_mode": "llm-only"}})

            self.write_profile(
                root,
                "hongloumeng",
                "\u6797\u9edb\u7389",
                speech_style="\u514b\u5236",
                soul_goal="\u5b88\u4f4f\u4e0d\u80af\u660e\u8bf4\u7684\u771f\u5fc3",
                thinking_style="\u5148\u8bd5\u63a2\u518d\u56de\u5e94",
                values={"\u5584\u826f": 8},
            )
            self.write_profile(
                root,
                "hongloumeng",
                "\u8d3e\u5b9d\u7389",
                speech_style="\u76f4\u767d",
                soul_goal="\u628a\u5728\u610f\u7684\u4eba\u7559\u5728\u8eab\u8fb9",
                values={"\u81ea\u7531": 8},
            )

            persona_dir = root / "characters" / "hongloumeng" / "\u6797\u9edb\u7389"
            (persona_dir / "STYLE.md").write_text(
                "# STYLE\n\n"
                "- speech_style: \u8f7b\u58f0\u7ec6\u8bed\uff0c\u8bdd\u91cc\u85cf\u950b\n"
                "- signature_phrases: \u4e5f\u7f62\uff1b\u5012\u4e5f\u672a\u5fc5\n",
                encoding="utf-8",
            )
            (persona_dir / "MEMORY.md").write_text(
                "# MEMORY\n\n"
                "- user_edits: \u8bb0\u4f4f\uff1a\u6797\u9edb\u7389\u8bf4\u8bdd\u8981\u66f4\u77ed\uff0c\u4e0d\u8981\u8bf4\u6559\n"
                "- notable_interactions: \u8fd1\u6765\u548c\u5b9d\u7389\u591a\u534a\u5148\u8bd5\u63a2\uff0c\u518d\u6162\u6162\u8f6f\u4e0b\u6765\n",
                encoding="utf-8",
            )
            (persona_dir / "RELATIONS.md").write_text(
                "# RELATIONS\n\n"
                "## \u8d3e\u5b9d\u7389\n"
                "- trust: 9\n"
                "- affection: 10\n"
                "- appellation_to_target: \u5b9d\u7389\n"
                "- typical_interaction: \u5148\u8bd5\u63a2\uff0c\u518d\u77ed\u6682\u7f13\u548c\n"
                "- hidden_attitude: \u5634\u4e0a\u85cf\u523a\uff0c\u5fc3\u91cc\u5176\u5b9e\u5728\u610f\n",
                encoding="utf-8",
            )

            engine = self.make_runtime_parts(config)["chat_engine"]
            capture_llm = CaptureLLM()
            engine.llm = capture_llm
            session = engine.create_session("hongloumeng.txt", "act")

            replies = engine.act_once(session, "\u8d3e\u5b9d\u7389", "\u6797\u59b9\u59b9\uff0c\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f")

            self.assertEqual(replies, [("\u6797\u9edb\u7389", "宝玉，我今日还好。")])
            self.assertEqual(len(capture_llm.calls), 1)
            system_prompt = capture_llm.calls[0][0]["content"]
            user_prompt = capture_llm.calls[0][1]["content"]
            self.assertIn("\u5b88\u4f4f\u4e0d\u80af\u660e\u8bf4\u7684\u771f\u5fc3", system_prompt)
            self.assertIn("\u8f7b\u58f0\u7ec6\u8bed\uff0c\u8bdd\u91cc\u85cf\u950b", system_prompt)
            self.assertIn("\u8bb0\u4f4f\uff1a\u6797\u9edb\u7389\u8bf4\u8bdd\u8981\u66f4\u77ed\uff0c\u4e0d\u8981\u8bf4\u6559", system_prompt)
            self.assertIn("\u5f53\u524d\u4e3b\u8981\u5bf9\u8c61: \u5b9d\u7389", system_prompt)
            self.assertIn("trust=9, affection=10", system_prompt)
            self.assertIn("\u5148\u8bd5\u63a2\uff0c\u518d\u77ed\u6682\u7f13\u548c", system_prompt)
            self.assertIn("\u5f53\u524d\u4e3b\u8981\u56de\u5e94\u5bf9\u8c61: \u8d3e\u5b9d\u7389", user_prompt)
            self.assertIn("\u8d3e\u5b9d\u7389: \u6797\u59b9\u59b9\uff0c\u4eca\u65e5\u53ef\u5927\u5b89\u4e86\uff1f", user_prompt)

    def test_observe_once_passes_group_relation_overview_into_llm_messages(self):
        class CaptureLLM:
            def __init__(self):
                self.calls = []

            def chat_completion(self, messages, model=None, temperature=None, max_tokens=None, stream=False):
                self.calls.append(messages)
                return {"content": "我先听明白，再接这句话。"}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"chat_engine": {"generation_mode": "llm-only", "max_speakers_per_turn": 1}})

            self.write_profile(root, "sanguo", "\u5218\u5907", speech_style="\u514b\u5236", values={"\u8d23\u4efb": 9})
            self.write_profile(
                root,
                "sanguo",
                "\u5173\u7fbd",
                speech_style="\u51b7\u9759\u7b80\u77ed",
                soul_goal="\u628a\u8ba4\u4e0b\u7684\u60c5\u5206\u5b88\u5230\u5e95",
                values={"\u5fe0\u8bda": 9},
            )
            self.write_profile(root, "sanguo", "\u5f20\u98de", speech_style="\u76f4\u767d", values={"\u52c7\u6c14": 9})
            self.write_relations(
                root,
                "sanguo",
                {
                    "\u5218\u5907_\u5173\u7fbd": {"trust": 9, "affection": 8, "hostility": 0, "power_gap": 0},
                    "\u5f20\u98de_\u5173\u7fbd": {"trust": 7, "affection": 6, "hostility": 1, "power_gap": 0},
                },
            )

            engine = self.make_runtime_parts(config)["chat_engine"]
            capture_llm = CaptureLLM()
            engine.llm = capture_llm
            session = engine.create_session("sanguo.txt", "observe")

            replies = engine.observe_once(session, "\u5218\u5907\uff1a\u4e91\u957f\uff0c\u4f60\u770b\u4eca\u65e5\u8fd9\u5c40\u9762\u8be5\u600e\u4e48\u7a33\u4f4f\uff1f")

            self.assertEqual(replies, [("\u5173\u7fbd", "我先听明白，再接这句话。")])
            self.assertEqual(len(capture_llm.calls), 1)
            system_prompt = capture_llm.calls[0][0]["content"]
            user_prompt = capture_llm.calls[0][1]["content"]
            self.assertIn("\u628a\u8ba4\u4e0b\u7684\u60c5\u5206\u5b88\u5230\u5e95", system_prompt)
            self.assertIn("\u7fa4\u4f53\u5173\u7cfb\u6982\u89c8", system_prompt)
            self.assertIn("\u5218\u5907(trust=9,aff=8,host=0)", system_prompt)
            self.assertIn("\u5f20\u98de(trust=7,aff=6,host=1)", system_prompt)
            self.assertIn("\u4f1a\u8bdd\u6a21\u5f0f: observe", user_prompt)
            self.assertIn("\u5f53\u524d\u8f6e\u53d1\u8d77\u8005: \u5218\u5907", user_prompt)

    def test_speaker_avoids_dumping_typical_line_as_reply(self):
        speaker = self.make_runtime_parts(Config())["speaker"]
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
        speaker = self.make_runtime_parts(Config())["speaker"]
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
        speaker = self.make_runtime_parts(Config())["speaker"]
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
        speaker = self.make_runtime_parts(Config())["speaker"]
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
        speaker = self.make_runtime_parts(Config())["speaker"]
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

            distiller = self.make_runtime_parts(config)["distiller"]
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

            distiller = self.make_runtime_parts(config)["distiller"]
            distiller.distill(str(novel_path), characters=["\u5218\u5907"])

            persona_dir = root / "characters" / "mini" / "\u5218\u5907"
            self.assertTrue((persona_dir / "PROFILE.generated.md").exists())
            self.assertTrue((persona_dir / "PROFILE.md").exists())
            self.assertTrue((persona_dir / "SOUL.generated.md").exists())
            self.assertTrue((persona_dir / "IDENTITY.generated.md").exists())
            self.assertTrue((persona_dir / "AGENTS.generated.md").exists())
            self.assertTrue((persona_dir / "MEMORY.generated.md").exists())
            self.assertTrue((persona_dir / "NAVIGATION.generated.md").exists())
            self.assertTrue((persona_dir / "NAVIGATION.md").exists())
            self.assertTrue((persona_dir / "SOUL.md").exists())
            self.assertFalse((root / "characters" / "mini" / "\u5218\u5907.json").exists())

    def test_chat_engine_can_load_markdown_profile_without_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            persona_dir = root / "characters" / "sanguo" / "\u5218\u5907"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "PROFILE.md").write_text(
                "# PROFILE\n\n"
                "## Meta\n"
                "- name: \u5218\u5907\n"
                "- novel_id: sanguo\n\n"
                "## Core\n"
                "- core_traits: \u4ec1\u539a\uff1b\u514b\u5236\n"
                "- values: \u8d23\u4efb=9\uff1b\u5584\u826f=8\n"
                "- speech_style: \u514b\u5236\n"
                "- soul_goal: \u5b88\u4f4f\u4f17\u4eba\u9000\u8def\n"
                "- worldview: \u5148\u987e\u4f17\u4eba\n"
                "- thinking_style: \u5148\u770b\u540e\u679c\n\n"
                "## Voice\n"
                "- decision_rules: \u540c\u4f34\u53d7\u538b\u2192\u4e3b\u52a8\u4ecb\u5165\n"
                "- cadence: medium\n",
                encoding="utf-8",
            )
            (persona_dir / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")

            engine = self.make_runtime_parts(config)["chat_engine"]
            profile = engine._load_character_profiles("sanguo")["\u5218\u5907"]

            self.assertEqual(profile["name"], "\u5218\u5907")
            self.assertEqual(profile["speech_style"], "\u514b\u5236")
            self.assertEqual(profile["values"]["\u8d23\u4efb"], 9)
            self.assertIn("\u4ec1\u539a", profile["core_traits"])

    def test_cli_chat_setup_writes_session_summary_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "session-summary.json"
            argv = [
                "zaomeng",
                "chat",
                "--novel",
                "hongloumeng.txt",
                "--message",
                "\u8ba9\u6211\u4ee5\u6211\u81ea\u5df1\u8fdb\u5165\u7ea2\u697c\u68a6\uff0c\u548c\u6797\u9edb\u7389\u804a\u5929",
                "--session-summary-out",
                str(summary_path),
            ]

            with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print"):
                engine = engine_cls.return_value
                engine._load_character_profiles.return_value = {
                    "\u6797\u9edb\u7389": {"name": "\u6797\u9edb\u7389"},
                }
                engine._mentioned_characters.return_value = ["\u6797\u9edb\u7389"]
                engine.build_session_summary.return_value = {
                    "status": "ready",
                    "mode": "insert",
                    "session_id": "defaultinsert",
                }
                session = {
                    "id": "defaultinsert",
                    "title": "insert",
                    "characters": ["\u6797\u9edb\u7389"],
                    "state": {"focus_targets": {}},
                }
                engine.create_session.return_value = session

                ZaomengCLI().run()

                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["mode"], "insert")
                self.assertEqual(payload["session_id"], "defaultinsert")
                engine.build_session_summary.assert_called_once()

    def test_cli_chat_single_turn_writes_result_and_status_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "chat-result.json"
            status_path = Path(tmp) / "chat-status.json"
            summary_path = Path(tmp) / "session-summary.json"
            argv = [
                "zaomeng",
                "chat",
                "--novel",
                "hongloumeng.txt",
                "--mode",
                "insert",
                "--message",
                "\u6211\u53eb\u963f\u9752\uff0c\u60f3\u548c\u6797\u9edb\u7389\u8bf4\u8bdd\u3002",
                "--session-summary-out",
                str(summary_path),
                "--chat-result-out",
                str(result_path),
                "--chat-status-out",
                str(status_path),
            ]

            with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print"):
                engine = engine_cls.return_value
                engine._load_character_profiles.return_value = {
                    "\u6797\u9edb\u7389": {"name": "\u6797\u9edb\u7389"},
                }
                engine._mentioned_characters.return_value = ["\u6797\u9edb\u7389"]
                engine.insert_once.return_value = [("\u6797\u9edb\u7389", "\u4e0d\u5fc5\u62d8\u793c\u3002")]
                engine.build_session_summary.return_value = {
                    "status": "ready",
                    "mode": "insert",
                    "session_id": "turninsert",
                    "novel_id": "hongloumeng",
                    "participants": ["\u6797\u9edb\u7389"],
                    "self_insert": {"display_name": "\u963f\u9752"},
                }
                session = {
                    "id": "turninsert",
                    "title": "insert",
                    "novel": "hongloumeng.txt",
                    "novel_id": "hongloumeng",
                    "characters": ["\u6797\u9edb\u7389"],
                    "state": {"focus_targets": {}},
                }
                engine.create_session.return_value = session

                ZaomengCLI().run()

                result_payload = json.loads(result_path.read_text(encoding="utf-8"))
                status_payload = json.loads(status_path.read_text(encoding="utf-8"))
                self.assertEqual(result_payload["kind"], "zaomeng_chat_result")
                self.assertEqual(result_payload["action"], "single_turn")
                self.assertEqual(result_payload["responses"][0]["speaker"], "\u6797\u9edb\u7389")
                self.assertEqual(result_payload["summary"]["mode"], "insert")
                self.assertEqual(status_payload["capability"], "chat")
                self.assertTrue(status_payload["success"])
                self.assertEqual(status_payload["status"], "complete")
                self.assertEqual(status_payload["outputs"]["responses_count"], 1)
                self.assertIn("chat_result_out", status_payload["outputs"])

    def test_relationship_extractor_exports_relation_markdown_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            extractor = self.make_runtime_parts(config)["extractor"]
            extractor._export_relation_bundle(
                {
                    "\u5218\u5907_\u5173\u7fbd": {
                        "trust": 8,
                        "affection": 7,
                        "power_gap": 0,
                        "conflict_point": "\u540c\u76df\u53d6\u820d",
                        "typical_interaction": "\u5148\u8bae\u8f7b\u91cd\uff0c\u518d\u5b9a\u8fdb\u9000",
                        "hidden_attitude": "\u8868\u9762\u7a33\u4f4f\u5927\u5c40\uff0c\u79c1\u4e0b\u66f4\u5728\u610f\u5173\u7fbd\u662f\u5426\u7ad9\u4f4f",
                        "relation_change": "\u5347\u6e29",
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
            relation_text = (root / "characters" / "mini" / "\u5218\u5907" / "RELATIONS.generated.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## RELATIONS", nav_text)
            self.assertIn("- status: active", nav_text)
            self.assertIn("hidden_attitude", relation_text)
            self.assertIn("relation_change", relation_text)

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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
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

            engine = self.make_runtime_parts(config)["chat_engine"]
            session = engine.create_session("sanguo.txt", "observe")

            handled = engine._handle_inline_command(
                session,
                "/correct \u5173\u7fbd|\u5218\u5907|\u5bb9\u6211\u518d\u60f3\u60f3|\u5927\u4e49\u5f53\u524d\uff0c\u4e0d\u53ef\u8f7b\u6613\u80cc\u4fe1|tone_fix",
            )

            self.assertTrue(handled)
            profile = engine._load_character_profiles("sanguo")["\u5173\u7fbd"]
            self.assertTrue(any("\u7ea0\u6b63" in item for item in profile.get("user_edits", [])))

    def test_user_edits_can_change_voice_constraints(self):
        speaker = self.make_runtime_parts(Config())["speaker"]
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
            engine._load_character_profiles.return_value = {
                "\u8d3e\u5b9d\u7389": {"name": "\u8d3e\u5b9d\u7389"},
                "\u6797\u9edb\u7389": {"name": "\u6797\u9edb\u7389"},
            }
            engine._resolve_character_name.return_value = "\u8d3e\u5b9d\u7389"
            session = {
                "id": "testsession",
                "title": "test",
                "characters": ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389"],
                "state": {"focus_targets": {}},
            }
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

    def test_cli_chat_auto_mode_detects_setup_only_act_request(self):
        argv = [
            "zaomeng",
            "chat",
            "--novel",
            "hongloumeng.txt",
            "--message",
            "\u8ba9\u6211\u626e\u6f14\u8d3e\u5b9d\u7389\u548c\u6797\u9edb\u7389\u804a\u5929",
        ]

        with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print"):
            engine = engine_cls.return_value
            engine._load_character_profiles.return_value = {
                "\u8d3e\u5b9d\u7389": {"name": "\u8d3e\u5b9d\u7389"},
                "\u6797\u9edb\u7389": {"name": "\u6797\u9edb\u7389"},
            }
            engine._mentioned_characters.return_value = ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389"]
            session = {
                "id": "setupsession",
                "title": "setup",
                "characters": ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389", "\u859b\u5b9d\u9497"],
                "state": {"focus_targets": {}},
            }
            engine.create_session.return_value = session

            ZaomengCLI().run()

            engine.create_session.assert_called_once_with("hongloumeng.txt", "act")
            engine.act_once.assert_not_called()
            engine.observe_once.assert_not_called()
            engine._save_session.assert_called_once()
            self.assertEqual(session["mode"], "act")
            self.assertEqual(session["state"]["controlled_character"], "\u8d3e\u5b9d\u7389")
            self.assertEqual(session["state"]["focus_targets"]["\u8d3e\u5b9d\u7389"], "\u6797\u9edb\u7389")
            self.assertEqual(session["characters"], ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389"])

    def test_cli_chat_auto_mode_reuses_controlled_character_from_session(self):
        argv = [
            "zaomeng",
            "chat",
            "--novel",
            "hongloumeng.txt",
            "--session",
            "setupsession",
            "--message",
            "\u59b9\u59b9\u4eca\u65e5\u8fd8\u597d\u4e48\uff1f",
        ]

        with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print"):
            engine = engine_cls.return_value
            engine._mentioned_characters.return_value = []
            session = {
                "id": "setupsession",
                "title": "setup",
                "novel_id": "hongloumeng",
                "mode": "act",
                "characters": ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389"],
                "state": {
                    "controlled_character": "\u8d3e\u5b9d\u7389",
                    "focus_targets": {"\u8d3e\u5b9d\u7389": "\u6797\u9edb\u7389"},
                },
            }
            engine.restore_session.return_value = session
            engine.act_once.return_value = [("\u6797\u9edb\u7389", "\u4e0d\u52b3\u60e6\u5ff5\uff0c\u6211\u8fd8\u597d\u3002")]

            ZaomengCLI().run()

            engine.restore_session.assert_called_once_with("setupsession")
            engine.act_once.assert_called_once_with(
                session,
                "\u8d3e\u5b9d\u7389",
                "\u59b9\u59b9\u4eca\u65e5\u8fd8\u597d\u4e48\uff1f",
            )

    def test_cli_chat_auto_mode_supports_group_act_setup_request(self):
        argv = [
            "zaomeng",
            "chat",
            "--novel",
            "hongloumeng.txt",
            "--message",
            "\u8ba9\u6211\u4ee3\u5165\u8d3e\u5b9d\u7389\uff0c\u548c\u6797\u9edb\u7389\u3001\u859b\u5b9d\u9497\u4e00\u8d77\u7fa4\u804a",
        ]

        with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print"):
            engine = engine_cls.return_value
            engine._load_character_profiles.return_value = {
                "\u8d3e\u5b9d\u7389": {"name": "\u8d3e\u5b9d\u7389"},
                "\u6797\u9edb\u7389": {"name": "\u6797\u9edb\u7389"},
                "\u859b\u5b9d\u9497": {"name": "\u859b\u5b9d\u9497"},
            }
            engine._mentioned_characters.return_value = [
                "\u8d3e\u5b9d\u7389",
                "\u6797\u9edb\u7389",
                "\u859b\u5b9d\u9497",
            ]
            session = {
                "id": "groupactsession",
                "title": "group-act",
                "characters": ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389", "\u859b\u5b9d\u9497"],
                "state": {"focus_targets": {}},
            }
            engine.create_session.return_value = session

            ZaomengCLI().run()

            engine.create_session.assert_called_once_with("hongloumeng.txt", "act")
            engine.act_once.assert_not_called()
            engine.observe_once.assert_not_called()
            engine._save_session.assert_called_once()
            self.assertEqual(session["mode"], "act")
            self.assertEqual(session["state"]["controlled_character"], "\u8d3e\u5b9d\u7389")
            self.assertEqual(
                session["state"]["selected_characters"],
                ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389", "\u859b\u5b9d\u9497"],
            )
            self.assertEqual(
                session["characters"],
                ["\u8d3e\u5b9d\u7389", "\u6797\u9edb\u7389", "\u859b\u5b9d\u9497"],
            )

    def test_cli_chat_auto_mode_supports_self_insert_setup_request(self):
        argv = [
            "zaomeng",
            "chat",
            "--novel",
            "hongloumeng.txt",
            "--message",
            "\u8ba9\u6211\u4ee5\u6211\u81ea\u5df1\u8fdb\u5165\u7ea2\u697c\u68a6\uff0c\u548c\u6797\u9edb\u7389\u3001\u8d3e\u5b9d\u7389\u804a\u5929",
            "--self-name",
            "\u963f\u9752",
            "--self-identity",
            "\u8d3e\u5e9c\u521d\u6765\u7684\u65b0\u5ba2",
        ]

        with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print"):
            engine = engine_cls.return_value
            engine._load_character_profiles.return_value = {
                "\u8d3e\u5b9d\u7389": {"name": "\u8d3e\u5b9d\u7389"},
                "\u6797\u9edb\u7389": {"name": "\u6797\u9edb\u7389"},
            }
            engine._mentioned_characters.return_value = ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"]
            session = {
                "id": "insertsession",
                "title": "insert",
                "characters": ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"],
                "state": {"focus_targets": {}},
            }
            engine.create_session.return_value = session

            ZaomengCLI().run()

            engine.create_session.assert_called_once_with("hongloumeng.txt", "insert")
            engine.insert_once.assert_not_called()
            engine._save_session.assert_called_once()
            self.assertEqual(session["mode"], "insert")
            self.assertEqual(session["characters"], ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"])
            self.assertEqual(session["state"]["self_insert"]["display_name"], "\u963f\u9752")
            self.assertEqual(session["state"]["self_insert"]["scene_identity"], "\u8d3e\u5e9c\u521d\u6765\u7684\u65b0\u5ba2")

    def test_cli_chat_auto_mode_extracts_self_insert_profile_from_message(self):
        argv = [
            "zaomeng",
            "chat",
            "--novel",
            "hongloumeng.txt",
            "--message",
            "\u8ba9\u6211\u4ee5\u6211\u81ea\u5df1\u8fdb\u5165\u7ea2\u697c\u68a6\uff0c\u6211\u53eb\u963f\u9752\uff0c\u6211\u662f\u8d3e\u5e9c\u521d\u6765\u7684\u65b0\u5ba2\uff0c\u548c\u6797\u9edb\u7389\u3001\u8d3e\u5b9d\u7389\u804a\u5929",
        ]

        with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print"):
            engine = engine_cls.return_value
            engine._load_character_profiles.return_value = {
                "\u8d3e\u5b9d\u7389": {"name": "\u8d3e\u5b9d\u7389"},
                "\u6797\u9edb\u7389": {"name": "\u6797\u9edb\u7389"},
            }
            engine._mentioned_characters.return_value = ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"]
            session = {
                "id": "insertsession",
                "title": "insert",
                "characters": ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"],
                "state": {"focus_targets": {}},
            }
            engine.create_session.return_value = session

            ZaomengCLI().run()

            self.assertEqual(session["mode"], "insert")
            self.assertEqual(session["state"]["self_insert"]["display_name"], "\u963f\u9752")
            self.assertEqual(session["state"]["self_insert"]["scene_identity"], "\u8d3e\u5e9c\u521d\u6765\u7684\u65b0\u5ba2")

    def test_cli_chat_reuses_self_insert_card_from_session(self):
        argv = [
            "zaomeng",
            "chat",
            "--novel",
            "hongloumeng.txt",
            "--session",
            "insertsession",
            "--message",
            "\u521d\u6765\u8d35\u5e9c\uff0c\u8fd8\u8bf7\u591a\u591a\u6307\u6559\u3002",
        ]

        with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print") as mock_print:
            engine = engine_cls.return_value
            engine._mentioned_characters.return_value = []
            session = {
                "id": "insertsession",
                "title": "insert",
                "novel_id": "hongloumeng",
                "mode": "insert",
                "characters": ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"],
                "state": {
                    "focus_targets": {},
                    "self_insert": {
                        "display_name": "\u963f\u9752",
                        "scene_identity": "\u8d3e\u5e9c\u65b0\u5ba2",
                        "interaction_style": "immersive",
                        "plot_agency": "light",
                    },
                },
            }
            engine.restore_session.return_value = session
            engine.insert_once.return_value = [("\u6797\u9edb\u7389", "\u4e0d\u5fc5\u62d8\u793c\u3002")]

            ZaomengCLI().run()

            engine.restore_session.assert_called_once_with("insertsession")
            engine.insert_once.assert_called_once_with(
                session,
                "\u521d\u6765\u8d35\u5e9c\uff0c\u8fd8\u8bf7\u591a\u591a\u6307\u6559\u3002",
            )
            rendered = "\n".join(" ".join(str(arg) for arg in call.args) for call in mock_print.call_args_list)
            self.assertIn("Reusing self insert card", rendered)
            self.assertIn("\u963f\u9752", rendered)

    def test_cli_chat_insert_setup_prints_first_time_hint_when_profile_is_default(self):
        argv = [
            "zaomeng",
            "chat",
            "--novel",
            "hongloumeng.txt",
            "--message",
            "\u8ba9\u6211\u4ee5\u6211\u81ea\u5df1\u8fdb\u5165\u7ea2\u697c\u68a6\uff0c\u548c\u6797\u9edb\u7389\u804a\u5929",
        ]

        with patch("src.core.main.ChatEngine") as engine_cls, patch("sys.argv", argv), patch("builtins.print") as mock_print:
            engine = engine_cls.return_value
            engine._load_character_profiles.return_value = {
                "\u6797\u9edb\u7389": {"name": "\u6797\u9edb\u7389"},
            }
            engine._mentioned_characters.return_value = ["\u6797\u9edb\u7389"]
            session = {
                "id": "defaultinsert",
                "title": "insert",
                "characters": ["\u6797\u9edb\u7389"],
                "state": {"focus_targets": {}},
            }
            engine.create_session.return_value = session

            ZaomengCLI().run()

            rendered = "\n".join(" ".join(str(arg) for arg in call.args) for call in mock_print.call_args_list)
            self.assertIn("First-time insert hint:", rendered)
            self.assertIn("我叫阿青", rendered)
            self.assertIn("我是初到贾府的新客", rendered)

    def test_relationship_extractor_exports_relation_markdown_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            save_json(
                root / "characters" / "mini" / "\u5218\u5907.json",
                {"name": "\u5218\u5907", "speech_style": "\u514b\u5236", "typical_lines": [], "values": {}},
            )
            save_json(
                root / "characters" / "mini" / "\u5173\u7fbd.json",
                {"name": "\u5173\u7fbd", "speech_style": "\u51b7\u9759", "typical_lines": [], "values": {}},
            )

            extractor = self.make_runtime_parts(config)["extractor"]
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

    def test_speaker_answers_decision_question_with_a_stance(self):
        speaker = self.make_runtime_parts(Config())["speaker"]
        reply = speaker.generate(
            character_profile={
                "name": "\u5173\u7fbd",
                "core_traits": ["\u8c28\u614e"],
                "speech_style": "\u514b\u5236",
                "typical_lines": [],
                "values": {},
            },
            context="\u4e8c\u4f4d\u8d24\u5f1f\uff0c\u6211\u4eec\u662f\u5426\u5e94\u8be5\u8054\u5408\u5b59\u6743\u5bf9\u6297\u66f9\u64cd\uff1f",
            history=[],
            target_name="\u5218\u5907",
            relation_state={"affection": 7, "trust": 8, "hostility": 0, "ambiguity": 4},
        )

        self.assertTrue(any(token in reply for token in ("\u5148", "\u5b9a", "\u5c40\u52bf", "\u7acb\u573a")))
        self.assertGreater(len(reply), 6)

    def test_speaker_uses_key_bond_and_stress_response_in_fallback(self):
        speaker = self.make_runtime_parts(Config())["speaker"]
        profile = {
            "name": "\u738b\u7199\u51e4",
            "core_traits": ["\u673a\u53d8", "\u5f3a\u52bf"],
            "speech_style": "\u76f4\u63a5",
            "typical_lines": [],
            "values": {"\u667a\u6167": 8, "\u8d23\u4efb": 7},
            "key_bonds": ["bond_marker_keep_safe"],
            "stress_response": "stress_marker_hold_scene",
        }

        care_reply = speaker.generate(
            character_profile=profile,
            context="\u5e73\u513f\u8fd9\u51e0\u65e5\u5fc3\u91cc\u4e0d\u5b89\uff0c\u4f60\u600e\u4e48\u770b\uff1f",
            history=[],
            target_name="\u5e73\u513f",
            relation_state={"affection": 8, "trust": 8, "hostility": 0, "ambiguity": 2},
        )
        conflict_reply = speaker.generate(
            character_profile=profile,
            context="\u5982\u679c\u8fd9\u4ef6\u4e8b\u771f\u8981\u6495\u7834\u8138\uff0c\u4f60\u4f1a\u600e\u4e48\u505a\uff1f",
            history=[],
            target_name="\u8d3e\u740f",
            relation_state={"affection": 3, "trust": 3, "hostility": 6, "ambiguity": 2},
        )
        voice = speaker._build_voice(profile)

        self.assertIn("bond_marker_keep_safe", speaker._drive_line(voice, "care"))
        self.assertIn("stress_marker_hold_scene", speaker._drive_line(voice, "conflict"))
        self.assertGreaterEqual(care_reply.count("\u3002"), 2)
        self.assertGreaterEqual(conflict_reply.count("\u3002"), 2)

    def test_speaker_profiles_produce_distinct_voices(self):
        speaker = self.make_runtime_parts(Config())["speaker"]

        liubei_voice = speaker._build_voice(
            {
                "name": "\u5218\u5907",
                "core_traits": ["\u4ec1\u539a", "\u514b\u5236"],
                "speech_style": "\u8bed\u8a00\u94fa\u9648\uff0c\u6574\u4f53\u514b\u5236\u3002",
                "typical_lines": ["\u767e\u59d3\u6d41\u79bb\u5931\u6240\uff0c\u624d\u662f\u6211\u6700\u4e0d\u613f\u89c1\u4e4b\u4e8b\u3002"],
                "decision_rules": ["\u540c\u4f34\u53d7\u538b\u2192\u503e\u5411\u4e3b\u52a8\u4ecb\u5165"],
                "values": {"\u8d23\u4efb": 9, "\u5584\u826f": 8, "\u5fe0\u8bda": 8, "\u667a\u6167": 7},
            }
        )
        zhangfei_voice = speaker._build_voice(
            {
                "name": "\u5f20\u98de",
                "core_traits": ["\u8c6a\u723d", "\u52c7\u6562"],
                "speech_style": "\u8bed\u8a00\u76f4\u767d\uff0c\u60c5\u7eea\u5916\u9732\u3002",
                "typical_lines": ["\u54e5\u54e5\u82e5\u6709\u53f7\u4ee4\uff0c\u6211\u5148\u4e0a\u524d\u3002"],
                "decision_rules": ["\u540c\u4f34\u53d7\u538b\u2192\u503e\u5411\u4e3b\u52a8\u4ecb\u5165"],
                "values": {"\u52c7\u6c14": 9, "\u5fe0\u8bda": 8, "\u8d23\u4efb": 6, "\u667a\u6167": 4},
            }
        )

        self.assertNotEqual(liubei_voice["primary_priority"], zhangfei_voice["primary_priority"])
        self.assertNotEqual(liubei_voice["restrained"], zhangfei_voice["restrained"])
        self.assertNotEqual(liubei_voice["speech_habits"]["cadence"], zhangfei_voice["speech_habits"]["cadence"])
        self.assertNotEqual(liubei_voice["worldview"], zhangfei_voice["worldview"])

    def test_distiller_llm_second_pass_refines_profile(self):
        class StubLLM:
            def estimate_cost(self, prompt: str, expected_completion_ratio: float = 0.0) -> float:
                return 0.0

            def is_generation_enabled(self) -> bool:
                return True

            def chat_completion(self, messages, model=None, temperature=None, max_tokens=None, stream=False):
                return {
                    "content": (
                        "# PROFILE\n"
                        "- soul_goal: \u5b88\u4f4f\u548c\u5b9d\u7389\u4e4b\u95f4\u90a3\u70b9\u4e0d\u80af\u660e\u8bf4\u7684\u771f\u5fc3\n"
                        "- hidden_desire: \u88ab\u7406\u89e3\uff0c\u4f46\u53c8\u4e0d\u613f\u8f7b\u6613\u793a\u5f31\n"
                        "- temperament_type: \u9ad8\u654f\u611f\u3001\u5916\u51b7\u5185\u70ed\u578b\n"
                        "- stress_response: \u538b\u529b\u8d8a\u5927\uff0c\u8d8a\u4f1a\u628a\u60c5\u7eea\u538b\u4f4e\uff0c\u5148\u7528\u51b7\u8bed\u6c14\u81ea\u62a4\n"
                        "- arc_mid: trigger_event=\u56e0\u8bef\u89e3\u4e0e\u731c\u5fcc\u53cd\u590d\u62c9\u626f\uff1bphase_summary=\u60c5\u7eea\u8d77\u4f0f\u53d8\u5f97\u660e\u663e\n"
                        "- arc_end: final_state=\u611f\u60c5\u8d8a\u6df1\uff0c\u8eab\u5fc3\u4e5f\u66f4\u75b2\u60eb\uff1bphase_summary=\u4ee5\u51b7\u6de1\u63a9\u4f4f\u771f\u60c5\n"
                        "- arc_confidence: 8\n"
                    )
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            config.update({"distillation": {"second_pass_mode": "llm-only"}})
            parts = self.make_runtime_parts(config)
            distiller = parts["distiller"]
            distiller.llm_client = StubLLM()

            profile = {
                "name": "\u6797\u9edb\u7389",
                "soul_goal": "\u5b88\u4f4f\u81ea\u5c0a",
                "hidden_desire": "",
                "arc": {
                    "start": {"phase_summary": "\u521d\u5165\u8d3e\u5e9c\u65f6\u5c0f\u5fc3\u8bd5\u63a2"},
                    "mid": {"trigger_event": "\u672a\u8bc6\u522b\u5230\u660e\u786e\u53d8\u5316\u4e8b\u4ef6", "phase_summary": "\u8bc1\u636e\u4e0d\u8db3"},
                    "end": {"final_state": "\u672a\u5224\u5b9a\uff08\u8bc1\u636e\u4e0d\u8db3\uff09", "phase_summary": "\u8bc1\u636e\u4e0d\u8db3"},
                },
                "arc_summary": "",
                "arc_confidence": 1,
            }
            bucket = {
                "descriptions": ["\u9edb\u7389\u521d\u5165\u8d3e\u5e9c\uff0c\u51e1\u4e8b\u7559\u5fc3"],
                "dialogues": ["\u4f60\u65e2\u6765\u4e86\uff0c\u4fbf\u5750\u4e00\u4f1a\u513f\u3002"],
                "thoughts": ["\u5fc3\u4e0b\u53c8\u9178\u53c8\u75db\uff0c\u5374\u4e0d\u80af\u660e\u8bf4"],
                "timeline": [
                    {"index": 0, "descriptions": ["\u521d\u5165\u8d3e\u5e9c\uff0c\u5c0f\u5fc3\u8bd5\u63a2"], "dialogues": [], "thoughts": []},
                    {"index": 1, "descriptions": [], "dialogues": [], "thoughts": ["\u8bef\u89e3\u7d2f\u79ef\uff0c\u60c5\u7eea\u53cd\u590d"]},
                    {"index": 2, "descriptions": ["\u8868\u9762\u66f4\u51b7\u6de1\uff0c\u5fc3\u4e8b\u5374\u66f4\u91cd"], "dialogues": [], "thoughts": []},
                ],
            }
            refined = distiller._refine_profile_with_llm(profile, bucket=bucket, arc_values=[(0, {}), (1, {}), (2, {})])

            self.assertEqual(refined["soul_goal"], "\u5b88\u4f4f\u548c\u5b9d\u7389\u4e4b\u95f4\u90a3\u70b9\u4e0d\u80af\u660e\u8bf4\u7684\u771f\u5fc3")
            self.assertEqual(refined["temperament_type"], "\u9ad8\u654f\u611f\u3001\u5916\u51b7\u5185\u70ed\u578b")
            self.assertIn("\u538b\u529b", refined["stress_response"])
            self.assertEqual(refined["arc"]["mid"]["trigger_event"], "\u56e0\u8bef\u89e3\u4e0e\u731c\u5fcc\u53cd\u590d\u62c9\u626f")
            self.assertEqual(refined["arc"]["end"]["final_state"], "\u611f\u60c5\u8d8a\u6df1\uff0c\u8eab\u5fc3\u4e5f\u66f4\u75b2\u60eb")
            self.assertEqual(refined["arc_confidence"], 8)

    def test_distiller_second_pass_includes_peer_contrast_and_overlap_alerts(self):
        class CaptureLLM:
            def __init__(self):
                self.messages = []

            def estimate_cost(self, prompt: str, expected_completion_ratio: float = 0.0) -> float:
                return 0.0

            def is_generation_enabled(self) -> bool:
                return True

            def chat_completion(self, messages, model=None, temperature=None, max_tokens=None, stream=False):
                self.messages = messages
                return {"content": ""}

        config = Config()
        config.update({"distillation": {"second_pass_mode": "llm-only"}})
        distiller = self.make_runtime_parts(config)["distiller"]
        capture_llm = CaptureLLM()
        distiller.llm_client = capture_llm

        distiller._refine_profile_with_llm(
            {
                "name": "\u9f50\u590f",
                "identity_anchor": "\u5b88\u89c4\u5219\u7684\u8c0b\u5c40\u8005",
                "soul_goal": "\u628a\u4eba\u4ece\u6b7b\u5c40\u91cc\u62c9\u51fa\u6765",
                "speech_style": "\u5148\u62c6\u89c4\u5219\u518d\u843d\u7ed3\u8bba",
                "background_imprint": "\u957f\u671f\u5728\u9ad8\u538b\u89c4\u5219\u91cc\u8bad\u7ec3\u51fa\u51b7\u9759",
                "social_mode": "\u5148\u89c2\u5bdf\u540e\u8054\u76df",
                "reward_logic": "\u8bb0\u6069\u4e5f\u8bb0\u8d26",
                "belief_anchor": "\u89c4\u5219\u53ef\u4ee5\u88ab\u7528\u6765\u4fdd\u4eba",
                "decision_rules": ["\u5148\u62c6\u89c4\u5219\u518d\u884c\u52a8"],
                "key_bonds": ["\u5bf9\u5e76\u80a9\u6d3b\u4e0b\u6765\u7684\u4eba\u4f1a\u66f4\u4fe1"],
                "arc": {},
                "arc_summary": "",
                "arc_confidence": 0,
            },
            bucket={
                "descriptions": ["\u9f50\u590f\u770b\u4eba\u5148\u770b\u5c40\u52bf\u548c\u89c4\u5219\u7f3a\u53e3"],
                "dialogues": ["\u5148\u522b\u6025\uff0c\u628a\u8fd9\u6761\u89c4\u5219\u518d\u8fc7\u4e00\u904d\u3002"],
                "thoughts": ["\u4ed6\u5fc3\u91cc\u5148\u7b97\u7684\u662f\u4ee3\u4ef7\u548c\u9000\u8def"],
                "timeline": [],
            },
            arc_values=[],
            peer_profiles={
                "\u4e54\u5bb6\u52b2": {
                    "name": "\u4e54\u5bb6\u52b2",
                    "identity_anchor": "\u76f4\u63a5\u9876\u538b\u7684\u5bf9\u6297\u8005",
                    "soul_goal": "\u4e0d\u80fd\u61cb\u5c48\u5730\u6297\u4e0b\u53bb",
                    "speech_style": "\u77ed\u53e5\u5e26\u523a",
                    "decision_rules": ["\u5148\u8868\u6001\u518d\u8bf4"],
                    "key_bonds": ["\u770b\u4e2d\u5c31\u62a4\u5230\u5e95"],
                }
            },
            overlap_report=["identity_anchor is identical to \u4e54\u5bb6\u52b2"],
        )

        self.assertEqual(len(capture_llm.messages), 2)
        self.assertIn("Peer Contrast", capture_llm.messages[1]["content"])
        self.assertIn("Overlap Alerts", capture_llm.messages[1]["content"])
        self.assertIn("identity_anchor is identical to", capture_llm.messages[1]["content"])
        self.assertIn("\u4e54\u5bb6\u52b2", capture_llm.messages[1]["content"])

    def test_distiller_second_pass_enforces_distinction_when_llm_returns_empty(self):
        class EmptyLLM:
            def estimate_cost(self, prompt: str, expected_completion_ratio: float = 0.0) -> float:
                return 0.0

            def is_generation_enabled(self) -> bool:
                return True

            def chat_completion(self, messages, model=None, temperature=None, max_tokens=None, stream=False):
                return {"content": ""}

        config = Config()
        config.update({"distillation": {"second_pass_mode": "llm-only"}})
        distiller = self.make_runtime_parts(config)["distiller"]
        distiller.llm_client = EmptyLLM()

        refined = distiller._refine_profile_with_llm(
            {
                "name": "\u9f50\u590f",
                "identity_anchor": "\u5b88\u89c4\u5219\u7684\u4eba",
                "soul_goal": "\u628a\u4eba\u62c9\u51fa\u6b7b\u5c40",
                "speech_style": "\u5148\u89c2\u5bdf\u518d\u4e0b\u7ed3\u8bba",
                "background_imprint": "\u957f\u671f\u8eab\u5728\u9ad8\u538b\u89c4\u5219\u4e2d",
                "social_mode": "\u5148\u89c2\u5bdf\u540e\u7ed3\u76df",
                "reward_logic": "\u8bb0\u6069\u4e5f\u8bb0\u8d26",
                "belief_anchor": "\u89c4\u5219\u4e5f\u80fd\u7528\u6765\u4fdd\u4eba",
                "decision_rules": ["\u5148\u62c6\u89c4\u5219", "\u5148\u627e\u9000\u8def", "\u7ed9\u81ea\u5df1\u4eba\u7559\u751f\u8def"],
                "key_bonds": ["\u5e76\u80a9\u6d3b\u4e0b\u6765\u7684\u4eba", "\u53ef\u4ee5\u4ea4\u80cc\u7684\u4eba"],
                "core_traits": ["\u51b7\u9759", "\u514b\u5236", "\u8c0b\u5b9a\u540e\u52a8"],
                "forbidden_behaviors": ["\u62ff\u540c\u4f34\u5f53\u5f03\u5b50"],
                "life_experience": ["\u957f\u671f\u5728\u89c4\u5219\u4e0e\u6b7b\u5c40\u95f4\u6c42\u751f"],
                "emotion_profile": {"anger_style": "\u5148\u538b\u4f4f", "joy_style": "", "grievance_style": ""},
                "worldview": "\u865a\u5b9e\u90fd\u8981\u5148\u7b97\u6e05",
                "action_style": "\u770b\u6e05\u7834\u7efd\u624d\u51fa\u624b",
                "story_role": "\u62c6\u89c4\u5219\u7684\u5c40\u5185\u4eba",
                "others_impression": "\u8868\u9762\u51b7\u9759\u4e0d\u597d\u4eb2\u8fd1",
                "restraint_threshold": "\u5e73\u65f6\u538b\u5f97\u4f4f\uff0c\u903c\u5230\u5e95\u7ebf\u624d\u4f1a\u7ffb\u8138",
                "temperament_type": "\u51b7\u9759\u62c6\u5c40\u578b",
                "stress_response": "\u9ad8\u538b\u4e0b\u5148\u62c6\u89c4\u5219",
                "arc": {},
                "arc_summary": "",
                "arc_confidence": 0,
            },
            bucket={
                "descriptions": ["\u4ed6\u770b\u4eba\u5148\u770b\u5c40\u52bf\u4e0e\u89c4\u5219\u7f3a\u53e3"],
                "dialogues": ["\u5148\u522b\u6025\uff0c\u628a\u8fd9\u6761\u89c4\u5219\u518d\u8fc7\u4e00\u904d\u3002"],
                "thoughts": ["\u4ed6\u5fc3\u91cc\u5148\u7b97\u7684\u662f\u4ee3\u4ef7\u548c\u9000\u8def"],
                "timeline": [],
            },
            arc_values=[],
            peer_profiles={
                "\u4e54\u5bb6\u52b2": {
                    "name": "\u4e54\u5bb6\u52b2",
                    "identity_anchor": "\u5b88\u89c4\u5219\u7684\u4eba",
                    "soul_goal": "\u628a\u4eba\u62c9\u51fa\u6b7b\u5c40",
                    "background_imprint": "\u957f\u671f\u8eab\u5728\u9ad8\u538b\u89c4\u5219\u4e2d",
                    "social_mode": "\u5148\u89c2\u5bdf\u540e\u7ed3\u76df",
                    "reward_logic": "\u8bb0\u6069\u4e5f\u8bb0\u8d26",
                    "belief_anchor": "\u89c4\u5219\u4e5f\u80fd\u7528\u6765\u4fdd\u4eba",
                    "decision_rules": ["\u5148\u62c6\u89c4\u5219", "\u5148\u627e\u9000\u8def"],
                    "key_bonds": ["\u5e76\u80a9\u6d3b\u4e0b\u6765\u7684\u4eba"],
                    "core_traits": ["\u51b7\u9759", "\u514b\u5236"],
                    "moral_bottom_line": "\u62ff\u540c\u4f34\u5f53\u5f03\u5b50",
                    "stress_response": "\u9ad8\u538b\u4e0b\u5148\u62c6\u89c4\u5219",
                    "story_role": "\u62c6\u89c4\u5219\u7684\u5c40\u5185\u4eba",
                    "others_impression": "\u8868\u9762\u51b7\u9759\u4e0d\u597d\u4eb2\u8fd1",
                    "restraint_threshold": "\u5e73\u65f6\u538b\u5f97\u4f4f\uff0c\u903c\u5230\u5e95\u7ebf\u624d\u4f1a\u7ffb\u8138",
                    "temperament_type": "\u51b7\u9759\u62c6\u5c40\u578b",
                }
            },
            overlap_report=["identity_anchor is identical to \u4e54\u5bb6\u52b2"],
        )

        self.assertEqual(refined["identity_anchor"], "\u4ed6\u770b\u4eba\u5148\u770b\u5c40\u52bf\u4e0e\u89c4\u5219\u7f3a\u53e3")
        self.assertEqual(refined["soul_goal"], "\u4ed6\u5fc3\u91cc\u5148\u7b97\u7684\u662f\u4ee3\u4ef7\u548c\u9000\u8def")
        self.assertEqual(refined["social_mode"], "\u5148\u522b\u6025\uff0c\u628a\u8fd9\u6761\u89c4\u5219\u518d\u8fc7\u4e00\u904d\u3002")
        self.assertEqual(refined["decision_rules"], ["\u7ed9\u81ea\u5df1\u4eba\u7559\u751f\u8def"])
        self.assertEqual(refined["key_bonds"], ["\u53ef\u4ee5\u4ea4\u80cc\u7684\u4eba"])
        self.assertEqual(refined["core_traits"], ["\u8c0b\u5b9a\u540e\u52a8"])

    def test_distiller_local_refine_preserves_profile_when_local_rewrite_is_disabled(self):
        distiller = self.make_runtime_parts(Config())["distiller"]
        profile = {
            "name": "\u6797\u9edb\u7389",
            "core_traits": ["\u654f\u611f", "\u514b\u5236"],
            "values": {"\u8d23\u4efb": 8, "\u60c5\u611f": 7},
            "speech_style": "\u8bf4\u8bdd\u6574\u4f53\u504f\u514b\u5236",
            "speech_habits": {"cadence": "medium", "signature_phrases": ["\u6211\u539f\u4e0d\u611f"]},
            "decision_rules": ["\u5148\u770b\u6e05\u4eba\u5fc3->\u518d\u51b3\u5b9a\u5f00\u53e3"],
            "key_bonds": ["\u5bf9\u5b9d\u7389\u7684\u60c5\u610f\u4e0d\u80af\u660e\u8bf4"],
            "hidden_desire": "\u88ab\u7406\u89e3",
            "soul_goal": "\u628a\u773c\u524d\u7684\u4eba\u548c\u5c40\u9762\u5c3d\u91cf\u7a33\u4f4f",
            "inner_conflict": "\u7406\u667a\u4e0e\u60c5\u611f\u4e92\u76f8\u62c9\u6254",
            "private_self": "\u79c1\u4e0b\u66f4\u613f\u610f\u4e00\u4e2a\u4eba\u6d88\u5316",
            "moral_bottom_line": "\u771f\u6b63\u89e6\u5230\u5e95\u7ebf\u65f6\u4e0d\u4f1a\u542b\u7cca",
            "self_cognition": "\u5fc3\u91cc\u6e05\u695a\u81ea\u5df1",
            "taboo_topics": ["\u5931\u4fe1"],
            "forbidden_behaviors": ["\u8f7b\u8d31\u771f\u5fc3"],
        }
        refined = distiller._refine_profile_locally(
            profile,
            bucket={
                "thoughts": ["\u5979\u628a\u5bf9\u5b9d\u7389\u7684\u60c5\u610f\u6536\u5728\u5fc3\u91cc\uff0c\u4e0d\u80af\u8bf4\u7834"],
                "dialogues": ["\u6211\u539f\u4e0d\u611f\u8fd9\u6837\u8f7b\u6613\u628a\u8bdd\u8bf4\u5c3d\u4e86\u3002"],
                "descriptions": ["\u8bdd\u5230\u5634\u8fb9\u53c8\u6536\u4f4f\uff0c\u53ea\u7559\u4e09\u5206\u51b7\u610f\u62a4\u4f4f\u81ea\u5df1\u3002"],
            },
            peer_profiles={"薛宝钗": {"decision_rules": [], "key_bonds": [], "typical_lines": [], "life_experience": []}},
            overlap_report=[
                "speech_style is identical to \u859b\u5b9d\u9497",
                "inner_conflict is identical to \u859b\u5b9d\u9497",
                "private_self is identical to \u859b\u5b9d\u9497",
                "moral_bottom_line is identical to \u859b\u5b9d\u9497",
                "self_cognition is identical to \u859b\u5b9d\u9497",
            ],
        )

        self.assertEqual(refined["speech_style"], profile["speech_style"])
        self.assertEqual(refined["inner_conflict"], profile["inner_conflict"])
        self.assertEqual(refined["private_self"], profile["private_self"])
        self.assertEqual(refined["moral_bottom_line"], profile["moral_bottom_line"])
        self.assertEqual(refined["self_cognition"], profile["self_cognition"])

    def test_text_parser_prefers_gbk_for_chinese_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel_path = Path(tmp) / "\u7ea2\u697c\u68a6.txt"
            novel_path.write_bytes("\u8d3e\u5b9d\u7389\u4e0e\u6797\u9edb\u7389\u76f8\u89c1\u3002".encode("gb18030"))

            text = load_novel_text(str(novel_path))

            self.assertIn("\u8d3e\u5b9d\u7389", text)
            self.assertIn("\u6797\u9edb\u7389", text)

    def test_distiller_without_llm_second_pass_preserves_draft_profile(self):
        distiller = self.make_runtime_parts(Config())["distiller"]
        profile = {
            "name": "\u6797\u9edb\u7389",
            "core_traits": ["\u654f\u611f", "\u514b\u5236"],
            "values": {"\u8d23\u4efb": 6, "\u5fe0\u8bda": 7, "\u667a\u6167": 6, "\u5584\u826f": 7},
            "speech_style": "\u53e5\u5f0f\u8f83\u957f\uff0c\u514b\u5236\u542b\u84c4",
            "emotion_profile": {"anger_style": "", "joy_style": "", "grievance_style": "\u53d7\u59d4\u5c48\u65f6\u5148\u538b\u4f4f"},
            "life_experience": ["\u5bc4\u5c45\u8d3e\u5e9c\uff0c\u5fc3\u4e8b\u591a\u534a\u53ea\u80fd\u81ea\u5df1\u6536\u7740"],
            "identity_anchor": "\u4e0d\u4f1a\u8f7b\u7387\u4ea4\u51fa\u771f\u5b9e\u6001\u5ea6\u7684\u4eba",
            "soul_goal": "\u5c3d\u91cf\u5c11\u4f24\u4eba\u5fc3\uff0c\u4e5f\u5c11\u4f24\u65e0\u8f9c\u4e4b\u4eba",
            "background_imprint": "\u6210\u957f\u73af\u5883\u4e0e\u65e7\u4e8b\u4ecd\u5728\u5f71\u54cd\u5982\u4eca\u7684\u53d6\u820d\u548c\u5206\u5bf8",
            "social_mode": "\u4e0d\u8f7b\u6613\u4ea4\u5e95\uff0c\u4eb2\u758f\u8fdc\u8fd1\u8981\u9760\u65f6\u95f4\u548c\u4e8b\u6765\u6162\u6162\u8bd5",
            "reward_logic": "\u8bb0\u6069\u4e5f\u8bb0\u5931\u4fe1\uff0c\u8ba4\u5b9a\u540e\u4f1a\u957f\u671f\u56de\u62a4",
            "belief_anchor": "\u4fe1\u4e49\u548c\u8ba4\u4e0b\u7684\u4eba\u4e0d\u80fd\u8f7b\u6613\u540e\u7f6e",
            "stress_response": "\u8d8a\u5230\u7edd\u5883\u8d8a\u4f1a\u628a\u60c5\u7eea\u538b\u5f97\u66f4\u4f4e",
            "others_impression": "\u65c1\u4eba\u7b2c\u4e00\u5370\u8c61\u591a\u534a\u662f\uff1a\u4e0d\u592a\u597d\u63a5\u8fd1",
            "restraint_threshold": "\u6b32\u671b\u548c\u60c5\u7eea\u5e73\u65f6\u538b\u5f97\u4f4f",
        }
        refined = distiller._refine_profile_with_llm(
            profile,
            bucket={
                "descriptions": ["\u9edb\u7389\u5bc4\u4eba\u7bf1\u4e0b\uff0c\u4e8e\u7ec6\u5904\u66f4\u89c1\u5fc3\u601d"],
                "dialogues": ["\u4f60\u9053\u6211\u522b\u626d\uff0c\u6211\u504f\u53c8\u4e0d\u80af\u660e\u8bf4\u3002"],
                "thoughts": ["\u5fc3\u4e0b\u53c8\u9178\u53c8\u75db\uff0c\u5374\u4e0d\u80af\u660e\u8bf4"],
                "timeline": [],
            },
            arc_values=[],
            peer_profiles={
                "\u859b\u5b9d\u9497": {
                    "name": "\u859b\u5b9d\u9497",
                    "typical_lines": ["\u4f60\u9053\u6211\u522b\u626d\uff0c\u6211\u504f\u53c8\u4e0d\u80af\u660e\u8bf4\u3002"],
                }
            },
            overlap_report=[
                "identity_anchor is identical to \u859b\u5b9d\u9497",
                "soul_goal is identical to \u859b\u5b9d\u9497",
                "social_mode is identical to \u859b\u5b9d\u9497",
            ],
        )

        self.assertEqual(refined["identity_anchor"], profile["identity_anchor"])
        self.assertEqual(refined["soul_goal"], profile["soul_goal"])
        self.assertEqual(refined["social_mode"], profile["social_mode"])

    def test_speaker_does_not_dump_rule_or_goal_text_verbatim(self):
        speaker = self.make_runtime_parts(Config())["speaker"]
        reply = speaker.generate(
            character_profile={
                "name": "\u6797\u9edb\u7389",
                "core_traits": ["\u654f\u611f"],
                "speech_style": "\u514b\u5236\u542b\u84c4",
                "decision_rules": ["\u9047\u5230\u5e95\u7ebf\u95ee\u9898\u65f6\uff0c\u4f1a\u660e\u663e\u6536\u7d27\u8bed\u6c14\u5e76\u7acb\u5373\u8868\u6001"],
                "soul_goal": "\u60f3\u628a\u771f\u6b63\u653e\u4e0d\u4e0b\u7684\u4eba\u548c\u60c5\u610f\u5b88\u4f4f",
                "identity_anchor": "\u5fc3\u601d\u7ec6\uff0c\u8d77\u4e86\u6ce2\u6f9c\u4e5f\u5148\u6536\u5728\u8bdd\u91cc\u7684\u4eba",
                "typical_lines": ["\u4f60\u53c8\u6765\u62db\u6211\u3002"],
                "values": {"\u5fe0\u8bda": 7, "\u5584\u826f": 7, "\u8d23\u4efb": 6},
            },
            context="\u4f60\u5fc3\u91cc\u5230\u5e95\u600e\u4e48\u60f3\uff1f",
            history=[],
            target_name="\u8d3e\u5b9d\u7389",
            relation_state={"affection": 8, "trust": 8, "hostility": 0, "ambiguity": 3},
        )

        self.assertNotIn("\u9047\u5230\u5e95\u7ebf\u95ee\u9898\u65f6", reply)
        self.assertNotIn("\u60f3\u628a\u771f\u6b63\u653e\u4e0d\u4e0b\u7684\u4eba\u548c\u60c5\u610f\u5b88\u4f4f", reply)
        self.assertIn("\u8d3e\u5b9d\u7389", reply)

    def test_distiller_groups_large_character_sets_into_refinement_batches(self):
        distiller = self.make_runtime_parts(Config())["distiller"]
        distiller.refinement_batch_size = 2

        batches = distiller._character_batches(
            ["\u9f50\u590f", "\u4e54\u5bb6\u52b2", "\u5730\u9f20", "\u4f59\u5ff5\u5b89", "\u9648\u4fca\u5357"]
        )

        self.assertEqual(
            batches,
            [
                ["\u9f50\u590f", "\u4e54\u5bb6\u52b2"],
                ["\u5730\u9f20", "\u4f59\u5ff5\u5b89"],
                ["\u9648\u4fca\u5357"],
            ],
        )

    def test_relationship_visualizations_are_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            extractor = self.make_runtime_parts(config)["extractor"]
            self.write_profile(
                root,
                "mini",
                "\u5218\u5907",
                faction_position="\u8700\u6c49",
            )
            self.write_profile(
                root,
                "mini",
                "\u5173\u7fbd",
                story_role="\u5148\u950b",
            )

            extractor._export_relation_visualizations(
                {
                    "\u5218\u5907_\u5173\u7fbd": {
                        "trust": 9,
                        "affection": 8,
                        "hostility": 1,
                        "power_gap": 0,
                        "conflict_point": "\u53d6\u820d\u5148\u540e",
                        "typical_interaction": "\u5148\u95ee\u8fdb\u9000\uff0c\u518d\u8bae\u8f7b\u91cd",
                    }
                },
                "mini",
            )

            mermaid_path = root / "relations" / "mini" / "mini_relations.mermaid.md"
            html_path = root / "relations" / "mini" / "mini_relations.html"
            self.assertTrue(mermaid_path.exists())
            self.assertTrue(html_path.exists())
            mermaid_text = mermaid_path.read_text(encoding="utf-8")
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("graph LR", mermaid_text)
            self.assertIn("classDef group_0", mermaid_text)
            self.assertIn("linkStyle 0 stroke:#15803d,stroke-width:5px", mermaid_text)
            self.assertNotIn("color:#15803d", mermaid_text)
            self.assertNotIn(";;", mermaid_text)
            self.assertIn("class=\"mermaid\"", html_text)
            self.assertIn("mermaid.initialize", html_text)
            self.assertIn("节点颜色优先按阵营", html_text)
            self.assertIn("Closeness", html_text)


if __name__ == "__main__":
    unittest.main()
