import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.exceptions import LLMRequestError
from src.web.chat.helpers import parse_dialogue_suggestion
from src.web.workflow import WebRunService

try:
    from fastapi.testclient import TestClient
    from src.web.app import create_app
except Exception:  # pragma: no cover - optional test dependency guard
    TestClient = None
    create_app = None


class WebRunServiceTests(unittest.TestCase):
    def test_service_prefers_storage_root_env_when_explicit_root_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage_root = Path(tmp) / "custom-storage"
            with patch.dict(os.environ, {"ZAOMENG_STORAGE_DIR": str(storage_root)}, clear=False):
                service = WebRunService()

            self.assertEqual(service.storage_root, storage_root)
            self.assertEqual(service.runs_root, storage_root / "runs")
            self.assertEqual(service.settings_path, storage_root / "model_settings.json")
            self.assertTrue(service.runs_root.exists())

    def test_build_distill_chunk_payloads_splits_large_excerpt(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.DISTILL_CHUNK_MAX_CHARS = 24
            service.DISTILL_CHUNK_MAX_SENTENCES = 2
            payload = {
                "prompt": "system",
                "references": {},
                "request": {
                    "excerpt": "第一句很长很长。第二句也很长很长。第三句依旧很长很长。第四句还是很长很长。",
                    "excerpt_stages": {
                        "start": "第一句很长很长。第二句也很长很长。",
                        "mid": "第三句依旧很长很长。第四句还是很长很长。",
                        "end": "",
                    },
                    "excerpt_focus": {"strategy": "character_windows"},
                },
                "meta": {},
            }

            chunks = service._build_distill_chunk_payloads(payload)

            self.assertGreaterEqual(len(chunks), 2)
            self.assertTrue(all(item["payload"]["request"]["excerpt"] for item in chunks))
            self.assertTrue(any(str(item["label"]).startswith("前段") for item in chunks))

    def test_chunk_parallel_workers_stays_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            config = Mock()
            config.get = Mock(side_effect=lambda key, default=None: {"llm.provider": "openai-compatible", "llm.parallel_chunk_workers": 3}.get(key, default))
            self.assertEqual(service._chunk_parallel_workers(config=config, chunk_total=1), 1)
            self.assertEqual(service._chunk_parallel_workers(config=config, chunk_total=2), 2)
            self.assertEqual(service._chunk_parallel_workers(config=config, chunk_total=5), 3)

    def test_generate_character_profile_markdown_falls_back_to_chunked_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            manifest_path = Path(tmp) / "run_manifest.json"
            manifest_path.write_text(
                json.dumps({"control": {"stop_requested": False}}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            payload = {
                "prompt": "system",
                "references": {
                    "output_schema": "schema",
                    "style_differ": "style",
                    "logic_constraint": "logic",
                    "validation_policy": "policy",
                },
                "request": {
                    "excerpt": "甲说。乙说。",
                    "excerpt_stages": {"start": "甲说。", "mid": "乙说。", "end": ""},
                    "excerpt_focus": {"strategy": "character_windows"},
                },
                "meta": {"novel_id": "demo"},
            }
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                side_effect=[
                    LLMRequestError("LLM 连接失败: [WinError 10054]"),
                    {"content": "# PROFILE\n- name: 甲\n- speech_style: 先压住再开口\n"},
                    {"content": "# PROFILE\n- name: 甲\n- speech_style: 句尾收得很轻\n"},
                    {"content": "# PROFILE\n- name: 甲\n- speech_style: 先压住再开口，句尾收得很轻\n"},
                ]
            )

            with patch.object(
                service,
                "_build_distill_chunk_payloads",
                return_value=[
                    {"label": "前段", "payload": payload},
                    {"label": "中段", "payload": payload},
                ],
            ):
                content, meta = service._generate_character_profile_markdown(
                    parts=fake_parts,
                    config=Mock(get=Mock(side_effect=lambda key, default=None: default)),
                    manifest_path=manifest_path,
                    payload=payload,
                    character="甲",
                    peer_characters=["甲", "乙"],
                )

            self.assertIn("speech_style", content)
            self.assertTrue(meta["chunked"])
            self.assertEqual(meta["chunk_count"], 2)
            self.assertEqual(fake_parts.llm.chat_completion.call_count, 4)

    def test_generate_relation_markdown_falls_back_to_chunked_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            manifest_path = Path(tmp) / "run_manifest.json"
            manifest_path.write_text(
                json.dumps({"control": {"stop_requested": False}}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            payload = {
                "prompt": "system",
                "references": {
                    "output_schema": "schema",
                    "logic_constraint": "logic",
                    "validation_policy": "policy",
                },
                "request": {
                    "excerpt": "甲见乙。乙应甲。",
                    "excerpt_stages": {"start": "甲见乙。", "mid": "乙应甲。", "end": ""},
                    "excerpt_focus": {"strategy": "character_windows"},
                },
                "meta": {"novel_id": "demo"},
            }
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                side_effect=[
                    LLMRequestError("LLM 连接失败: [WinError 10054]"),
                    {"content": "# RELATION_GRAPH\n\n## 甲_乙\n- trust: 7\n- affection: 3\n- power_gap: 0\n- conflict_point: 立场试探\n- typical_interaction: 观察与回应\n- hidden_attitude: \n- relation_change: 固化\n- appellation_to_target: 乙\n- confidence: 7\n"},
                    {"content": "# RELATION_GRAPH\n\n## 甲_乙\n- trust: 8\n- affection: 4\n- power_gap: 0\n- conflict_point: 互相试探\n- typical_interaction: 追问与回应\n- hidden_attitude: \n- relation_change: 升温\n- appellation_to_target: 乙\n- confidence: 7\n"},
                    {"content": "# RELATION_GRAPH\n\n## 甲_乙\n- trust: 8\n- affection: 4\n- power_gap: 0\n- conflict_point: 互相试探\n- typical_interaction: 观察、追问与回应\n- hidden_attitude: \n- relation_change: 反复波动\n- appellation_to_target: 乙\n- confidence: 8\n"},
                ]
            )

            with patch.object(
                service,
                "_build_relation_chunk_payloads",
                return_value=[
                    {"label": "前段", "payload": payload},
                    {"label": "中段", "payload": payload},
                ],
            ):
                content, meta = service._generate_relation_markdown(
                    parts=fake_parts,
                    config=Mock(get=Mock(side_effect=lambda key, default=None: default)),
                    manifest_path=manifest_path,
                    payload=payload,
                    characters=["甲", "乙"],
                )

            self.assertIn("RELATION_GRAPH", content)
            self.assertTrue(meta["chunked"])
            self.assertEqual(meta["chunk_count"], 2)
            self.assertEqual(fake_parts.llm.chat_completion.call_count, 4)

    def test_finalize_generated_profile_source_backfills_evidence_counts_from_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            source_path = Path(tmp) / "PROFILE.generated.md"
            source_path.write_text(
                "# PROFILE\n"
                "- name: 魏无羡\n"
                "- novel_id: 魔道祖师\n"
                "- worldview: 人心自有轻重。\n"
                "- description_count: 0\n"
                "- dialogue_count: 0\n"
                "- thought_count: 0\n"
                "- chunk_count: 0\n"
                "- evidence_source: \n",
                encoding="utf-8",
            )
            payload = {
                "request": {
                    "excerpt": "魏无羡笑道：“先别慌。”\n江澄心想此事绝不简单。\n夷陵风声渐紧。",
                    "excerpt_stages": {"start": "魏无羡笑道：“先别慌。”", "mid": "江澄心想此事绝不简单。", "end": "夷陵风声渐紧。"},
                    "excerpt_focus": {"strategy": "character_windows_mixed"},
                }
            }

            service._finalize_generated_profile_source(source_path, payload=payload, chunk_count=3)
            content = source_path.read_text(encoding="utf-8")

            self.assertIn("- description_count: 1", content)
            self.assertIn("- dialogue_count: 1", content)
            self.assertIn("- thought_count: 1", content)
            self.assertIn("- chunk_count: 3", content)
            self.assertIn("- evidence_source: excerpt:start；excerpt:mid；excerpt:end；strategy:character_windows_mixed", content)

    def test_profile_repair_triggers_when_completion_fields_are_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            source_path = Path(tmp) / "PROFILE.generated.md"
            source_path.write_text(
                "# PROFILE\n"
                "- name: 魏无羡\n"
                "- novel_id: 魔道祖师\n"
                "- worldview: 人心自有轻重。\n"
                "- belief_anchor: 人总得护住自己想护的。\n"
                "- moral_bottom_line: 不会主动把无辜者推进死局。\n"
                "- restraint_threshold: 真被逼到绝路时会掀桌。\n"
                "- stress_response: 压得越狠越像没事。\n"
                "- speech_style: 先笑后刺。\n",
                encoding="utf-8",
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(return_value={"content": "# PROFILE\n- name: 魏无羡\n- soul_goal: 护住该护的人\n"})
            payload = {
                "prompt": "系统提示",
                "references": {"output_schema": "schema", "style_differ": "style", "logic_constraint": "logic", "validation_policy": "policy"},
                "request": {
                    "excerpt": "魏无羡笑道：“先别慌。”\n江澄心想此事绝不简单。\n夷陵风声渐紧。",
                    "excerpt_stages": {"start": "魏无羡笑道：“先别慌。”", "mid": "江澄心想此事绝不简单。", "end": "夷陵风声渐紧。"},
                    "excerpt_focus": {"strategy": "character_windows_mixed"},
                },
                "meta": {"novel_id": "魔道祖师"},
            }

            repaired = service._maybe_repair_generated_profile(
                parts=fake_parts,
                config=Mock(get=Mock(side_effect=lambda key, default=None: default)),
                payload=payload,
                character="魏无羡",
                peer_characters=["魏无羡", "蓝忘机"],
                source_path=source_path,
            )

            self.assertIsNotNone(repaired)
            self.assertGreaterEqual(fake_parts.llm.chat_completion.call_count, 1)

    def test_extract_dialogue_evidence_prioritizes_character_specific_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            payload = {
                "request": {
                    "excerpt": "\n".join(
                        [
                            "袭人笑道：“今日倒热闹。”",
                            "麝月道：“且先坐下。”",
                            "众人都笑了起来。",
                            "薛宝钗笑道：“这话也太急了些。”",
                            "宝钗心想此事还得再看一步。",
                            "探春道：“先把话说清楚。”",
                        ]
                    ),
                    "excerpt_stages": {
                        "start": "袭人笑道：“今日倒热闹。”\n麝月道：“且先坐下。”",
                        "mid": "薛宝钗笑道：“这话也太急了些。”\n宝钗心想此事还得再看一步。",
                        "end": "探春道：“先把话说清楚。”",
                    },
                }
            }

            evidence = service._extract_dialogue_evidence(payload, character="薛宝钗")

            self.assertGreaterEqual(len(evidence), 2)
            self.assertEqual(evidence[0], "薛宝钗笑道：“这话也太急了些。”")
            self.assertEqual(evidence[1], "宝钗心想此事还得再看一步。")

    def test_extract_dialogue_evidence_matches_traditional_character_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            payload = {
                "request": {
                    "excerpt": "薛寶釵笑道：「你先别急。」\n眾人一时无话。",
                    "excerpt_stages": {
                        "start": "薛寶釵笑道：「你先别急。」",
                        "mid": "",
                        "end": "",
                    },
                }
            }

            evidence = service._extract_dialogue_evidence(payload, character="薛宝钗")

            self.assertIn("薛寶釵笑道：「你先别急。」", evidence)

    def test_model_settings_must_be_configured_before_create_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            with self.assertRaisesRegex(ValueError, "Model is not configured yet."):
                service.create_run(
                    novel_name="hongloumeng.txt",
                    novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    characters=["林黛玉"],
                )

            settings = service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            self.assertTrue(settings["configured"])

    def test_get_app_update_status_reports_available_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            with patch.object(
                service,
                "_discover_launcher_metadata",
                return_value={
                    "launcher_path": "/home/test/.local/bin/zaomeng",
                    "repo_slug": "wkbin/zaomeng",
                    "repo_ref": "main",
                },
            ), patch.object(service, "_read_local_app_version", return_value="20260508100000"), patch.object(
                service,
                "_fetch_remote_app_version",
                return_value="20260510120000",
            ):
                status = service.get_app_update_status(force_check=True)

            self.assertTrue(status["supported"])
            self.assertTrue(status["update_available"])
            self.assertEqual(status["current_version"], "20260508100000")
            self.assertEqual(status["remote_version"], "20260510120000")

    def test_start_app_update_runs_in_background_and_marks_reload_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            with patch.object(
                service,
                "_discover_launcher_metadata",
                return_value={
                    "launcher_path": "/home/test/.local/bin/zaomeng",
                    "repo_slug": "wkbin/zaomeng",
                    "repo_ref": "main",
                },
            ), patch.object(
                service,
                "_read_local_app_version",
                side_effect=["20260508100000", "20260510120000"],
            ), patch.object(
                service,
                "_fetch_remote_app_version",
                side_effect=["20260510120000", "20260510120000"],
            ), patch("src.web.service_facades.system_update.subprocess.run") as run_update:
                run_update.return_value = Mock(returncode=0, stdout="updated", stderr="")
                started = service.start_app_update()
                self.assertEqual(started["status"], "updating")
                self.assertIsNotNone(service._app_update_thread)
                service._app_update_thread.join(timeout=2)
                finished = service.get_app_update_status()

            self.assertEqual(finished["status"], "completed")
            self.assertTrue(finished["reload_required"])
            self.assertFalse(finished["update_available"])

    def test_create_run_builds_manifest_and_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。薛宝钗也在场。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉", "薛宝钗"],
            )

            self.assertEqual(payload["entrypoint"], "webui")
            self.assertEqual(payload["progress"]["stage"], "relation_payload_ready")
            self.assertEqual(payload["summary"]["status_text"], "waiting_for_host_generation")
            self.assertEqual(payload["locked_characters"], ["林黛玉", "贾宝玉", "薛宝钗"])
            self.assertEqual(payload["novel_sources"][0]["kind"], "initial")
            self.assertGreater(payload["novel_sources"][0]["byte_size"], 0)
            self.assertGreater(payload["novel_sources"][0]["char_count"], 0)
            self.assertIn("quality", payload)
            self.assertIn("excerpt_focus", payload["quality"])
            self.assertIn("chunking", payload["progress"])
            self.assertIn("chunking", payload["summary"])
            self.assertIn("chunking", payload["artifacts"])
            self.assertIn("distill", payload["artifacts"]["chunking"])
            self.assertIn("relation", payload["artifacts"]["chunking"])

            run_dir = Path(tmp) / "runs" / payload["run_id"]
            self.assertTrue((run_dir / "run_manifest.json").exists())
            self.assertTrue((run_dir / "payloads" / "distill_payload.json").exists())
            self.assertTrue((run_dir / "payloads" / "relation_payload.json").exists())
            self.assertIn("payload_distill", payload["file_urls"])
            self.assertIn("payload_relation", payload["file_urls"])

    def test_create_run_auto_run_starts_background_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            with patch.object(service, "_start_background_run") as start_background_run:
                payload = service.create_run(
                    novel_name="hongloumeng.txt",
                    novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    characters=["林黛玉", "贾宝玉"],
                    auto_run=True,
                )

            self.assertEqual(payload["status"], "running")
            self.assertEqual(payload["progress"]["stage"], "characters_locked")
            start_background_run.assert_called_once()

    def test_restart_run_distill_reuses_existing_novel_and_starts_background_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            with patch.object(service, "_start_background_run") as start_background_run:
                refreshed = service.restart_run_distill(
                    payload["run_id"],
                    characters=["林黛玉", "王熙凤"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertEqual(refreshed["status"], "running")
            self.assertEqual(refreshed["locked_characters"], ["林黛玉", "王熙凤"])
            self.assertEqual(refreshed["progress"]["stage"], "characters_locked")
            self.assertIn("待完成 2 人", refreshed["redistill"]["summary"])
            start_background_run.assert_called_once()

    def test_restart_run_distill_accepts_new_source_segment_for_incremental_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng-1.txt",
                novel_content_base64=base64.b64encode("第一章里林黛玉初见贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            persona_dir = run_dir / "artifacts" / "characters" / "hongloumeng-1" / "林黛玉"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "PROFILE.generated.md").write_text("- name: 林黛玉\n", encoding="utf-8")
            service.refresh_run(payload["run_id"])

            with patch.object(service, "_start_background_run") as start_background_run:
                refreshed = service.restart_run_distill(
                    payload["run_id"],
                    characters=["林黛玉", "薛宝钗"],
                    novel_name="hongloumeng-2.txt",
                    novel_content_base64=base64.b64encode("第二章里宝钗登场，黛玉再见宝玉。".encode("utf-8")).decode("ascii"),
                )

            self.assertTrue(refreshed["redistill"]["used_new_source"])
            self.assertEqual(refreshed["redistill"]["existing_characters"], ["林黛玉"])
            self.assertEqual(refreshed["redistill"]["new_characters"], ["薛宝钗"])
            self.assertEqual(refreshed["redistill"]["relation_characters"], ["林黛玉", "薛宝钗"])
            self.assertIn("增量 1 人", refreshed["redistill"]["summary"])
            self.assertIn("updates", refreshed["novel_path"])
            self.assertEqual(refreshed["novel_sources"][-1]["kind"], "incremental_update")
            self.assertGreater(refreshed["novel_sources"][-1]["byte_size"], 0)
            self.assertGreater(refreshed["novel_sources"][-1]["char_count"], 0)
            start_background_run.assert_called_once()

    def test_restart_run_distill_preserves_completed_characters_when_reusing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉先出场，后面宝钗还没来。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "薛宝钗"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            persona_dir = run_dir / "artifacts" / "characters" / "hongloumeng" / "林黛玉"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "PROFILE.generated.md").write_text("- name: 林黛玉\n", encoding="utf-8")
            service.refresh_run(payload["run_id"])

            with patch.object(service, "_start_background_run") as start_background_run:
                refreshed = service.restart_run_distill(
                    payload["run_id"],
                    characters=["林黛玉", "薛宝钗"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertFalse(refreshed["redistill"]["used_new_source"])
            self.assertEqual(refreshed["redistill"]["resume_completed_characters"], ["林黛玉"])
            self.assertEqual(refreshed["redistill"]["pending_characters"], ["薛宝钗"])
            self.assertEqual(refreshed["progress"]["completed_characters"], ["林黛玉"])
            self.assertEqual(refreshed["progress"]["completed_count"], 1)
            self.assertEqual(refreshed["summary"]["characters_completed"], 1)
            self.assertIn("待完成 1 人", refreshed["redistill"]["summary"])
            start_background_run.assert_called_once()

    def test_delete_run_group_removes_same_novel_runs_and_dialogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            first = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            second = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("宝钗也在场。".encode("utf-8")).decode("ascii"),
                characters=["薛宝钗"],
            )
            third = service.create_run(
                novel_name="sanguo.txt",
                novel_content_base64=base64.b64encode("刘备见关羽。".encode("utf-8")).decode("ascii"),
                characters=["刘备"],
            )

            first_dialogue_dir = Path(tmp) / "runs" / first["run_id"] / "dialogue" / "dlg-a"
            second_dialogue_dir = Path(tmp) / "runs" / second["run_id"] / "dialogue" / "dlg-b"
            first_dialogue_dir.mkdir(parents=True, exist_ok=True)
            second_dialogue_dir.mkdir(parents=True, exist_ok=True)
            for run in (first, second, third):
                manifest_path = Path(tmp) / "runs" / run["run_id"] / "run_manifest.json"
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                payload["status"] = "ready"
                manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            payload = service.delete_run_group(first["run_id"])

            self.assertEqual(payload["status"], "deleted")
            self.assertEqual(payload["deleted_run_count"], 2)
            self.assertEqual(payload["deleted_session_count"], 2)
            self.assertFalse((Path(tmp) / "runs" / first["run_id"]).exists())
            self.assertFalse((Path(tmp) / "runs" / second["run_id"]).exists())
            self.assertTrue((Path(tmp) / "runs" / third["run_id"]).exists())

    def test_delete_run_group_rejects_running_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            with patch.object(service, "_start_background_run"):
                run = service.create_run(
                    novel_name="hongloumeng.txt",
                    novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    characters=["林黛玉"],
                    auto_run=True,
                )

            with self.assertRaisesRegex(ValueError, "暂时不能删除"):
                service.delete_run_group(run["run_id"])

    def test_stop_run_marks_manifest_and_blocks_non_running_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            with patch.object(service, "_start_background_run"):
                run = service.create_run(
                    novel_name="hongloumeng.txt",
                    novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    characters=["林黛玉"],
                    auto_run=True,
                )

            stopped = service.stop_run(run["run_id"])
            self.assertTrue(stopped["control"]["stop_requested"])
            self.assertEqual(stopped["summary"]["status_text"], "stop_requested")
            self.assertIn("正在收束当前步骤", stopped["progress"]["message"])

            manifest_path = Path(tmp) / "runs" / run["run_id"] / "run_manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["status"] = "ready"
            manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "只有正在蒸馏的书卷才能停止"):
                service.stop_run(run["run_id"])

    def test_automatic_pipeline_returns_stopped_when_stop_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "hongloumeng.txt"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["control"]["stop_requested"] = True
            manifest["control"]["stop_requested_at"] = "2026-05-07T00:00:00Z"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            with patch("src.web.workflow.build_runtime_parts") as build_parts:
                fake_parts = Mock()
                fake_parts.llm.chat_completion = Mock()
                build_parts.return_value = fake_parts
                result = service._run_automatic_pipeline(
                    manifest_path=manifest_path,
                    novel_path=novel_path,
                    locked_characters=["林黛玉"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertEqual(result["status"], "stopped")
            self.assertEqual(result["summary"]["status_text"], "stopped")
            self.assertEqual(result["progress"]["stage"], "stopped")
            self.assertTrue(result["control"]["stop_acknowledged_at"])

    def test_get_run_reconciles_detached_stop_requested_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run_dir = Path(tmp) / "runs" / "run-oldstop"
            run_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = run_dir / "run_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-oldstop",
                        "novel_id": "魔道祖师",
                        "status": "running",
                        "success": False,
                        "progress": {
                            "stage": "distilling",
                            "message": "已收到停止请求，正在收束当前步骤",
                            "current_character": "魏无羡",
                        },
                        "summary": {"status_text": "stop_requested"},
                        "control": {
                            "stop_requested": True,
                            "stop_requested_at": "2026-05-07T10:14:54.453675Z",
                        },
                        "timing": {
                            "started_at": "2026-05-07T10:03:50.967231Z",
                            "completed_at": "",
                            "failed_at": "",
                            "elapsed_seconds": 0.0,
                            "elapsed_text": "",
                        },
                        "events": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            payload = service.get_run("run-oldstop")

            self.assertEqual(payload["status"], "stopped")
            self.assertEqual(payload["summary"]["status_text"], "stopped")
            self.assertEqual(payload["progress"]["stage"], "stopped")
            self.assertIn("魏无羡", payload["progress"]["message"])

    def test_automatic_pipeline_uses_union_cast_for_graph_on_redistill(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉，王熙凤后至。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "hongloumeng.txt"

            class _FakePathProvider:
                def __init__(self, base_dir: Path) -> None:
                    self.base_dir = base_dir

                def characters_root(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "characters" / novel_id
                    path.mkdir(parents=True, exist_ok=True)
                    return path

                def relations_file(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "relations" / f"{novel_id}_relations.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return path

            fake_parts = Mock()
            fake_parts.path_provider = _FakePathProvider(run_dir)
            def fake_chat_completion(messages, **kwargs):
                prompt = messages[1]["content"]
                if "COMPLETION_TASK" in prompt:
                    return {
                        "content": "- faction_position: 贾府内务中枢\n- story_role: 场面控制者\n- stance_stability: 高\n- identity_anchor: 我先把场面收住\n- world_rule_fit: 高\n- background_imprint: 自幼熟悉权势人情\n- life_experience: 管家理事；周旋内外\n- trauma_scar: 证据不足\n- taboo_topics: 失势；失体面\n- forbidden_behaviors: 白白让人夺权\n- world_belong: 贾府内宅\n- rule_view: 规则是拿来稳场面的\n- plot_restriction: 家族体面与利益绑定\n- soul_goal: 守住手中的秩序与位置\n- hidden_desire: 证据不足\n- core_traits: 利落；强势；机变\n- temperament_type: 明快泼辣\n- values: 责任=8；智慧=8；忠诚=7\n- inner_conflict: 证据不足\n- self_cognition: 知道自己必须撑场\n- private_self: 证据不足\n- thinking_style: 先算局势再动手\n- cognitive_limits: 证据不足\n- decision_rules: 先稳场；后分利害\n- reward_logic: 有用者可拉拢\n- action_style: 先控场后施压\n- fear_triggers: 失势；失控\n- emotion_model: 面上稳，心里算\n- social_mode: 外热内硬\n- carry_style: 分层待人\n- others_impression: 精明强干\n- key_bonds: 贾府；家族秩序\n- appearance_feature: 证据不足\n- habit_action: 证据不足\n- preference_like: 场面稳妥\n- dislike_hate: 失序\n- interest_claim: 掌控局面\n- resource_dependence: 家族权势\n- trade_principle: 不做亏本交换\n- disguise_switch: 证据不足\n- ooc_redline: 不会轻易自乱阵脚\n- strengths: 控场；算账\n- weaknesses: 证据不足\n- arc_type: 证据不足\n- arc_blocker: 证据不足\n- arc_summary: 证据不足\n"
                    }
                if "RELATION_GRAPH" in prompt:
                    return {
                        "content": "# RELATION_GRAPH\n\n## 林黛玉_贾宝玉\n- trust: 8\n- affection: 9\n- power_gap: 0\n- conflict_point: 误会\n- typical_interaction: 试探与安抚\n- hidden_attitude: \n- relation_change: 升温\n- appellation_to_target: 宝玉\n- confidence: 8\n"
                    }
                return {
                    "content": "# PROFILE\n- name: 王熙凤\n- novel_id: hongloumeng\n- core_identity: 管家者\n- speech_style: 利落带锋芒\n- cadence: 快里带稳\n- signature_phrases: 我来收这个场；你且看着\n- typical_lines: 我来收这个场；你且看着\n- sentence_openers: 我来；你且\n- sentence_endings: 便是了；就成\n- worldview: 人情与权势都要算清。\n- belief_anchor: 场面和秩序不能乱。\n- moral_bottom_line: 不轻易让贾府失序。\n- restraint_threshold: 平时压得住，利益与脸面同时受损才会翻脸。\n- stress_response: 压力越大越会先稳住场面，再亮出锋芒。\n"
                }

            fake_parts.llm.chat_completion = Mock(side_effect=fake_chat_completion)
            fake_parts.extractor.extract = Mock()

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                service._run_automatic_pipeline(
                    manifest_path=manifest_path,
                    novel_path=novel_path,
                    locked_characters=["王熙凤"],
                    relation_characters=["林黛玉", "贾宝玉", "王熙凤"],
                    max_sentences=120,
                    max_chars=50000,
                )

            relation_messages = fake_parts.llm.chat_completion.call_args_list[-1].args[0]
            self.assertIn("王熙凤", relation_messages[1]["content"])
            self.assertIn("贾宝玉", relation_messages[1]["content"])
            self.assertIn("林黛玉", relation_messages[1]["content"])

    def test_automatic_pipeline_skips_completed_characters_on_same_source_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉先出场，后来薛宝钗也来了。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "薛宝钗"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "hongloumeng.txt"
            persona_dir = run_dir / "artifacts" / "characters" / "hongloumeng" / "林黛玉"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "PROFILE.generated.md").write_text(
                "# PROFILE\n- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 才女\n",
                encoding="utf-8",
            )
            service.refresh_run(payload["run_id"])
            with patch.object(service, "_start_background_run"):
                restarted = service.restart_run_distill(
                    payload["run_id"],
                    characters=["林黛玉", "薛宝钗"],
                    max_sentences=120,
                    max_chars=50000,
                )

            class _FakePathProvider:
                def __init__(self, base_dir: Path) -> None:
                    self.base_dir = base_dir

                def characters_root(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "characters" / novel_id
                    path.mkdir(parents=True, exist_ok=True)
                    return path

                def relations_file(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "relations" / f"{novel_id}_relations.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return path

            fake_parts = Mock()
            fake_parts.path_provider = _FakePathProvider(run_dir)

            def fake_chat_completion(messages, **kwargs):
                prompt = messages[1]["content"]
                if "RELATION_GRAPH" in prompt:
                    return {
                        "content": "# RELATION_GRAPH\n\n## 林黛玉_薛宝钗\n- trust: 7\n- affection: 6\n- power_gap: 0\n- conflict_point: 心事不明说\n- typical_interaction: 试探与照看\n- hidden_attitude: \n- relation_change: 固化\n- appellation_to_target: 宝钗\n- confidence: 7\n"
                    }
                return {
                    "content": "# PROFILE\n- name: 薛宝钗\n- novel_id: hongloumeng\n- core_identity: 端稳持重之人\n- soul_goal: 把局面稳住\n- speech_style: 温稳克制\n- cadence: 平整收束\n- signature_phrases: 先缓一缓；不妨再看\n- typical_lines: 先缓一缓；不妨再看\n- sentence_openers: 先；不妨\n- sentence_endings: 便好；也罢\n- worldview: 局势先稳，再谈情理。\n- belief_anchor: 分寸不能乱。\n- moral_bottom_line: 不把人逼到失面。\n- restraint_threshold: 平时极稳，被误伤真心时才会显出锋芒。\n- stress_response: 压力越大越会先稳语气，再调次序。\n"
                }

            fake_parts.llm.chat_completion = Mock(side_effect=fake_chat_completion)

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                result = service._run_automatic_pipeline(
                    manifest_path=manifest_path,
                    novel_path=novel_path,
                    locked_characters=restarted["locked_characters"],
                    relation_characters=restarted["redistill"]["relation_characters"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertTrue(result["success"])
            self.assertFalse((run_dir / "payloads" / "distill_林黛玉.json").exists())
            self.assertTrue((run_dir / "payloads" / "distill_薛宝钗.json").exists())
            self.assertEqual(result["summary"]["characters_completed"], 2)
            self.assertCountEqual(
                [item["name"] for item in result["artifact_index"]["characters"]],
                ["林黛玉", "薛宝钗"],
            )

    def test_automatic_pipeline_relation_graph_failure_does_not_fail_chat_ready_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="novel.txt",
                novel_content_base64=base64.b64encode("Alpha meets Beta.".encode("utf-8")).decode("ascii"),
                characters=["Alpha"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "novel.txt"

            class _FakePathProvider:
                def __init__(self, base_dir: Path) -> None:
                    self.base_dir = base_dir

                def characters_root(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "characters" / novel_id
                    path.mkdir(parents=True, exist_ok=True)
                    return path

                def relations_file(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "relations" / f"{novel_id}_relations.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return path

            fake_parts = Mock()
            fake_parts.path_provider = _FakePathProvider(run_dir)

            def fake_chat_completion(messages, **kwargs):
                prompt = messages[1]["content"]
                if "RELATION_GRAPH" in prompt:
                    return {"content": "# RELATION_GRAPH\n\n这里不是可解析的关系图正文。"}
                return {
                    "content": "# PROFILE\n- name: Alpha\n- novel_id: novel\n- core_identity: 核心人物\n- soul_goal: 守住答案\n- speech_style: 先压低语气再落结论\n- cadence: 慢半拍后落点\n- signature_phrases: 先看清；别急着站位\n- typical_lines: 先看清再说；别急着站位\n- sentence_openers: 先；别急\n- sentence_endings: 再说；也罢\n- worldview: 先把局势看清，再决定站位。\n- belief_anchor: 关键时刻不能自乱阵脚。\n- moral_bottom_line: 不把同伴当代价随手抛掉。\n- restraint_threshold: 平时克制，底线被逼穿时才会失控。\n- stress_response: 压力越大越会先收声，再集中判断。\n"
                }

            fake_parts.llm.chat_completion = Mock(side_effect=fake_chat_completion)

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                result = service._run_automatic_pipeline(
                    manifest_path=manifest_path,
                    novel_path=novel_path,
                    locked_characters=["Alpha"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["summary"]["status_text"], "workflow_complete")
            self.assertEqual(result["summary"]["graph_status"], "failed")
            self.assertEqual(result["progress"]["graph_status"], "failed")
            self.assertIn("关系图谱生成失败", result["progress"]["message"])
            self.assertFalse(result["capabilities"]["export_graph"]["success"])
            self.assertTrue((run_dir / "artifacts" / "characters" / "novel" / "Alpha" / "PROFILE.generated.md").exists())

    def test_automatic_pipeline_uses_llm_generated_profiles_and_materializes_persona_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="novel.txt",
                novel_content_base64=base64.b64encode("Alpha meets Beta.".encode("utf-8")).decode("ascii"),
                characters=["Alpha"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "novel.txt"

            class _FakePathProvider:
                def __init__(self, base_dir: Path) -> None:
                    self.base_dir = base_dir

                def characters_root(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "characters" / novel_id
                    path.mkdir(parents=True, exist_ok=True)
                    return path

                def relations_file(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "relations" / f"{novel_id}_relations.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return path

            fake_parts = Mock()
            fake_parts.path_provider = _FakePathProvider(run_dir)
            def fake_chat_completion(messages, **kwargs):
                prompt = messages[1]["content"]
                if "COMPLETION_TASK" in prompt:
                    return {
                        "content": "- faction_position: 自由行动者\n- story_role: 事件推进者\n- stance_stability: 高\n- identity_anchor: 先看清，再站位\n- world_rule_fit: 中低\n- background_imprint: 证据不足\n- life_experience: 与局势周旋\n- trauma_scar: 证据不足\n- taboo_topics: 证据不足\n- forbidden_behaviors: 不拿同伴垫后\n- world_belong: 灰区地带\n- rule_view: 规则先看是否值得守\n- plot_restriction: 证据不足\n- hidden_desire: 想把答案守住\n- core_traits: 冷静；谨慎\n- temperament_type: 收着锋芒\n- values: 智慧=8；责任=7；忠诚=7\n- inner_conflict: 证据不足\n- self_cognition: 知道自己得稳住判断\n- private_self: 证据不足\n- thinking_style: 先分析再表态\n- cognitive_limits: 证据不足\n- decision_rules: 先看清再站位；不为噪声改判断\n- reward_logic: 值得的人就护住\n- action_style: 先压住，再落手\n- fear_triggers: 误判局势\n- emotion_model: 外冷内稳\n- anger_style: 证据不足\n- joy_style: 证据不足\n- grievance_style: 证据不足\n- social_mode: 先观察，再靠近\n- carry_style: 证据不足\n- others_impression: 稳得住\n- key_bonds: 同伴\n- appearance_feature: 证据不足\n- habit_action: 证据不足\n- preference_like: 证据不足\n- dislike_hate: 噪声判断\n- interest_claim: 护住答案\n- resource_dependence: 判断空间\n- trade_principle: 不轻易交换底线\n- disguise_switch: 证据不足\n- ooc_redline: 不会把同伴当代价\n- strengths: 冷静；判断稳\n- weaknesses: 过度防备\n- arc_type: 证据不足\n- arc_blocker: 证据不足\n- arc_summary: 证据不足\n"
                    }
                if "RELATION_GRAPH" in prompt:
                    return {
                        "content": "# RELATION_GRAPH\n\n## Alpha_Beta\n- trust: 7\n- affection: 3\n- power_gap: 0\n- conflict_point: 立场试探\n- typical_interaction: 观察与回应\n- hidden_attitude: \n- relation_change: 固化\n- appellation_to_target: Beta\n- confidence: 7\n"
                    }
                return {
                    "content": "# PROFILE\n- name: Alpha\n- novel_id: novel\n- core_identity: 核心人物\n- soul_goal: 守住答案\n- speech_style: 先压低语气再落结论\n- cadence: 慢半拍后落点\n- signature_phrases: 先看清；别急着站位\n- typical_lines: 先看清再说；别急着站位\n- sentence_openers: 先；别急\n- sentence_endings: 再说；也罢\n- worldview: 先把局势看清，再决定站位。\n- belief_anchor: 关键时刻不能自乱阵脚。\n- moral_bottom_line: 不把同伴当代价随手抛掉。\n- restraint_threshold: 平时克制，底线被逼穿时才会失控。\n- stress_response: 压力越大越会先收声，再集中判断。\n"
                }

            fake_parts.llm.chat_completion = Mock(side_effect=fake_chat_completion)

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                result = service._run_automatic_pipeline(
                    manifest_path=manifest_path,
                    novel_path=novel_path,
                    locked_characters=["Alpha"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertTrue(result["success"])
            persona_dir = run_dir / "artifacts" / "characters" / "novel" / "Alpha"
            self.assertTrue((persona_dir / "PROFILE.generated.md").exists())
            self.assertTrue((persona_dir / "SOUL.generated.md").exists())
            self.assertTrue((run_dir / "payloads" / "distill_Alpha.json").exists())
            self.assertTrue((run_dir / "payloads" / "relation_payload.auto.json").exists())
            self.assertFalse(fake_parts.distiller.distill.called)
            distill_messages = fake_parts.llm.chat_completion.call_args_list[0].args[0]
            self.assertIn("PRIORITY_GUIDANCE", distill_messages[1]["content"])
            self.assertIn("EVIDENCE_STAGES", distill_messages[1]["content"])

    def test_automatic_pipeline_repairs_risky_profile_scalars_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("贾宝玉初入大观园。后来贾宝玉看破繁华。".encode("utf-8")).decode("ascii"),
                characters=["贾宝玉"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "hongloumeng.txt"

            class _FakePathProvider:
                def __init__(self, base_dir: Path) -> None:
                    self.base_dir = base_dir

                def characters_root(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "characters" / novel_id
                    path.mkdir(parents=True, exist_ok=True)
                    return path

                def relations_file(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "relations" / f"{novel_id}_relations.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return path

            fake_parts = Mock()
            fake_parts.path_provider = _FakePathProvider(run_dir)
            def fake_chat_completion(messages, **kwargs):
                prompt = messages[1]["content"]
                if "COMPLETION_TASK" in prompt:
                    return {
                        "content": "- soul_goal: 守住真情与自我\n- hidden_desire: 证据不足\n- core_traits: 重情；敏感\n- temperament_type: 清醒又多情\n- values: 善良=8；自由=7；责任=6\n- inner_conflict: 真情与礼法冲突\n- self_cognition: 知道自己不愿顺着功名路走\n- private_self: 证据不足\n- thinking_style: 先凭真心，再看后果\n- cognitive_limits: 情绪重时易偏执\n- decision_rules: 真情优先；不拿真心换体面\n- reward_logic: 谁真心待我，我便真心回之\n- action_style: 先试探，再靠近\n- fear_triggers: 真心受损\n- emotion_model: 外软内执\n- social_mode: 亲疏分明\n- carry_style: 对亲近者更柔软\n- others_impression: 多情而不愿俗\n- key_bonds: 黛玉；家人\n- strengths: 共情；真诚\n- weaknesses: 情绪牵引重\n- speech_style: 软中带刺\n- typical_lines: 你也不用哄我；这有什么意思\n- cadence: 先轻再沉\n- signature_phrases: 你也不用；我偏\n- sentence_openers: 你也；我偏\n- sentence_endings: 罢了；也就如此\n- arc_type: 觉醒\n- arc_blocker: 礼法与家族压力\n- arc_summary: 从被裹挟到更认清自己所重\n"
                    }
                if "REPAIR_TASK" in prompt:
                    return {
                        "content": "# PROFILE\n- name: 贾宝玉\n- novel_id: hongloumeng\n- core_identity: 贾府公子\n- worldview: 人情比功名更重，真心不能拿来铺垫场面。\n- belief_anchor: 真情不可轻负\n- restraint_threshold: 平时压得住，唯独真心与自尊同时受损时会明显失控。\n- stress_response: 压力越大越会先把情绪压低，再用更冷的语气自护。\n"
                    }
                if "RELATION_GRAPH" in prompt:
                    return {
                        "content": "# RELATION_GRAPH\n\n## 贾宝玉_林黛玉\n- trust: 8\n- affection: 9\n- power_gap: 0\n- conflict_point: 真心太重时易生误会\n- typical_interaction: 试探与安抚\n- hidden_attitude: \n- relation_change: 升温\n- appellation_to_target: 黛玉\n- confidence: 8\n"
                    }
                return {
                    "content": "# PROFILE\n- name: 贾宝玉\n- novel_id: hongloumeng\n- core_identity: 贾府公子\n- worldview: 大家想着，宝玉却等不得了，也不等贾政的命，便说道：“旧诗有云：\n- belief_anchor: 真情不可轻负\n- restraint_threshold: 转过大厅，宝玉心里还自狐疑，只听墙角边一阵呵呵大笑。\n- stress_response: 平时压得住，真心受损时会失控\n"
                }

            fake_parts.llm.chat_completion = Mock(side_effect=fake_chat_completion)

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                result = service._run_automatic_pipeline(
                    manifest_path=manifest_path,
                    novel_path=novel_path,
                    locked_characters=["贾宝玉"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertTrue(result["success"])
            self.assertIn("elapsed_text", result["timing"])
            self.assertTrue(str(result["timing"]["elapsed_text"]).strip())
            self.assertEqual(result["summary"]["elapsed_text"], result["timing"]["elapsed_text"])
            profile_path = run_dir / "host_output" / "hongloumeng" / "贾宝玉" / "PROFILE.generated.md"
            profile_text = profile_path.read_text(encoding="utf-8")
            self.assertIn("人情比功名更重", profile_text)
            self.assertNotIn("旧诗有云", profile_text)
            self.assertEqual(result["quality"]["profile_repairs"]["count"], 1)
            self.assertIn("贾宝玉", result["quality"]["profile_repairs"]["characters"])
            self.assertIn("chunking", result["progress"])
            self.assertIn("distill", result["progress"]["chunking"])
            self.assertEqual(result["progress"]["chunking"]["distill"]["status"], "complete")
            self.assertIn("chunking", result["summary"])
            self.assertTrue(any("本次整理耗时" in str(item.get("message", "")) for item in result.get("events", [])))
            repair_messages = fake_parts.llm.chat_completion.call_args_list[1].args[0]
            self.assertIn("REPAIR_TASK", repair_messages[1]["content"])
            self.assertIn("剧情碎句", repair_messages[1]["content"])

    def test_suggest_dialogue_turn_does_not_mutate_session_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            run_id = run["run_id"]
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run_id,
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                service,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session = service.create_dialogue_session(
                    run_id,
                    mode="observe",
                    participants=["???", "???"],
                    controlled_character="",
                    self_profile={},
                )

            original_history = list(session["history"])

            with patch.object(
                service,
                "_generate_dialogue_suggestion",
                return_value="要不先让他们把刚才那句接下去？",
            ):
                result = service.suggest_dialogue_turn(
                    run_id,
                    session_id=session["session_id"],
                    seed_text="要不先让",
                )

            self.assertEqual(result["suggestion"], "要不先让他们把刚才那句接下去？")
            refreshed_session = service.get_dialogue_session(run_id, session["session_id"])
            self.assertEqual(refreshed_session["history"], original_history)
            self.assertEqual(refreshed_session["pending_turn_summary"], {})
            self.assertEqual(refreshed_session["status"], "ready")

    def test_dialogue_relative_to_run_dir_accepts_case_or_short_path_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run_dir = Path(tmp) / "runs" / "run-demo"
            nested = run_dir / "dialogue" / "dlg-1" / "turns" / "turn-1.payload.json"
            nested.parent.mkdir(parents=True, exist_ok=True)
            nested.write_text("{}", encoding="utf-8")

            relative = service.dialogue._relative_to_run_dir(nested, Path(str(run_dir).upper()))

            self.assertEqual(relative, Path("dialogue") / "dlg-1" / "turns" / "turn-1.payload.json")

    def test_parse_dialogue_suggestion_rejects_meta_explanation(self):
        with self.assertRaisesRegex(ValueError, "explanation instead of a direct sendable line"):
            parse_dialogue_suggestion(
                "我们作为“你”是误入此间的来客，当前场景是对方在生气，我们可以先安抚，再解释。"
            )

    def test_generate_dialogue_suggestion_retries_after_meta_explanation(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            run_id = run["run_id"]
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run_id,
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                service,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session = service.create_dialogue_session(
                    run_id,
                    mode="insert",
                    participants=["???", "???"],
                    controlled_character="",
                    self_profile={"display_name": "你", "scene_identity": "来客"},
                )

            with patch("src.web.service_facades.dialogue.build_runtime_parts") as build_parts:
                fake_parts = Mock()
                fake_parts.llm.chat_completion.side_effect = [
                    {"content": "我们作为“你”是误入此间的来客，当前场景是对方在生气，我们可以先安抚，再解释。", "raw": {}},
                    {"content": "别生气，我刚才那句不是在呛你。", "raw": {}},
                ]
                build_parts.return_value = fake_parts

                result = service.suggest_dialogue_turn(
                    run_id,
                    session_id=session["session_id"],
                    seed_text="我不是那个意思",
                )

            self.assertEqual(result["suggestion"], "别生气，我刚才那句不是在呛你。")
            self.assertEqual(fake_parts.llm.chat_completion.call_count, 2)

    def test_build_suggestion_payload_uses_self_insert_persona_in_insert_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            run_id = run["run_id"]
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run_id,
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n- speech_style: 各有口气\n".encode("utf-8")
                    ).decode("ascii"),
                )
            manifest = service._require_manifest(run_id)
            session = service.dialogue.create_session(
                manifest,
                mode="insert",
                participants=["林黛玉", "贾宝玉"],
                controlled_character="",
                self_profile={
                    "display_name": "阿眠",
                    "scene_identity": "误入园中的来客",
                    "interaction_style": "先软后稳",
                },
            )

            payload = service.dialogue.build_suggestion_payload(
                manifest,
                session_id=session["session_id"],
                seed_text="",
            )

            self.assertEqual(payload["user_persona"]["source"], "self_insert_profile")
            self.assertEqual(payload["user_persona"]["speaker"], "阿眠")
            self.assertEqual(payload["user_persona"]["profile"]["scene_identity"], "误入园中的来客")
            self.assertEqual(payload["user_persona"]["profile"]["interaction_style"], "先软后稳")

    def test_build_suggestion_payload_uses_controlled_character_persona_in_act_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            run_id = run["run_id"]
            service.ingest_character_result(
                run_id,
                character="贾宝玉",
                content_base64=base64.b64encode(
                    "- name: 贾宝玉\n- novel_id: hongloumeng\n- core_identity: 贾府公子\n- speech_style: 软中带刺\n- temperament_type: 多情敏感\n".encode("utf-8")
                ).decode("ascii"),
            )
            service.ingest_character_result(
                run_id,
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                ).decode("ascii"),
            )
            manifest = service._require_manifest(run_id)
            session = service.dialogue.create_session(
                manifest,
                mode="act",
                participants=["贾宝玉", "林黛玉"],
                controlled_character="贾宝玉",
                self_profile={},
            )

            payload = service.dialogue.build_suggestion_payload(
                manifest,
                session_id=session["session_id"],
                seed_text="",
            )

            self.assertEqual(payload["user_persona"]["source"], "controlled_character_persona")
            self.assertEqual(payload["user_persona"]["speaker"], "贾宝玉")
            self.assertEqual(payload["user_persona"]["profile"]["speech_style"], "软中带刺")
            self.assertEqual(payload["user_persona"]["profile"]["temperament_type"], "多情敏感")

    def test_build_suggestion_payload_uses_plot_push_observer_hint_in_observe_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            run_id = run["run_id"]
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run_id,
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )
            manifest = service._require_manifest(run_id)
            session = service.dialogue.create_session(
                manifest,
                mode="observe",
                participants=["林黛玉", "贾宝玉"],
                controlled_character="",
                self_profile={},
            )

            payload = service.dialogue.build_suggestion_payload(
                manifest,
                session_id=session["session_id"],
                seed_text="",
            )

            self.assertEqual(payload["user_persona"]["source"], "observer_hint")
            self.assertEqual(payload["user_persona"]["profile"]["goal"], "push_plot_forward")
            self.assertIn("introduce a new action", payload["user_persona"]["profile"]["preferred_moves"])
            self.assertIn("pushes the plot forward", payload["instructions"]["response_style"])


@unittest.skipIf(TestClient is None or create_app is None, "fastapi test dependencies unavailable")
class WebAppRouteTests(unittest.TestCase):
    def test_delete_run_route_removes_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            client = TestClient(create_app(service))

            response = client.delete(f"/api/web/runs/{run['run_id']}")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "deleted")
            self.assertFalse((Path(tmp) / "runs" / run["run_id"]).exists())

    def test_automatic_pipeline_repairs_risky_relation_scalars_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "hongloumeng.txt"

            class _FakePathProvider:
                def __init__(self, base_dir: Path) -> None:
                    self.base_dir = base_dir

                def characters_root(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "characters" / novel_id
                    path.mkdir(parents=True, exist_ok=True)
                    return path

                def relations_file(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "relations" / f"{novel_id}_relations.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return path

            fake_parts = Mock()
            fake_parts.path_provider = _FakePathProvider(run_dir)
            fake_parts.llm.chat_completion = Mock(
                side_effect=[
                    {
                        "content": "# PROFILE\n- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 贾府外来才女\n- speech_style: 清冷里带一点针锋\n- cadence: 轻声慢落却藏锋\n- signature_phrases: 你也不用哄我；我原知道\n- typical_lines: 你也不用哄我；我原知道你心里有数\n- sentence_openers: 你也；我原\n- sentence_endings: 罢了；也就如此\n- worldview: 世情热闹，真心稀薄。\n- belief_anchor: 真心不可轻负\n- moral_bottom_line: 不肯轻贱真情\n- restraint_threshold: 平日克制，唯独真心受损时会失控。\n- stress_response: 越委屈越先收住情绪，再把语气压得更冷。\n"
                    },
                    {
                        "content": "# RELATION_GRAPH\n\n## 林黛玉_贾宝玉\n- trust: 8\n- affection: 9\n- power_gap: 0\n- conflict_point: 转过大厅，宝玉心里还自狐疑，只听墙角边一阵呵呵大笑。\n- typical_interaction: 大家想着，宝玉却等不得了，也不等贾政的命，便说道：“旧诗有云：\n- hidden_attitude: \n- relation_change: 因为许多事情反复拉扯所以一直变化\n- appellation_to_target: 宝玉\n- confidence: 8\n"
                    },
                    {
                        "content": "# RELATION_GRAPH\n\n## 林黛玉_贾宝玉\n- trust: 8\n- affection: 9\n- power_gap: 0\n- conflict_point: 真心太重时容易因误会互伤。\n- typical_interaction: 常在试探、心软与安抚之间来回。\n- hidden_attitude: \n- relation_change: 反复波动\n- appellation_to_target: 宝玉\n- confidence: 8\n"
                    },
                ]
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                result = service._run_automatic_pipeline(
                    manifest_path=manifest_path,
                    novel_path=novel_path,
                    locked_characters=["林黛玉"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertTrue(result["success"])
            relation_path = run_dir / "artifacts" / "relations" / "hongloumeng_relations.md"
            relation_text = relation_path.read_text(encoding="utf-8")
            self.assertIn("反复波动", relation_text)
            self.assertNotIn("旧诗有云", relation_text)
            self.assertEqual(result["quality"]["relation_repairs"]["count"], 1)
            repair_messages = fake_parts.llm.chat_completion.call_args_list[2].args[0]
            self.assertIn("REPAIR_TASK", repair_messages[1]["content"])
            self.assertIn("关系图谱", repair_messages[1]["content"])

    def test_automatic_pipeline_uses_distinct_distill_stage_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="novel.txt",
                novel_content_base64=base64.b64encode("Alpha meets Beta.".encode("utf-8")).decode("ascii"),
                characters=["Alpha"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "novel.txt"

            class _FakePathProvider:
                def __init__(self, base_dir: Path) -> None:
                    self.base_dir = base_dir

                def characters_root(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "characters" / novel_id
                    path.mkdir(parents=True, exist_ok=True)
                    return path

                def relations_file(self, novel_id: str) -> Path:
                    path = self.base_dir / "artifacts" / "relations" / f"{novel_id}_relations.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return path

            fake_parts = Mock()
            fake_parts.path_provider = _FakePathProvider(run_dir)
            fake_parts.llm.chat_completion = Mock(
                side_effect=[
                    {
                        "content": "# PROFILE\n- name: Alpha\n- novel_id: novel\n- core_identity: 核心人物\n- soul_goal: 守住答案\n- speech_style: 先压低语气再落结论\n- cadence: 慢半拍后落点\n- signature_phrases: 先看清；别急着站位\n- typical_lines: 先看清再说；别急着站位\n- sentence_openers: 先；别急\n- sentence_endings: 再说；也罢\n- worldview: 先把局势看清，再决定站位。\n- belief_anchor: 关键时刻不能自乱阵脚。\n- moral_bottom_line: 不把同伴当代价随手抛掉。\n- restraint_threshold: 平时克制，底线被逼穿时才会失控。\n- stress_response: 压力越大越会先收声，再集中判断。\n"
                    },
                    {
                        "content": "# RELATION_GRAPH\n\n## Alpha_Beta\n- trust: 7\n- affection: 3\n- power_gap: 0\n- conflict_point: 立场试探\n- typical_interaction: 观察与回应\n- hidden_attitude: \n- relation_change: 固化\n- appellation_to_target: Beta\n- confidence: 7\n"
                    },
                ]
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                result = service._run_automatic_pipeline(
                    manifest_path=manifest_path,
                    novel_path=novel_path,
                    locked_characters=["Alpha"],
                    max_sentences=120,
                    max_chars=50000,
                )

            messages = [item["message"] for item in result["events"]]
            self.assertIn("已载入小说文本", messages)
            self.assertIn("已锁定 1 个待蒸馏角色", messages)
            self.assertIn("正在蒸馏 Alpha", messages)
            self.assertIn("正在落盘 Alpha", messages)

    def test_build_distill_llm_messages_include_stage_evidence_and_field_priorities(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            payload = {
                "prompt": "系统提示",
                "references": {
                    "output_schema": "schema",
                    "style_differ": "style",
                    "logic_constraint": "logic",
                    "validation_policy": "validation",
                },
                "request": {
                    "characters": ["贾宝玉"],
                    "excerpt": "总证据",
                    "excerpt_stages": {
                        "start": "贾宝玉初入大观园。",
                        "mid": "贾宝玉为黛玉伤神。",
                        "end": "贾宝玉看破繁华。",
                    },
                    "excerpt_focus": {
                        "requested_characters": ["贾宝玉"],
                        "matched_characters": ["贾宝玉"],
                        "missing_characters": [],
                        "strategy": "character_windows",
                    },
                    "update_mode": "create",
                    "existing_profiles": {},
                },
                "meta": {"novel_id": "hongloumeng"},
            }

            messages = service._build_distill_llm_messages(payload, character="贾宝玉", peer_characters=["林黛玉", "贾宝玉"])
            self.assertEqual(messages[0]["content"], "系统提示")
            self.assertIn("FIELD_GROUPS", messages[1]["content"])
            self.assertIn("### START", messages[1]["content"])
            self.assertIn("DIALOGUE_STYLE", messages[1]["content"])
            self.assertIn("贾宝玉初入大观园", messages[1]["content"])
            self.assertIn("贾宝玉看破繁华", messages[1]["content"])

    def test_profile_repair_targets_flag_generic_style_when_dialogue_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            profile = {
                "speech_style": "冷静克制",
                "cadence": "",
                "signature_phrases": [],
                "typical_lines": [],
                "sentence_openers": [],
                "sentence_endings": [],
                "worldview": "人情比功名更重。",
                "belief_anchor": "真情不可轻负。",
                "moral_bottom_line": "不轻贱真情。",
                "restraint_threshold": "平日克制，真心受损时会失控。",
                "stress_response": "压力越大越先把情绪压低。",
            }
            issues = service._collect_profile_repair_targets(
                profile,
                dialogue_evidence=["贾宝玉道：“你瞧瞧，这个好不好？”"],
            )

            self.assertIn("speech_style", issues)
            self.assertIn("cadence", issues)
            self.assertIn("signature_phrases", issues)

    def test_profile_completion_groups_are_limited_to_four_target_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            groups = service._collect_profile_completion_groups({}, repair_targets={})

            self.assertEqual([name for name, _, _ in groups], ["Inner Core", "Decision Logic", "Emotion And Stress", "Voice"])

    def test_profile_completion_groups_treat_evidence_insufficient_as_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            groups = service._collect_profile_completion_groups(
                {
                    "soul_goal": "证据不足",
                    "speech_style": "证据不足",
                    "speech_habits": {"cadence": "证据不足", "signature_phrases": ["证据不足"]},
                    "emotion_profile": {"anger_style": "证据不足"},
                },
                repair_targets={},
            )

            self.assertIn("Inner Core", [name for name, _, _ in groups])
            self.assertIn("Emotion And Stress", [name for name, _, _ in groups])
            self.assertIn("Voice", [name for name, _, _ in groups])

    def test_profile_repair_prompt_is_single_group_patch_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            payload = {
                "prompt": "系统提示",
                "references": {"output_schema": "schema", "style_differ": "style", "logic_constraint": "logic", "validation_policy": "policy"},
                "request": {"excerpt": "贾宝玉道：“你也不用哄我。”"},
                "meta": {"novel_id": "hongloumeng"},
            }

            messages = service._build_distill_repair_messages(
                payload,
                character="贾宝玉",
                peer_characters=["贾宝玉", "林黛玉"],
                profile={"name": "贾宝玉", "novel_id": "hongloumeng"},
                group_name="Voice",
                fields=("speech_style", "cadence", "signature_phrases"),
                repair_targets={"speech_style": "太泛，缺少对白味道 -> 冷静克制", "cadence": "为空"},
                dialogue_evidence=["贾宝玉道：“你也不用哄我。”"],
            )

            prompt = messages[1]["content"]
            self.assertIn("REPAIR_TASK", prompt)
            self.assertIn("请只修补这一组字段：Voice", prompt)
            self.assertIn("不要自由重写整份 PROFILE", prompt)
            self.assertIn("- speech_style", prompt)
            self.assertIn("- cadence", prompt)
            self.assertNotIn("完整的 PROFILE.generated.md Markdown", prompt)

    def test_refresh_run_discovers_character_cards_and_graph_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。薛宝钗也在场。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            characters_root = run_dir / "artifacts" / "characters" / "hongloumeng"
            dai_dir = characters_root / "林黛玉"
            dai_dir.mkdir(parents=True, exist_ok=True)
            (dai_dir / "PROFILE.generated.md").write_text(
                "\n".join(
                    [
                        "- name: 林黛玉",
                        "- core_identity: 贾府外来才女",
                        "- story_role: 情感核心",
                        "- soul_goal: 守住真心",
                        "- speech_style: 清冷带刺",
                        "- temperament_type: 敏感孤高",
                    ]
                ),
                encoding="utf-8",
            )
            relations_root = run_dir / "artifacts" / "relations"
            relations_root.mkdir(parents=True, exist_ok=True)
            (relations_root / "hongloumeng_relations.html").write_text("<html></html>", encoding="utf-8")
            (relations_root / "hongloumeng_relations.svg").write_text("<svg></svg>", encoding="utf-8")
            (relations_root / "hongloumeng_relations.mermaid.md").write_text("graph LR", encoding="utf-8")
            (relations_root / "hongloumeng_relations.md").write_text("## 林黛玉_贾宝玉", encoding="utf-8")

            refreshed = service.refresh_run(payload["run_id"])
            self.assertEqual(refreshed["summary"]["characters_completed"], 1)
            self.assertEqual(refreshed["summary"]["graph_status"], "complete")
            self.assertEqual(refreshed["artifact_index"]["characters"][0]["name"], "林黛玉")
            self.assertIn("graph_html", refreshed["file_urls"])
            self.assertIn("graph_svg", refreshed["file_urls"])

    def test_ingest_character_result_materializes_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            profile_text = "\n".join(
                [
                    "- name: 林黛玉",
                    "- novel_id: hongloumeng",
                    "- core_identity: 贾府外来才女",
                    "- story_role: 情感核心",
                    "- soul_goal: 守住真心",
                    "- speech_style: 清冷带刺",
                ]
            )
            refreshed = service.ingest_character_result(
                payload["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(profile_text.encode("utf-8")).decode("ascii"),
            )
            self.assertEqual(refreshed["summary"]["characters_completed"], 1)
            self.assertEqual(refreshed["artifact_index"]["characters"][0]["name"], "林黛玉")
            self.assertTrue(
                (Path(tmp) / "runs" / payload["run_id"] / "artifacts" / "characters" / "hongloumeng" / "林黛玉" / "SOUL.generated.md").exists()
            )

    def test_ingest_relation_result_exports_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            relations_text = "\n".join(
                [
                    "- novel_id: hongloumeng",
                    "## 林黛玉_贾宝玉",
                    "- trust: 9",
                    "- affection: 10",
                    "- hostility: 1",
                    "- relation_change: 升温",
                    "- typical_interaction: 常以试探与关心交错",
                ]
            )
            refreshed = service.ingest_relation_result(
                payload["run_id"],
                content_base64=base64.b64encode(relations_text.encode("utf-8")).decode("ascii"),
                filename="hongloumeng_relations.md",
            )
            self.assertEqual(refreshed["summary"]["graph_status"], "complete")
            self.assertIn("graph_html", refreshed["file_urls"])

    def test_persona_review_can_load_and_save_editable_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            profile_text = "\n".join(
                [
                    "- name: 林黛玉",
                    "- novel_id: hongloumeng",
                    "- core_identity: 贾府外来才女",
                    "- identity_anchor: 真心与自尊都很重",
                    "- soul_goal: 守住真心",
                    "- worldview: 世情热闹，真心难得",
                    "- speech_style: 清冷带刺",
                    "- cadence: 先轻后冷",
                    "- signature_phrases: 也罢；我原知道",
                    "- typical_lines: 你也不用哄我；我原知道",
                    "- key_bonds: 贾宝玉；紫鹃",
                ]
            )
            service.ingest_character_result(
                payload["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(profile_text.encode("utf-8")).decode("ascii"),
            )

            review = service.get_persona_review(payload["run_id"], "林黛玉")
            self.assertEqual(review["fields"]["core_identity"], "贾府外来才女")
            self.assertEqual(review["fields"]["identity_anchor"], "真心与自尊都很重")
            self.assertEqual(review["fields"]["signature_phrases"], "也罢；我原知道")

            saved = service.save_persona_review(
                payload["run_id"],
                "林黛玉",
                {
                    "core_identity": "自尊极重的外来才女",
                    "identity_anchor": "我最看重真心，也最不肯委屈自己",
                    "worldview": "人情再热闹，也比不过一颗真心。",
                    "restraint_threshold": "平日克制，唯独真心受损时会失控。",
                    "signature_phrases": "也罢；你又来哄我",
                    "typical_lines": "你也不用哄我；我心里自然明白",
                    "key_bonds": "贾宝玉；紫鹃；贾母",
                    "anger_style": "先收住声气，再把冷意压进话里。",
                },
            )
            self.assertEqual(saved["fields"]["core_identity"], "自尊极重的外来才女")
            self.assertIn("真心", saved["fields"]["worldview"])
            self.assertIn("真心", saved["fields"]["identity_anchor"])
            self.assertEqual(saved["fields"]["signature_phrases"], "也罢；你又来哄我")
            self.assertIn("贾母", saved["fields"]["key_bonds"])
            self.assertIn("冷意", saved["fields"]["anger_style"])

    def test_relation_details_list_exposes_evidence_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            relations_text = "\n".join(
                [
                    "- novel_id: hongloumeng",
                    "## 林黛玉_贾宝玉",
                    "- trust: 9",
                    "- affection: 10",
                    "- hostility: 1",
                    "- relationship_type: 爱情",
                    "- typical_interaction: 试探里带着牵挂",
                    "- conflict_point: 真心太重，反而常被误伤",
                    "- evidence_lines: 初见时互相打量；试探里总藏着在意",
                ]
            )
            service.ingest_relation_result(
                payload["run_id"],
                content_base64=base64.b64encode(relations_text.encode("utf-8")).decode("ascii"),
                filename="hongloumeng_relations.md",
            )

            details = service.list_relation_details(payload["run_id"])
            self.assertEqual(details["relation_count"], 1)
            self.assertEqual(details["items"][0]["relationship_type"], "爱情")
            self.assertTrue(details["items"][0]["evidence_lines"])
            self.assertTrue(
                (Path(tmp) / "runs" / payload["run_id"] / "artifacts" / "relations" / "hongloumeng_relations.html").exists()
            )

    def test_dialogue_session_prepare_and_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            service.ingest_character_result(
                payload["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 才女\n- soul_goal: 守住真心\n".encode("utf-8")
                ).decode("ascii"),
            )
            service.ingest_character_result(
                payload["run_id"],
                character="贾宝玉",
                content_base64=base64.b64encode(
                    "- name: 贾宝玉\n- novel_id: hongloumeng\n- core_identity: 公子\n- soul_goal: 护住眼前人\n".encode("utf-8")
                ).decode("ascii"),
            )

            with patch.object(
                service,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session = service.create_dialogue_session(
                    payload["run_id"],
                    mode="insert",
                    participants=["???", "???"],
                    self_profile={"display_name": "Self", "scene_identity": "Guest"},
                )
            prepared = service.prepare_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                message="我刚进园子，想先和你们打个招呼。",
            )
            self.assertEqual(prepared["status"], "waiting_for_host_reply")
            self.assertIn("pending_turn_payload", prepared["file_urls"])
            self.assertEqual(prepared["session_card"]["self_insert"]["display_name"], "Self")
            self.assertEqual(prepared["pending_turn_summary"]["speaker"], "Self")

            completed = service.ingest_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                responses=[{"speaker": "林黛玉", "message": "你既来了，先坐下说话。"}],
            )
            self.assertEqual(completed["status"], "ready")
            self.assertEqual(len(completed["transcript"]), 3)
            self.assertEqual(completed["transcript"][0]["role"], "scene")
            self.assertEqual(completed["transcript"][1]["role"], "user")
            self.assertEqual(completed["transcript"][2]["role"], "character")

@unittest.skipUnless(TestClient and create_app, "fastapi test client is unavailable")
class WebAppRouteTests(unittest.TestCase):
    def test_persona_review_route_accepts_extended_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 贾府外来才女\n".encode("utf-8")
                ).decode("ascii"),
            )
            client = TestClient(create_app(service))

            response = client.put(
                f"/api/web/runs/{run['run_id']}/personas/林黛玉",
                json={
                    "identity_anchor": "我最看重真心，也最不肯委屈自己",
                    "signature_phrases": "也罢；你又来哄我",
                    "key_bonds": "贾宝玉；紫鹃；贾母",
                    "anger_style": "先收住声气，再把冷意压进话里。",
                },
            )

            self.assertEqual(response.status_code, 200)
            fields = response.json()["fields"]
            self.assertIn("真心", fields["identity_anchor"])
            self.assertIn("贾母", fields["key_bonds"])
            self.assertIn("冷意", fields["anger_style"])

    def test_model_settings_route_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(WebRunService(tmp))
            client = TestClient(app)

            initial = client.get("/api/web/settings/model")
            self.assertEqual(initial.status_code, 200)
            self.assertFalse(initial.json()["configured"])

            saved = client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                    "max_tokens": 1200,
                },
            )
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.json()["configured"])
            self.assertEqual(saved.json()["max_tokens"], 1200)

            resaved = client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "",
                    "max_tokens": 900,
                },
            )
            self.assertEqual(resaved.status_code, 200)
            self.assertTrue(resaved.json()["configured"])
            self.assertEqual(resaved.json()["max_tokens"], 900)

    def test_recent_sessions_route_lists_created_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(WebRunService(tmp))
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                },
            )
            run = create_response.json()
            for name in ("林黛玉", "贾宝玉"):
                client.post(
                    f"/api/web/runs/{run['run_id']}/ingest/character",
                    json={
                        "character": name,
                        "content_base64": base64.b64encode(
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                        ).decode("ascii"),
                    },
                )
            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions",
                    json={
                        "mode": "observe",
                        "participants": ["???", "???"],
                        "controlled_character": "",
                        "self_profile": {},
                    },
                )

            sessions_response = client.get("/api/web/sessions")
            self.assertEqual(sessions_response.status_code, 200)
            self.assertEqual(len(sessions_response.json()["items"]), 1)

    def test_delete_dialogue_session_route_removes_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(WebRunService(tmp))
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("镜中两人相见。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                },
            )
            run = create_response.json()
            for name in ("林黛玉", "贾宝玉"):
                client.post(
                    f"/api/web/runs/{run['run_id']}/ingest/character",
                    json={
                        "character": name,
                        "content_base64": base64.b64encode(
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                        ).decode("ascii"),
                    },
                )
            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions",
                    json={
                        "mode": "observe",
                        "participants": ["???", "???"],
                        "controlled_character": "",
                        "self_profile": {},
                    },
                )
            session = session_response.json()

            delete_response = client.delete(
                f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}"
            )
            self.assertEqual(delete_response.status_code, 200)
            self.assertEqual(delete_response.json()["status"], "deleted")

            sessions_response = client.get("/api/web/sessions")
            self.assertEqual(sessions_response.status_code, 200)
            self.assertEqual(len(sessions_response.json()["items"]), 0)

    def test_create_run_and_fetch_manifest_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(WebRunService(tmp))
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )

            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode(
                        "林黛玉初见贾宝玉。贾宝玉也在看她。".encode("utf-8")
                    ).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                    "max_sentences": 120,
                    "max_chars": 50000,
                },
            )
            self.assertEqual(create_response.status_code, 200)
            payload = create_response.json()

            list_response = client.get("/api/web/runs")
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(len(list_response.json()["items"]), 1)

            manifest_response = client.get(payload["file_urls"]["manifest"])
            self.assertEqual(manifest_response.status_code, 200)
            self.assertIn('"run_id"', manifest_response.text)

    def test_redistill_route_restarts_existing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            app = create_app(service)
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("镜中两人相见。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉"],
                },
            )
            payload = create_response.json()

            with patch.object(service, "_start_background_run") as start_background_run:
                response = client.post(
                    f"/api/web/runs/{payload['run_id']}/redistill",
                    json={
                        "characters": ["林黛玉", "王熙凤"],
                        "max_sentences": 120,
                        "max_chars": 50000,
                    },
                )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["locked_characters"], ["林黛玉", "王熙凤"])
            self.assertEqual(data["status"], "running")
            self.assertIn("redistill", data)
            start_background_run.assert_called_once()

    def test_redistill_route_accepts_new_source_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            app = create_app(service)
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng-1.txt",
                    "novel_content_base64": base64.b64encode("第一章里林黛玉出场。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉"],
                },
            )
            payload = create_response.json()

            with patch.object(service, "_start_background_run") as start_background_run:
                response = client.post(
                    f"/api/web/runs/{payload['run_id']}/redistill",
                    json={
                        "characters": ["林黛玉", "薛宝钗"],
                        "novel_name": "hongloumeng-2.txt",
                        "novel_content_base64": base64.b64encode("第二章里宝钗登场。".encode("utf-8")).decode("ascii"),
                        "max_sentences": 120,
                        "max_chars": 50000,
                    },
                )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["redistill"]["used_new_source"])
            self.assertIn("updates", data["novel_path"])
            self.assertEqual(data["novel_sources"][-1]["kind"], "incremental_update")
            self.assertGreater(data["novel_sources"][-1]["byte_size"], 0)
            self.assertGreater(data["novel_sources"][-1]["char_count"], 0)
            start_background_run.assert_called_once()

    def test_stop_run_route_marks_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            app = create_app(service)
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            with patch.object(service, "_start_background_run"):
                create_response = client.post(
                    "/api/web/runs",
                    json={
                        "novel_name": "hongloumeng.txt",
                        "novel_content_base64": base64.b64encode("镜中两人相见。".encode("utf-8")).decode("ascii"),
                        "characters": ["林黛玉"],
                        "auto_run": True,
                    },
                )
            payload = create_response.json()

            stop_response = client.post(f"/api/web/runs/{payload['run_id']}/stop")

            self.assertEqual(stop_response.status_code, 200)
            data = stop_response.json()
            self.assertTrue(data["control"]["stop_requested"])
            self.assertEqual(data["summary"]["status_text"], "stop_requested")

    def test_refresh_route_updates_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(WebRunService(tmp))
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("林黛玉见贾宝玉。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉"],
                },
            )
            payload = create_response.json()
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            profile_dir = run_dir / "artifacts" / "characters" / "hongloumeng" / "林黛玉"
            profile_dir.mkdir(parents=True, exist_ok=True)
            (profile_dir / "PROFILE.generated.md").write_text("- name: 林黛玉\n- core_identity: 才女\n", encoding="utf-8")

            refresh_response = client.post(f"/api/web/runs/{payload['run_id']}/refresh")
            self.assertEqual(refresh_response.status_code, 200)
            refreshed = refresh_response.json()
            self.assertEqual(refreshed["summary"]["characters_completed"], 1)

    def test_ingest_routes_update_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(WebRunService(tmp))
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                },
            )
            run = create_response.json()

            profile_text = "- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 才女\n"
            character_response = client.post(
                f"/api/web/runs/{run['run_id']}/ingest/character",
                json={
                    "character": "林黛玉",
                    "content_base64": base64.b64encode(profile_text.encode("utf-8")).decode("ascii"),
                    "filename": "PROFILE.generated.md",
                },
            )
            self.assertEqual(character_response.status_code, 200)
            self.assertEqual(character_response.json()["summary"]["characters_completed"], 1)
            self.assertIn("character_林黛玉", character_response.json()["file_urls"])

            relations_text = "\n".join(
                [
                    "- novel_id: hongloumeng",
                    "## 林黛玉_贾宝玉",
                    "- trust: 8",
                    "- affection: 9",
                    "- hostility: 1",
                ]
            )
            relation_response = client.post(
                f"/api/web/runs/{run['run_id']}/ingest/relation",
                json={
                    "content_base64": base64.b64encode(relations_text.encode("utf-8")).decode("ascii"),
                    "filename": "hongloumeng_relations.md",
                },
            )
            self.assertEqual(relation_response.status_code, 200)
            self.assertEqual(relation_response.json()["summary"]["graph_status"], "complete")

    def test_dialogue_routes_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(WebRunService(tmp))
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                },
            )
            run = create_response.json()
            for name in ("林黛玉", "贾宝玉"):
                client.post(
                    f"/api/web/runs/{run['run_id']}/ingest/character",
                    json={
                        "character": name,
                        "content_base64": base64.b64encode(
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                        ).decode("ascii"),
                    },
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions",
                    json={
                        "mode": "observe",
                        "participants": ["???", "???"],
                        "controlled_character": "",
                        "self_profile": {},
                    },
                )
            self.assertEqual(session_response.status_code, 200)
            session = session_response.json()

            prepare_response = client.post(
                f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}/prepare",
                json={"message": "两个人先聊起来吧。"},
            )
            self.assertEqual(prepare_response.status_code, 200)
            self.assertEqual(prepare_response.json()["status"], "waiting_for_host_reply")
            self.assertEqual(prepare_response.json()["pending_turn_summary"]["speaker"], "User")

            ingest_response = client.post(
                f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}/ingest",
                json={"responses": [{"speaker": "林黛玉", "message": "今日风倒清。"}]},
            )
            self.assertEqual(ingest_response.status_code, 200)
            self.assertEqual(ingest_response.json()["status"], "ready")
            self.assertEqual(ingest_response.json()["transcript"][0]["role"], "director")

    def test_dialogue_reply_route_generates_and_ingests(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            app = create_app(service)
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                },
            )
            run = create_response.json()
            for name in ("林黛玉", "贾宝玉"):
                client.post(
                    f"/api/web/runs/{run['run_id']}/ingest/character",
                    json={
                        "character": name,
                        "content_base64": base64.b64encode(
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                        ).decode("ascii"),
                    },
                )
            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions",
                    json={
                        "mode": "observe",
                        "participants": ["???", "???"],
                        "controlled_character": "",
                        "self_profile": {},
                    },
                )
            session = session_response.json()

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "林黛玉", "message": "你既来了，先坐下说话。"}],
            ):
                reply_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}/reply",
                    json={"message": "你们先聊几句。"},
                )

            self.assertEqual(reply_response.status_code, 200)
            payload = reply_response.json()
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["transcript"][-1]["speaker"], "林黛玉")

    def test_dialogue_suggest_route_returns_suggestion_without_mutating_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            app = create_app(service)
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                },
            )
            run = create_response.json()
            for name in ("林黛玉", "贾宝玉"):
                client.post(
                    f"/api/web/runs/{run['run_id']}/ingest/character",
                    json={
                        "character": name,
                        "content_base64": base64.b64encode(
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                        ).decode("ascii"),
                    },
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions",
                    json={
                        "mode": "observe",
                        "participants": ["???", "???"],
                        "controlled_character": "",
                        "self_profile": {},
                    },
                )
            session = session_response.json()
            initial_history = list(session["history"])

            with patch.object(
                WebRunService,
                "_generate_dialogue_suggestion",
                return_value="要不先让他们把刚才那句接下去？",
            ):
                suggest_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}/suggest",
                    json={"seed_text": "要不先让"},
                )

            self.assertEqual(suggest_response.status_code, 200)
            self.assertEqual(suggest_response.json()["suggestion"], "要不先让他们把刚才那句接下去？")

            refreshed_session = client.get(
                f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}"
            ).json()
            self.assertEqual(refreshed_session["history"], initial_history)
            self.assertEqual(refreshed_session["pending_turn_summary"], {})
            self.assertEqual(refreshed_session["status"], "ready")


    def test_dialogue_reply_route_returns_friendly_model_subscription_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            app = create_app(service)
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("镜中两人相见。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                },
            )
            run = create_response.json()
            for name in ("林黛玉", "贾宝玉"):
                client.post(
                    f"/api/web/runs/{run['run_id']}/ingest/character",
                    json={
                        "character": name,
                        "content_base64": base64.b64encode(
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                        ).decode("ascii"),
                    },
                )
            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions",
                    json={
                        "mode": "observe",
                        "participants": ["???", "???"],
                        "controlled_character": "",
                        "self_profile": {},
                    },
                )
            session = session_response.json()

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                side_effect=LLMRequestError(
                    'LLM 请求失败: 400 Bad Request | {"error":{"code":"InvalidSubscription","message":"CodingPlan expired"}}'
                ),
            ):
                reply_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}/reply",
                    json={"message": "你们先聊几句。"},
                )

            self.assertEqual(reply_response.status_code, 400)
            self.assertIn("对话生成订阅权限", reply_response.json()["detail"])

    def test_dialogue_reply_retries_once_after_empty_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            app = create_app(service)
            client = TestClient(app)
            client.put(
                "/api/web/settings/model",
                json={
                    "provider": "openai-compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-test",
                },
            )
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng.txt",
                    "novel_content_base64": base64.b64encode("镜中两人相见。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉", "贾宝玉"],
                },
            )
            run = create_response.json()
            for name in ("林黛玉", "贾宝玉"):
                client.post(
                    f"/api/web/runs/{run['run_id']}/ingest/character",
                    json={
                        "character": name,
                        "content_base64": base64.b64encode(
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                        ).decode("ascii"),
                    },
                )
            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "????", "message": "????????????"}],
            ):
                session_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions",
                    json={
                        "mode": "observe",
                        "participants": ["???", "???"],
                        "controlled_character": "",
                        "self_profile": {},
                    },
                )
            session = session_response.json()

            with patch.object(
                WebRunService,
                "_build_dialogue_llm_messages",
                side_effect=lambda payload, retry_on_empty=False: [{"role": "user", "content": "retry" if retry_on_empty else "first"}],
            ), patch("src.web.workflow.build_runtime_parts") as build_parts:
                fake_parts = Mock()
                fake_parts.llm.chat_completion.side_effect = [
                    {"content": "", "raw": {}},
                    {"content": '[{"speaker":"林黛玉","message":"你既开口了，我便回你一句。"}]', "raw": {}},
                ]
                build_parts.return_value = fake_parts
                reply_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}/reply",
                    json={"message": "你好"},
                )

            self.assertEqual(reply_response.status_code, 200)
            payload = reply_response.json()
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["transcript"][-1]["speaker"], "林黛玉")


if __name__ == "__main__":
    unittest.main()
