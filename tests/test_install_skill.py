#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.install_skill import copy_skill_bundle, iter_skill_entries


class InstallSkillTests(unittest.TestCase):
    def test_iter_skill_entries_only_lists_prompt_first_assets(self):
        entries = iter_skill_entries()
        self.assertIn(".metadata.json", entries)
        self.assertIn("SKILL.md", entries)
        self.assertIn("requirements.txt", entries)
        self.assertIn("assets", entries)
        self.assertIn("tools", entries)
        self.assertNotIn("runtime", entries)

    def test_copy_skill_bundle_installs_prompt_first_payload_by_default(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            dst = copy_skill_bundle(packaged_src, Path(tmpdir), "zaomeng-skill")
            self.assertTrue((dst / ".metadata.json").exists())
            self.assertTrue((dst / "SKILL.md").exists())
            self.assertTrue((dst / "requirements.txt").exists())
            self.assertTrue((dst / "assets" / "vendor" / "mermaid-11.14.0.min.js").exists())
            self.assertTrue((dst / "prompts").exists())
            self.assertTrue((dst / "references").exists())
            self.assertTrue((dst / "tools" / "prepare_novel_excerpt.py").exists())
            self.assertTrue((dst / "tools" / "build_prompt_payload.py").exists())
            self.assertTrue((dst / "tools" / "export_relation_graph.py").exists())
            self.assertTrue((dst / "tools" / "init_host_run.py").exists())
            self.assertTrue((dst / "tools" / "materialize_persona_bundle.py").exists())
            self.assertTrue((dst / "tools" / "update_run_progress.py").exists())
            self.assertTrue((dst / "tools" / "verify_host_workflow.py").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "novel_preparation.py").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "persona_bundle.py").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "workflow_completion.py").exists())
            self.assertFalse((dst / "runtime").exists())

    def test_installed_prepare_excerpt_tool_runs_without_repo_src(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "红楼梦.txt"
            novel_path.write_text("宝玉。黛玉。宝钗。", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "prepare_novel_excerpt.py"),
                    "--novel",
                    str(novel_path),
                    "--max-sentences",
                    "2",
                    "--max-chars",
                    "100",
                    "--output",
                    str(tmp_root / "excerpt.json"),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads((tmp_root / "excerpt.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["source_name"], "红楼梦.txt")
            self.assertEqual(payload["excerpt"], "宝玉。\n黛玉。")

    def test_installed_relation_graph_tool_exports_files_without_repo_src(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            relation_dir = tmp_root / "data" / "relations" / "mini"
            relation_dir.mkdir(parents=True, exist_ok=True)
            relations_file = relation_dir / "mini_relations.md"
            relations_file.write_text(
                "# RELATION_GRAPH\n\n"
                "- novel_id: mini\n\n"
                "## 刘备_关羽\n"
                "- trust: 9\n"
                "- affection: 8\n"
                "- power_gap: 0\n"
                "- conflict_point: 取舍先后\n"
                "- typical_interaction: 先问进退，再议轻重\n"
                "- hidden_attitude: 嘴上克制，私下更依赖对方\n"
                "- relation_change: 升温\n"
                "- confidence: 8\n",
                encoding="utf-8",
            )
            liubei_dir = tmp_root / "data" / "characters" / "mini" / "刘备"
            liubei_dir.mkdir(parents=True, exist_ok=True)
            (liubei_dir / "PROFILE.generated.md").write_text(
                "# PROFILE\n- faction_position: 蜀汉\n- story_role: 主君\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "export_relation_graph.py"),
                    "--relations-file",
                    str(relations_file),
                    "--output",
                    str(tmp_root / "relation_graph.json"),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads((tmp_root / "relation_graph.json").read_text(encoding="utf-8"))
            html_path = Path(payload["html_path"])
            mermaid_path = Path(payload["mermaid_path"])
            self.assertTrue(html_path.exists())
            self.assertTrue(mermaid_path.exists())
            self.assertIn("svg_path", payload)
            self.assertIn("status_path", payload)
            self.assertTrue(Path(payload["status_path"]).exists())
            if payload["svg_path"]:
                self.assertTrue(Path(payload["svg_path"]).exists())
            self.assertIn("mini_relations.html", payload["html_path"])
            self.assertIn("mini_relations.mermaid.md", payload["mermaid_path"])
            mermaid_text = mermaid_path.read_text(encoding="utf-8")
            html_text = html_path.read_text(encoding="utf-8")
            self.assertTrue((relation_dir / "mermaid-11.14.0.min.js").exists())
            self.assertIn("linkStyle 0", mermaid_text)
            self.assertNotIn(";;", mermaid_text)
            self.assertIn("mermaid-11.14.0.min.js", html_text)
            self.assertNotIn("cdn.jsdelivr.net", html_text)
            if payload["svg_path"]:
                self.assertIn(".svg", html_text)

    def test_installed_persona_bundle_tool_materializes_split_files_from_profile_markdown(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            persona_dir = tmp_root / "data" / "characters" / "hongloumeng" / "林黛玉"
            persona_dir.mkdir(parents=True, exist_ok=True)
            profile_path = persona_dir / "PROFILE.generated.md"
            profile_path.write_text(
                "# PROFILE\n"
                "## Meta\n"
                "- name: 林黛玉\n"
                "- novel_id: hongloumeng\n"
                "- source_path: C:/novels/红楼梦.txt\n"
                "## Basic Positioning\n"
                "- core_identity: 贾府寄居的闺秀\n"
                "- faction_position: 贾府内眷\n"
                "- story_role: 核心主角\n"
                "- identity_anchor: 我以真心照人，也最怕真心被轻慢\n"
                "## Root Layer\n"
                "- life_experience: 寄人篱下；敏感多思\n"
                "- taboo_topics: 被轻视；被比较\n"
                "## Inner Core\n"
                "- soul_goal: 求得一份不被辜负的真情\n"
                "- core_traits: 敏感；聪慧；清傲\n"
                "- temperament_type: 清冷而锋利\n"
                "- values: 真情=10；体面=8\n"
                "- worldview: 世情热闹，真心却稀薄\n"
                "- belief_anchor: 真情不可欺\n"
                "- moral_bottom_line: 不肯以假意换安稳\n"
                "## Value And Conflict\n"
                "- self_cognition: 知道自己多心，却也不愿装作不在意\n"
                "- thinking_style: 先感受再判断\n"
                "- decision_rules: 先辨真心；再决定亲疏\n"
                "## Emotion And Stress\n"
                "- fear_triggers: 被冷落；被误解\n"
                "- stress_response: 越委屈越克制，话反而更尖\n"
                "- grievance_style: 受了委屈会拐着弯试探\n"
                "## Social Pattern\n"
                "- social_mode: 慢热而挑剔\n"
                "- others_impression: 才情高，心事也重\n"
                "- key_bonds: 贾宝玉；紫鹃\n"
                "## Voice\n"
                "- speech_style: 轻声细语里带刺\n"
                "- typical_lines: 你既这么说，我也无话可回\n"
                "- cadence: 先缓后紧\n"
                "- signature_phrases: 也罢；倒也未必\n"
                "## Capability\n"
                "- strengths: 诗才；洞察力\n"
                "- weaknesses: 多疑；内耗\n"
                "## Arc\n"
                "- arc_end: 真情=10；自保=7\n"
                "## Evidence\n"
                "- description_count: 3\n"
                "- dialogue_count: 6\n"
                "- thought_count: 2\n"
                "- chunk_count: 4\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "materialize_persona_bundle.py"),
                    "--profile-file",
                    str(profile_path),
                    "--output",
                    str(tmp_root / "persona_bundle.json"),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads((tmp_root / "persona_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["character"], "林黛玉")
            self.assertEqual(Path(payload["persona_dir"]), persona_dir.resolve())
            self.assertTrue(Path(payload["status_path"]).exists())
            self.assertTrue((persona_dir / "SOUL.generated.md").exists())
            self.assertTrue((persona_dir / "IDENTITY.generated.md").exists())
            self.assertTrue((persona_dir / "BACKGROUND.generated.md").exists())
            self.assertTrue((persona_dir / "CAPABILITY.generated.md").exists())
            self.assertTrue((persona_dir / "BONDS.generated.md").exists())
            self.assertTrue((persona_dir / "CONFLICTS.generated.md").exists())
            self.assertTrue((persona_dir / "ROLE.generated.md").exists())
            self.assertTrue((persona_dir / "GOALS.generated.md").exists())
            self.assertTrue((persona_dir / "STYLE.generated.md").exists())
            self.assertTrue((persona_dir / "TRAUMA.generated.md").exists())
            self.assertTrue((persona_dir / "AGENTS.generated.md").exists())
            self.assertTrue((persona_dir / "MEMORY.generated.md").exists())
            self.assertTrue((persona_dir / "NAVIGATION.generated.md").exists())
            status_payload = json.loads((persona_dir / "ARTIFACT_STATUS.generated.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["status"], "complete")
            nav_text = (persona_dir / "NAVIGATION.generated.md").read_text(encoding="utf-8")
            self.assertIn("SOUL -> GOALS -> STYLE", nav_text)

    def test_installed_verify_host_workflow_reports_complete_after_persona_and_graph_outputs(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            characters_root = tmp_root / "data" / "characters" / "hongloumeng"
            relation_dir = tmp_root / "data" / "relations" / "hongloumeng"
            relation_dir.mkdir(parents=True, exist_ok=True)

            for name in ("林黛玉", "贾宝玉"):
                persona_dir = characters_root / name
                persona_dir.mkdir(parents=True, exist_ok=True)
                (persona_dir / "PROFILE.generated.md").write_text(
                    "# PROFILE\n"
                    f"- name: {name}\n"
                    "- novel_id: hongloumeng\n"
                    "- identity_anchor: 测试\n"
                    "- soul_goal: 测试\n"
                    "- worldview: 测试\n"
                    "- speech_style: 测试\n",
                    encoding="utf-8",
                )
                subprocess.run(
                    [
                        sys.executable,
                        str(dst / "tools" / "materialize_persona_bundle.py"),
                        "--profile-file",
                        str(persona_dir / "PROFILE.generated.md"),
                        "--output",
                        str(tmp_root / f"{name}.json"),
                    ],
                    cwd=dst,
                    check=True,
                    capture_output=True,
                )

            relations_file = relation_dir / "hongloumeng_relations.md"
            relations_file.write_text(
                "# RELATION_GRAPH\n\n"
                "- novel_id: hongloumeng\n\n"
                "## 林黛玉_贾宝玉\n"
                "- trust: 9\n"
                "- affection: 9\n"
                "- hostility: 1\n"
                "- confidence: 8\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "export_relation_graph.py"),
                    "--relations-file",
                    str(relations_file),
                    "--output",
                    str(tmp_root / "graph.json"),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "verify_host_workflow.py"),
                    "--characters-root",
                    str(characters_root),
                    "--characters",
                    "林黛玉,贾宝玉",
                    "--relations-file",
                    str(relations_file),
                    "--output",
                    str(tmp_root / "verify.json"),
                ],
                cwd=dst,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            verify_payload = json.loads((tmp_root / "verify.json").read_text(encoding="utf-8"))
            self.assertEqual(verify_payload["status"], "complete")
            self.assertEqual(len(verify_payload["characters"]), 2)
            self.assertEqual(verify_payload["relation_graph"]["status"], "complete")

    def test_installed_host_run_manifest_tracks_standard_progress_and_artifacts(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "hongloumeng.txt"
            novel_path.write_text("林黛玉见宝玉。宝玉念着黛玉。宝钗从旁调和。", encoding="utf-8")
            manifest_path = tmp_root / "run_manifest.json"

            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "init_host_run.py"),
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "林黛玉,贾宝玉",
                    "--output",
                    str(manifest_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["progress"]["stage"], "characters_locked")
            self.assertEqual(manifest_payload["locked_characters"], ["林黛玉", "贾宝玉"])

            distill_payload_path = tmp_root / "distill_payload.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_prompt_payload.py"),
                    "--mode",
                    "distill",
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "林黛玉,贾宝玉",
                    "--output",
                    str(distill_payload_path),
                    "--run-manifest",
                    str(manifest_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["progress"]["stage"], "distill_payload_ready")
            self.assertEqual(manifest_payload["summary"]["status_text"], "waiting_for_host_generation")
            self.assertIn("chunking", manifest_payload["progress"])

            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "update_run_progress.py"),
                    "--run-manifest",
                    str(manifest_path),
                    "--stage",
                    "character_started",
                    "--character",
                    "林黛玉",
                    "--message",
                    "正在蒸馏林黛玉",
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["progress"]["current_character"], "林黛玉")

            characters_root = tmp_root / "data" / "characters" / "hongloumeng"
            profiles = {
                "林黛玉": "# PROFILE\n- name: 林黛玉\n- novel_id: hongloumeng\n- identity_anchor: 真心与自尊都很重\n- soul_goal: 守住真情\n- worldview: 世情热闹，真心稀薄\n- speech_style: 轻声细语\n",
                "贾宝玉": "# PROFILE\n- name: 贾宝玉\n- novel_id: hongloumeng\n- identity_anchor: 看重真情\n- soul_goal: 留住身边真心的人\n- worldview: 人情比功名更重\n- speech_style: 直接真切\n",
            }
            for name, profile_text in profiles.items():
                persona_dir = characters_root / name
                persona_dir.mkdir(parents=True, exist_ok=True)
                profile_path = persona_dir / "PROFILE.generated.md"
                profile_path.write_text(profile_text, encoding="utf-8")
                subprocess.run(
                    [
                        sys.executable,
                        str(dst / "tools" / "materialize_persona_bundle.py"),
                        "--profile-file",
                        str(profile_path),
                        "--run-manifest",
                        str(manifest_path),
                        "--output",
                        str(tmp_root / f"{name}.json"),
                    ],
                    cwd=dst,
                    check=True,
                    capture_output=True,
                )

            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["progress"]["completed_count"], 2)
            self.assertEqual(manifest_payload["summary"]["characters_completed"], 2)
            self.assertIn("林黛玉", manifest_payload["artifacts"]["character_dirs"])
            self.assertIn("贾宝玉", manifest_payload["artifacts"]["character_dirs"])

            relation_dir = tmp_root / "data" / "relations" / "hongloumeng"
            relation_dir.mkdir(parents=True, exist_ok=True)
            relations_file = relation_dir / "hongloumeng_relations.md"
            relations_file.write_text(
                "# RELATION_GRAPH\n\n"
                "- novel_id: hongloumeng\n\n"
                "## 林黛玉_贾宝玉\n"
                "- trust: 9\n"
                "- affection: 9\n"
                "- hostility: 1\n"
                "- confidence: 8\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "export_relation_graph.py"),
                    "--relations-file",
                    str(relations_file),
                    "--run-manifest",
                    str(manifest_path),
                    "--output",
                    str(tmp_root / "graph.json"),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["progress"]["graph_status"], "complete")
            self.assertTrue(manifest_payload["artifacts"]["relation_graph"]["html_path"].endswith(".html"))

            result = subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "verify_host_workflow.py"),
                    "--characters-root",
                    str(characters_root),
                    "--characters",
                    "林黛玉,贾宝玉",
                    "--relations-file",
                    str(relations_file),
                    "--run-manifest",
                    str(manifest_path),
                    "--output",
                    str(tmp_root / "verify.json"),
                ],
                cwd=dst,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0)

            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest_payload["success"])
            self.assertEqual(manifest_payload["status"], "complete")
            self.assertEqual(manifest_payload["summary"]["status_text"], "workflow_complete")

    def test_installed_distill_payload_detects_incremental_context_and_updates_manifest(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "hongloumeng.txt"
            novel_path.write_text("林黛玉再见宝玉。", encoding="utf-8")
            manifest_path = tmp_root / "run_manifest.json"

            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "init_host_run.py"),
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "林黛玉",
                    "--output",
                    str(manifest_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            persona_dir = tmp_root / "data" / "characters" / "hongloumeng" / "林黛玉"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "PROFILE.generated.md").write_text(
                "# PROFILE\n"
                "- name: 林黛玉\n"
                "- novel_id: hongloumeng\n"
                "- identity_anchor: 真心与自尊都很重\n"
                "- soul_goal: 守住真情\n",
                encoding="utf-8",
            )
            (persona_dir / "MEMORY.md").write_text(
                "# MEMORY\n"
                "- user_edits: 说话更短，不要说教\n",
                encoding="utf-8",
            )

            distill_payload_path = tmp_root / "distill_payload.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_prompt_payload.py"),
                    "--mode",
                    "distill",
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "林黛玉",
                    "--characters-root",
                    str(tmp_root / "data" / "characters"),
                    "--run-manifest",
                    str(manifest_path),
                    "--output",
                    str(distill_payload_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            distill_payload = json.loads(distill_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(distill_payload["request"]["update_mode"], "incremental")
            self.assertIn("林黛玉", distill_payload["request"]["existing_profiles"])
            self.assertIn("说话更短，不要说教", distill_payload["request"]["existing_profiles"]["林黛玉"]["user_edits"])

            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["capabilities"]["distill"]["outputs"]["update_mode"], "incremental")
            self.assertEqual(manifest_payload["capabilities"]["distill"]["outputs"]["existing_character_count"], 1)
            self.assertEqual(manifest_payload["artifacts"]["distill_context"]["update_mode"], "incremental")
            self.assertEqual(manifest_payload["artifacts"]["distill_context"]["existing_character_count"], 1)
            self.assertIn("林黛玉", manifest_payload["artifacts"]["distill_context"]["existing_profile_paths"])

    def test_installed_run_manifest_tracks_chunk_overview_and_chunk_progress(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "long_novel.txt"
            repeated = (
                "林黛玉与贾宝玉在园中对看一眼，各有心事，"
                + ("真情与体面彼此牵扯，试探与怜惜交替翻涌，谁都不肯先把话说破，" * 18)
                + "却又句句都绕着彼此的心事打转。"
            )
            novel_path.write_text(repeated * 420, encoding="utf-8")
            manifest_path = tmp_root / "run_manifest.json"

            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "init_host_run.py"),
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "林黛玉,贾宝玉",
                    "--output",
                    str(manifest_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_prompt_payload.py"),
                    "--mode",
                    "distill",
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "林黛玉,贾宝玉",
                    "--output",
                    str(tmp_root / "distill_payload.json"),
                    "--run-manifest",
                    str(manifest_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["progress"]["chunking"]["distill"]["mode"], "chunked")
            self.assertGreaterEqual(manifest_payload["progress"]["chunking"]["distill"]["chunk_count"], 2)
            self.assertTrue(manifest_payload["summary"]["chunking"]["distill"]["merge_required"])

            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "update_run_progress.py"),
                    "--run-manifest",
                    str(manifest_path),
                    "--stage",
                    "chunk_started",
                    "--message",
                    "正在执行第 1 块",
                    "--chunk-capability",
                    "distill",
                    "--chunk-mode",
                    "chunked",
                    "--chunk-count",
                    "3",
                    "--current-chunk",
                    "1",
                    "--chunk-label",
                    "前段-1",
                    "--chunk-status",
                    "running",
                    "--merge-required",
                    "--merge-status",
                    "pending",
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["progress"]["chunking"]["distill"]["current_chunk"], 1)
            self.assertEqual(manifest_payload["progress"]["chunking"]["distill"]["current_label"], "前段-1")
            self.assertEqual(manifest_payload["progress"]["chunking"]["distill"]["status"], "running")

    def test_installed_distill_payload_supports_chunk_bundle_for_large_excerpt(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "long_novel.txt"
            repeated = (
                "林黛玉与贾宝玉在园中对看一眼，各有心事，"
                + ("真情与体面彼此牵扯，试探与怜惜交替翻涌，谁都不肯先把话说破，" * 18)
                + "却又句句都绕着彼此的心事打转。"
            )
            novel_path.write_text(repeated * 420, encoding="utf-8")

            distill_payload_path = tmp_root / "distill_payload.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_prompt_payload.py"),
                    "--mode",
                    "distill",
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "林黛玉,贾宝玉",
                    "--output",
                    str(distill_payload_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            payload = json.loads(distill_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["request"]["chunk_mode"], "chunked")
            self.assertGreaterEqual(payload["meta"]["chunk_count"], 2)
            self.assertTrue(payload["meta"]["merge_required"])
            self.assertTrue(payload["chunks"])
            self.assertEqual(payload["host_plan"]["execution"], "sequential_chunks_then_merge")
            self.assertEqual(payload["merge_payload"]["mode"], "distill_merge")
            self.assertIn("chunk_drafts", payload["merge_payload"]["request"])

    def test_installed_relation_payload_supports_chunk_bundle_for_large_excerpt(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "long_relation.txt"
            repeated = (
                "齐夏与肖冉互相试探，章晨泽在旁观察局势变化。"
                "三个人的每一句问答都像在试边界、探底牌，也不断暴露各自的判断、怀疑与暂时结盟。"
                "局面表面平静，实则张力一直绷着，谁更信谁、谁更防谁、谁又在暗中改变立场，都在对话细节里慢慢显形。"
            )
            novel_path.write_text(repeated * 360, encoding="utf-8")

            relation_payload_path = tmp_root / "relation_payload.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_prompt_payload.py"),
                    "--mode",
                    "relation",
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "齐夏,肖冉,章晨泽",
                    "--max-sentences",
                    "500",
                    "--max-chars",
                    "50000",
                    "--output",
                    str(relation_payload_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            payload = json.loads(relation_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["request"]["chunk_mode"], "chunked")
            self.assertGreaterEqual(payload["meta"]["chunk_count"], 2)
            self.assertTrue(payload["chunks"])
            self.assertEqual(payload["merge_payload"]["mode"], "relation_merge")
            self.assertEqual(payload["host_plan"]["execution"], "sequential_chunks_then_merge")

    def test_installed_skill_end_to_end_host_workflow(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "hongloumeng.txt"
            novel_path.write_text(
                (
                    "\u6797\u9edb\u7389\u521d\u8fdb\u8d3e\u5e9c\uff0c\u89c1\u8d3e\u5b9d\u7389\u65f6\u5fc3\u751f\u611f\u5e94\u3002"
                    "\u8d3e\u5b9d\u7389\u601c\u60dc\u6797\u9edb\u7389\u7684\u5b64\u51b7\u4e0e\u624d\u60c5\u3002"
                    "\u859b\u5b9d\u9497\u5904\u4e8b\u7a33\u59a5\uff0c\u5e38\u5728\u793c\u6cd5\u4e0e\u60c5\u611f\u95f4\u8c03\u548c\u6c14\u6c1b\u3002"
                ),
                encoding="utf-8",
            )

            excerpt_path = tmp_root / "excerpt.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "prepare_novel_excerpt.py"),
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "\u6797\u9edb\u7389,\u8d3e\u5b9d\u7389",
                    "--max-sentences",
                    "4",
                    "--max-chars",
                    "600",
                    "--output",
                    str(excerpt_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            excerpt_payload = json.loads(excerpt_path.read_text(encoding="utf-8"))
            self.assertIn("\u6797\u9edb\u7389", excerpt_payload["excerpt"])
            self.assertEqual(excerpt_payload["matched_characters"], ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"])

            distill_payload_path = tmp_root / "distill_payload.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_prompt_payload.py"),
                    "--mode",
                    "distill",
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "\u6797\u9edb\u7389,\u8d3e\u5b9d\u7389",
                    "--output",
                    str(distill_payload_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            distill_payload = json.loads(distill_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(distill_payload["mode"], "distill")
            self.assertEqual(distill_payload["request"]["characters"], ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"])
            self.assertIn("output_schema", distill_payload["references"])
            self.assertIn("\u8d3e\u5b9d\u7389", distill_payload["request"]["excerpt"])
            self.assertEqual(
                distill_payload["request"]["excerpt_focus"]["matched_characters"],
                ["\u6797\u9edb\u7389", "\u8d3e\u5b9d\u7389"],
            )

            relation_payload_path = tmp_root / "relation_payload.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_prompt_payload.py"),
                    "--mode",
                    "relation",
                    "--novel",
                    str(novel_path),
                    "--output",
                    str(relation_payload_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            relation_payload = json.loads(relation_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(relation_payload["mode"], "relation")
            self.assertIn("\u859b\u5b9d\u9497", relation_payload["request"]["excerpt"])

            characters_root = tmp_root / "data" / "characters" / "hongloumeng"
            profiles = {
                "\u6797\u9edb\u7389": (
                    "# PROFILE\n"
                    "## Meta\n"
                    "- name: \u6797\u9edb\u7389\n"
                    "- novel_id: hongloumeng\n"
                    f"- source_path: {novel_path.as_posix()}\n"
                    "## Basic Positioning\n"
                    "- core_identity: \u8d3e\u5e9c\u5bc4\u5c45\u95fa\u79c0\n"
                    "- faction_position: \u8d3e\u5e9c\u5185\u7720\n"
                    "- story_role: \u60c5\u611f\u4e2d\u5fc3\n"
                    "- identity_anchor: \u4ee5\u771f\u5fc3\u7167\u4eba\uff0c\u4e5f\u6700\u6015\u771f\u5fc3\u88ab\u8f7b\u6162\n"
                    "## Root Layer\n"
                    "- life_experience: \u5bc4\u4eba\u7bf1\u4e0b\uff1b\u654f\u611f\u591a\u601d\n"
                    "## Inner Core\n"
                    "- soul_goal: \u6c42\u5f97\u4e0d\u88ab\u8f9c\u8d1f\u7684\u771f\u60c5\n"
                    "- core_traits: \u654f\u611f\uff1b\u806a\u6167\uff1b\u6e05\u50b2\n"
                    "- worldview: \u4e16\u60c5\u70ed\u95f9\uff0c\u771f\u5fc3\u5374\u7a00\u8584\n"
                    "- speech_style: \u8f7b\u58f0\u7ec6\u8bed\uff0c\u8bdd\u91cc\u85cf\u950b\n"
                ),
                "\u8d3e\u5b9d\u7389": (
                    "# PROFILE\n"
                    "## Meta\n"
                    "- name: \u8d3e\u5b9d\u7389\n"
                    "- novel_id: hongloumeng\n"
                    f"- source_path: {novel_path.as_posix()}\n"
                    "## Basic Positioning\n"
                    "- core_identity: \u8d3e\u5e9c\u516c\u5b50\n"
                    "- faction_position: \u8d3e\u5e9c\u5185\u7720\n"
                    "- story_role: \u6838\u5fc3\u4e3b\u89d2\n"
                    "- identity_anchor: \u770b\u91cd\u771f\u60c5\uff0c\u4e0d\u613f\u88ab\u4e16\u4fd7\u675f\u7f1a\n"
                    "## Root Layer\n"
                    "- life_experience: \u751f\u4e8e\u9531\u79c0\uff0c\u5374\u53cd\u611f\u79c1\u6b32\u4e0e\u793c\u6cd5\n"
                    "## Inner Core\n"
                    "- soul_goal: \u7559\u4f4f\u8eab\u8fb9\u6700\u771f\u630a\u7684\u4eba\n"
                    "- core_traits: \u70ed\u70c8\uff1b\u6000\u60b2\uff1b\u53cd\u53db\n"
                    "- worldview: \u4eba\u60c5\u6bd4\u529f\u540d\u66f4\u91cd\u8981\n"
                    "- speech_style: \u76f4\u63a5\u771f\u5207\uff0c\u5076\u5c14\u5e26\u5c11\u5e74\u6c14\n"
                ),
            }

            for name, profile_text in profiles.items():
                persona_dir = characters_root / name
                persona_dir.mkdir(parents=True, exist_ok=True)
                profile_path = persona_dir / "PROFILE.generated.md"
                profile_path.write_text(profile_text, encoding="utf-8")
                subprocess.run(
                    [
                        sys.executable,
                        str(dst / "tools" / "materialize_persona_bundle.py"),
                        "--profile-file",
                        str(profile_path),
                        "--output",
                        str(tmp_root / f"{name}.json"),
                    ],
                    cwd=dst,
                    check=True,
                    capture_output=True,
                )
                self.assertTrue((persona_dir / "ARTIFACT_STATUS.generated.json").exists())
                self.assertTrue((persona_dir / "NAVIGATION.generated.md").exists())
                self.assertIn(
                    "SOUL -> GOALS -> STYLE",
                    (persona_dir / "NAVIGATION.generated.md").read_text(encoding="utf-8"),
                )

            relation_dir = tmp_root / "data" / "relations" / "hongloumeng"
            relation_dir.mkdir(parents=True, exist_ok=True)
            relations_file = relation_dir / "hongloumeng_relations.md"
            relations_file.write_text(
                (
                    "# RELATION_GRAPH\n\n"
                    "- novel_id: hongloumeng\n\n"
                    "## \u6797\u9edb\u7389_\u8d3e\u5b9d\u7389\n"
                    "- trust: 9\n"
                    "- affection: 10\n"
                    "- hostility: 1\n"
                    "- confidence: 8\n"
                    "- relation_change: \u5347\u6e29\n"
                    "- typical_interaction: \u8bdd\u91cc\u6709\u8bd5\u63a2\uff0c\u4e5f\u6709\u4e92\u76f8\u601c\u60dc\n"
                ),
                encoding="utf-8",
            )
            graph_payload_path = tmp_root / "graph.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "export_relation_graph.py"),
                    "--relations-file",
                    str(relations_file),
                    "--output",
                    str(graph_payload_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            graph_payload = json.loads(graph_payload_path.read_text(encoding="utf-8"))
            self.assertTrue(Path(graph_payload["html_path"]).exists())
            self.assertTrue(Path(graph_payload["mermaid_path"]).exists())
            self.assertTrue(Path(graph_payload["status_path"]).exists())

            verify_payload_path = tmp_root / "verify.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "verify_host_workflow.py"),
                    "--characters-root",
                    str(characters_root),
                    "--characters",
                    "\u6797\u9edb\u7389,\u8d3e\u5b9d\u7389",
                    "--relations-file",
                    str(relations_file),
                    "--output",
                    str(verify_payload_path),
                ],
                cwd=dst,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            verify_payload = json.loads(verify_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(verify_payload["status"], "complete")
            self.assertEqual(len(verify_payload["characters"]), 2)
            self.assertEqual(verify_payload["relation_graph"]["status"], "complete")
            self.assertEqual(verify_payload["missing_character_dirs"], [])


if __name__ == "__main__":
    unittest.main()
