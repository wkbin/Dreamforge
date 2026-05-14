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
            self.assertTrue((dst / "tools" / "build_persona_autofill_payload.py").exists())
            self.assertTrue((dst / "tools" / "build_dialogue_suggestion_payload.py").exists())
            self.assertTrue((dst / "tools" / "build_scene_recommendation_payload.py").exists())
            self.assertTrue((dst / "tools" / "manage_self_card.py").exists())
            self.assertTrue((dst / "tools" / "export_relation_graph.py").exists())
            self.assertTrue((dst / "tools" / "init_host_run.py").exists())
            self.assertTrue((dst / "tools" / "materialize_persona_bundle.py").exists())
            self.assertTrue((dst / "tools" / "update_run_progress.py").exists())
            self.assertTrue((dst / "tools" / "verify_host_workflow.py").exists())
            self.assertTrue((dst / "examples" / "scene_recommendation_context.example.json").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "novel_preparation.py").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "persona_bundle.py").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "persona_review.py").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "dialogue_payloads.py").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "scene_recommendations.py").exists())
            self.assertTrue((dst / "tools" / "_skill_support" / "workflow_completion.py").exists())
            self.assertFalse((dst / "runtime").exists())

    def test_installed_manage_self_card_supports_blank_random_parse_and_save(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            schema_path = tmp_root / "self_card_schema.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "manage_self_card.py"),
                    "--mode",
                    "blank",
                    "--output",
                    str(schema_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(schema["kind"], "self_card_schema")
            self.assertIn("display_name", schema["fields"])

            random_payload_path = tmp_root / "random_payload.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "manage_self_card.py"),
                    "--mode",
                    "build-random-payload",
                    "--output",
                    str(random_payload_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            random_payload = json.loads(random_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(random_payload["kind"], "self_card_random_payload")
            self.assertTrue(random_payload["messages"])

            response_path = tmp_root / "random_response.txt"
            response_path.write_text(
                json.dumps(
                    {
                        "display_name": "沈拂衣",
                        "scene_identity": "夜里误入书局的借宿客",
                        "interaction_style": "先试探后亲近，气氛微妙但不敌对",
                        "core_identity": "见多识广却不肯轻易交底的游历者",
                        "story_role": "外来搅局者",
                        "identity_anchor": "宁可被误解，也不愿先把底牌摊开",
                        "temperament_type": "冷静克制里藏着一点促狭",
                        "gender": "男性",
                        "age_stage": "青年",
                        "appearance_feature": "常着深色旧衫，眉眼清冷，袖口总收得极利落",
                        "habit_action": "说话前会先抬眼打量对方，指尖偶尔轻敲桌沿",
                        "soul_goal": "在局势失控前找到真正的线头",
                        "hidden_desire": "想遇到一个能听懂弦外之音的人",
                        "inner_conflict": "想靠近人群，却又习惯先留退路",
                        "self_cognition": "知道自己多疑，也知道多疑救过命",
                        "private_self": "独处时会把玩旧玉佩，显得比人前柔软",
                        "speech_style": "话不多，但句句留有余味",
                        "cadence": "慢起句，收尾轻",
                        "typical_lines": "先别急着信我；话说满了反而不好收",
                        "signature_phrases": "先别急；也未必",
                        "sentence_openers": "先说清楚；你再想想",
                        "sentence_endings": "就这样吧；也好",
                        "social_mode": "慢热试探型",
                        "thinking_style": "先看局，再看人",
                        "decision_rules": "先保留余地；再试对方底线",
                        "reward_logic": "只有真诚和胆识值得我加码",
                        "worldview": "热闹的局里，真正值钱的是没说出口的那句话",
                        "belief_anchor": "留一手不是失礼，是自保",
                        "moral_bottom_line": "不拿无辜之人垫背",
                        "restraint_threshold": "一旦有人故意算计弱者就会立刻翻脸",
                        "core_traits": "敏锐；克制；会留后手",
                        "key_bonds": "旧友阿照；下落不明的师兄",
                        "preference_like": "清净角落；能听懂话外音的人；旧书",
                        "dislike_hate": "被逼问底牌；虚张声势的人；拿弱者做筹码",
                        "forbidden_behaviors": "不会轻易赌命；不会先泄露同伴底牌",
                        "stress_response": "越危险越平静，连语气都会更轻",
                        "emotion_model": "情绪收着走，不轻易外露",
                        "anger_style": "越生气越像在讲道理",
                        "joy_style": "只会浅浅一笑，话反而更松一点",
                        "grievance_style": "不诉苦，只把距离拉开",
                        "others_impression": "像个永远还藏着半页真相的人",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cards_root = tmp_root / "cards"
            saved_path = tmp_root / "saved_card.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "manage_self_card.py"),
                    "--mode",
                    "save",
                    "--cards-root",
                    str(cards_root),
                    "--response-file",
                    str(response_path),
                    "--output",
                    str(saved_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            saved = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["kind"], "self_card")
            self.assertEqual(saved["fields"]["display_name"], "沈拂衣")
            self.assertTrue((cards_root / saved["card_id"] / "PROFILE.md").exists())

            saved_path_two = tmp_root / "saved_card_two.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "manage_self_card.py"),
                    "--mode",
                    "save",
                    "--cards-root",
                    str(cards_root),
                    "--response-file",
                    str(response_path),
                    "--output",
                    str(saved_path_two),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            saved_two = json.loads(saved_path_two.read_text(encoding="utf-8"))
            self.assertNotEqual(saved["card_id"], saved_two["card_id"])

    def test_installed_persona_autofill_tool_builds_plan_and_parses_result(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            persona_dir = tmp_root / "data" / "characters" / "mdzs" / "江澄"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "PROFILE.generated.md").write_text(
                "# PROFILE\n"
                "- name: 江澄\n"
                "- novel_id: mdzs\n"
                "- core_identity: 云梦江氏家主\n"
                "- story_role: 核心配角\n"
                "- speech_style: 冷硬直截\n"
                "- worldview: 责任比喜欢更重要\n",
                encoding="utf-8",
            )

            plan_path = tmp_root / "autofill_plan.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_persona_autofill_payload.py"),
                    "--persona-dir",
                    str(persona_dir),
                    "--field",
                    "key_bonds",
                    "--strategy",
                    "auto",
                    "--output",
                    str(plan_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["kind"], "persona_autofill_plan")
            self.assertEqual(plan["field"], "key_bonds")
            self.assertTrue(plan["steps"])
            self.assertEqual(plan["steps"][0]["source_mode"], "model_knowledge")
            self.assertEqual(len(plan["steps"]), 1)
            self.assertFalse(plan["web_collection_enabled"])
            self.assertIn("retry_messages", plan["host_hint"])

            result_path = tmp_root / "autofill_result.json"
            response_path = tmp_root / "autofill_response.txt"
            response_path.write_text('{"status":"filled","value":"魏无羡（前师弟/执念对象）；江厌离（姐姐/精神支柱）","reason":"角色关系稳定。"}', encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_persona_autofill_payload.py"),
                    "--response-file",
                    str(response_path),
                    "--output",
                    str(result_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(result["parsed"]["status"], "filled")
            self.assertIn("魏无羡", result["parsed"]["value"])

    def test_installed_dialogue_suggestion_tool_builds_bundle_and_parses_result(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            context_path = tmp_root / "context.json"
            context_path.write_text(
                json.dumps(
                    {
                        "mode": "insert",
                        "speaker": "沈拂衣",
                        "seed_text": "",
                        "participants": ["魏无羡", "蓝忘机"],
                        "history": [
                            {"speaker": "魏无羡", "message": "你刚才为什么突然停下？"},
                            {"speaker": "蓝忘机", "message": "前面有人。"},
                        ],
                        "relation_excerpt": "魏无羡与蓝忘机之间已有默契，但对外来者仍保持警惕。",
                        "user_persona": {
                            "display_name": "沈拂衣",
                            "scene_identity": "临时同行者",
                            "interaction_style": "先试探再靠近",
                            "core_identity": "谨慎的外来者",
                            "speech_style": "轻声试探，句子不长",
                            "soul_goal": "先确认对方立场，再决定是否交底",
                        },
                        "persona_contexts": [
                            {
                                "name": "魏无羡",
                                "preview": {"display_name": "魏无羡", "speech_style": "轻快带笑"},
                                "profile": {"core_identity": "夷陵老祖", "speech_style": "轻快带笑"},
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            bundle_path = tmp_root / "suggest_bundle.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_dialogue_suggestion_payload.py"),
                    "--context-file",
                    str(context_path),
                    "--output",
                    str(bundle_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(bundle["kind"], "dialogue_suggestion_bundle")
            self.assertEqual(bundle["payload"]["mode"], "insert")
            self.assertTrue(bundle["messages"])
            self.assertTrue(bundle["compact_messages"])

            result_path = tmp_root / "suggest_result.json"
            response_path = tmp_root / "suggest_response.txt"
            response_path.write_text('{"suggestion":"那我先不往前走，你们谁先告诉我，前面到底是人还是局？"}', encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_dialogue_suggestion_payload.py"),
                    "--response-file",
                    str(response_path),
                    "--output",
                    str(result_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertIn("前面到底是人还是局", result["suggestion"])

    def test_installed_dialogue_suggestion_tool_rejects_invalid_mode(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            context_path = tmp_root / "bad_context.json"
            context_path.write_text(
                json.dumps(
                    {
                        "mode": "scene_push",
                        "participants": ["林黛玉"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_dialogue_suggestion_payload.py"),
                    "--context-file",
                    str(context_path),
                ],
                cwd=dst,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsupported dialogue suggestion mode", result.stderr)

    def test_installed_scene_recommendation_tool_builds_bundle(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            context_path = tmp_root / "scene_context.json"
            context_path.write_text(
                json.dumps(
                    {
                        "mode": "observe",
                        "participants": ["魏无羡", "蓝忘机", "江澄"],
                        "current_scene_card_id": "garden",
                        "current_scene": {
                            "title": "后园僵持",
                            "location": "后园",
                            "time_hint": "傍晚",
                            "atmosphere": "气氛发紧",
                        },
                        "runtime_state_overview": {
                            "location": "后园",
                            "time_hint": "傍晚",
                            "beat_maturity": 82,
                            "should_offer_scene_shift": True,
                            "scene_shift_reason": "这边该说的话已经说尽了",
                        },
                        "transcript": [
                            {"message": "魏无羡没再笑。"},
                            {"message": "江澄也没继续留人。"},
                        ],
                        "scene_cards": [
                            {
                                "card_id": "garden",
                                "fields": {
                                    "title": "后园僵持",
                                    "location": "后园",
                                    "time_hint": "傍晚",
                                    "atmosphere": "气氛发紧",
                                    "opening_situation": "人都站着没动。",
                                    "scene_drive": "继续僵持",
                                },
                            },
                            {
                                "card_id": "hall",
                                "fields": {
                                    "title": "回厅再坐",
                                    "location": "前厅",
                                    "time_hint": "入夜",
                                    "atmosphere": "表面平静，底下仍压着话头",
                                    "opening_situation": "人重新入席，谁都没先开口。",
                                    "scene_drive": "借换场逼近摊牌",
                                },
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            bundle_path = tmp_root / "scene_bundle.json"
            subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_scene_recommendation_payload.py"),
                    "--context-file",
                    str(context_path),
                    "--output",
                    str(bundle_path),
                ],
                cwd=dst,
                check=True,
                capture_output=True,
            )

            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(bundle["kind"], "dialogue_scene_recommendation_bundle")
            self.assertEqual(bundle["payload"]["recommended_card_id"], "hall")
            self.assertTrue(bundle["payload"]["recommended_transition_message"])
            self.assertTrue(bundle["payload"]["recommended_auto_continue_message"])

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
            self.assertIn("status_path", payload)
            self.assertTrue(Path(payload["status_path"]).exists())
            self.assertIn("mini_relations.html", payload["html_path"])
            self.assertIn("mini_relations.mermaid.md", payload["mermaid_path"])
            mermaid_text = mermaid_path.read_text(encoding="utf-8")
            html_text = html_path.read_text(encoding="utf-8")
            self.assertTrue((relation_dir / "mermaid-11.14.0.min.js").exists())
            self.assertIn("linkStyle 0", mermaid_text)
            self.assertNotIn(";;", mermaid_text)
            self.assertIn("mermaid-11.14.0.min.js", html_text)
            self.assertNotIn("cdn.jsdelivr.net", html_text)

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

    def test_installed_build_prompt_payload_emits_stderr_warning_and_verbose_summary_for_no_match(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "novel.txt"
            repeated = "前文只有旁白，谁都没有真正露面，局势像蒙着一层雾，所有人都在绕圈试探却始终不落到目标角色身上。"
            novel_path.write_text((repeated + "。") * 320, encoding="utf-8")
            payload_path = tmp_root / "distill_payload.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(dst / "tools" / "build_prompt_payload.py"),
                    "--mode",
                    "distill",
                    "--novel",
                    str(novel_path),
                    "--characters",
                    "齐夏",
                    "--max-sentences",
                    "500",
                    "--max-chars",
                    "50000",
                    "--output",
                    str(payload_path),
                    "--verbose",
                ],
                cwd=dst,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["request"]["chunk_mode"], "chunked")
            self.assertEqual(payload["request"]["excerpt_focus"]["matched_characters"], [])
            self.assertIn("未匹配到任何目标角色", payload["meta"]["warnings"][0])
            self.assertTrue(any("chunk 分块" in item for item in payload["meta"]["warnings"]))
            self.assertIn("[build_prompt_payload] warning(", result.stderr)
            self.assertIn("warning(chunk_fallback)", result.stderr)
            self.assertIn("mode=distill", result.stderr)
            self.assertIn("matched=[]", result.stderr)

    def test_installed_skill_end_to_end_host_workflow(self):
        repo_root = Path(__file__).resolve().parents[1]
        packaged_src = repo_root / "zaomeng-skill"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            dst = copy_skill_bundle(packaged_src, tmp_root, "zaomeng-skill")
            novel_path = tmp_root / "hongloumeng.txt"
            novel_path.write_text(
                (
                    "林黛玉初进贾府，见贾宝玉时心生感应。"
                    "贾宝玉怜惜林黛玉的孤冷与才情。"
                    "薛宝钗处事稳妥，常在礼法与情感间调和气氛。"
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
                    "林黛玉,贾宝玉",
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
            self.assertIn("林黛玉", excerpt_payload["excerpt"])
            self.assertEqual(excerpt_payload["matched_characters"], ["林黛玉", "贾宝玉"])

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
            distill_payload = json.loads(distill_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(distill_payload["mode"], "distill")
            self.assertEqual(distill_payload["request"]["characters"], ["林黛玉", "贾宝玉"])
            self.assertIn("output_schema", distill_payload["references"])
            self.assertIn("贾宝玉", distill_payload["request"]["excerpt"])
            self.assertEqual(
                distill_payload["request"]["excerpt_focus"]["matched_characters"],
                ["林黛玉", "贾宝玉"],
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
            self.assertIn("薛宝钗", relation_payload["request"]["excerpt"])

            characters_root = tmp_root / "data" / "characters" / "hongloumeng"
            profiles = {
                "林黛玉": (
                    "# PROFILE\n"
                    "## Meta\n"
                    "- name: 林黛玉\n"
                    "- novel_id: hongloumeng\n"
                    f"- source_path: {novel_path.as_posix()}\n"
                    "## Basic Positioning\n"
                    "- core_identity: 贾府寄居闺秀\n"
                    "- faction_position: 贾府内眠\n"
                    "- story_role: 情感中心\n"
                    "- identity_anchor: 以真心照人，也最怕真心被轻慢\n"
                    "## Root Layer\n"
                    "- life_experience: 寄人篱下；敏感多思\n"
                    "## Inner Core\n"
                    "- soul_goal: 求得不被辜负的真情\n"
                    "- core_traits: 敏感；聪慧；清傲\n"
                    "- worldview: 世情热闹，真心却稀薄\n"
                    "- speech_style: 轻声细语，话里藏锋\n"
                ),
                "贾宝玉": (
                    "# PROFILE\n"
                    "## Meta\n"
                    "- name: 贾宝玉\n"
                    "- novel_id: hongloumeng\n"
                    f"- source_path: {novel_path.as_posix()}\n"
                    "## Basic Positioning\n"
                    "- core_identity: 贾府公子\n"
                    "- faction_position: 贾府内眠\n"
                    "- story_role: 核心主角\n"
                    "- identity_anchor: 看重真情，不愿被世俗束缚\n"
                    "## Root Layer\n"
                    "- life_experience: 生于锱秀，却反感私欲与礼法\n"
                    "## Inner Core\n"
                    "- soul_goal: 留住身边最真挊的人\n"
                    "- core_traits: 热烈；怀悲；反叛\n"
                    "- worldview: 人情比功名更重要\n"
                    "- speech_style: 直接真切，偶尔带少年气\n"
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
                    "## 林黛玉_贾宝玉\n"
                    "- trust: 9\n"
                    "- affection: 10\n"
                    "- hostility: 1\n"
                    "- confidence: 8\n"
                    "- relation_change: 升温\n"
                    "- typical_interaction: 话里有试探，也有互相怜惜\n"
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
                    "林黛玉,贾宝玉",
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
