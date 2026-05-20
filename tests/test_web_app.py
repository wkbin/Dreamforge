import base64
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from src.core.exceptions import LLMRequestError
from src.web.chat.helpers import compact_dialogue_suggestion_payload, parse_dialogue_suggestion
from src.web.pipeline import process_relation_graph, update_manifest_chunk_progress
from src.web.review.persona_completion import collect_persona_web_references
from src.web.workflow import WebRunService

try:
    from fastapi.testclient import TestClient
    from src.web.app import create_app
except Exception:  # pragma: no cover - optional test dependency guard
    TestClient = None
    create_app = None


class WebRunServiceTests(unittest.TestCase):
    def test_scene_card_recommendation_prefers_insert_friendly_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            guest_card = service.save_scene_card(
                fields={
                    "title": "新客入席",
                    "time_hint": "薄暮",
                    "location": "花厅",
                    "atmosphere": "表面热络，暗地试探",
                    "opening_situation": "一位新到的外客被引入席间，众人的目光都轻轻落了过去。",
                    "public_goal": "先把这位来客安顿进今晚的场面。",
                    "hidden_tension": "谁都想先看清这位外客站在哪边。",
                    "scene_drive": "让来客与席上人物迅速形成试探。",
                    "expected_rhythm": "慢热试探",
                    "forbidden_topics": "旧案",
                }
            )
            service.save_scene_card(
                fields={
                    "title": "二人檐下",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "安静发紧",
                    "opening_situation": "两个人被雨声隔在檐下，谁都不肯先明说。",
                    "public_goal": "先把真正来意试出来。",
                    "hidden_tension": "旧事随时会被挑破。",
                    "scene_drive": "把试探慢慢推成摊牌。",
                    "expected_rhythm": "慢热",
                    "forbidden_topics": "前尘",
                }
            )

            payload = service.recommend_scene_cards(mode="insert", participants=["林黛玉", "贾宝玉", "薛宝钗"])

            self.assertEqual(payload["recommended_card_id"], guest_card["card_id"])
            self.assertTrue(payload["items"][0]["recommendation"]["reasons"])

    def test_dialogue_scene_card_recommendation_prefers_next_scene_not_current_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            current_scene = service.save_scene_card(
                fields={
                    "title": "雨夜回廊",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "雨声压得人心发紧",
                    "opening_situation": "两个人被雨隔在檐下，话还没真正说开。",
                    "public_goal": "先把来意试出来。",
                    "hidden_tension": "旧事随时会被翻出来。",
                    "scene_drive": "让试探一点点逼近摊牌。",
                    "expected_rhythm": "慢热",
                    "forbidden_topics": "前尘",
                }
            )
            next_scene = service.save_scene_card(
                fields={
                    "title": "转入花厅",
                    "time_hint": "夜深",
                    "location": "花厅",
                    "atmosphere": "人多却更安静，像谁都在等先开口",
                    "opening_situation": "雨势更大，众人不得不转入花厅继续对坐。",
                    "public_goal": "把表面客套维持住。",
                    "hidden_tension": "真正要问的话终于躲不过去了。",
                    "scene_drive": "让局面从试探推向摊牌。",
                    "expected_rhythm": "三句一推进",
                    "forbidden_topics": "旧账",
                }
            )
            service.save_scene_card(
                fields={
                    "title": "席后逼问",
                    "time_hint": "更深",
                    "location": "偏厅",
                    "atmosphere": "客套彻底收住，只剩正面拉扯",
                    "opening_situation": "众人散去后，只余两人留在偏厅把话挑明。",
                    "public_goal": "把真正立场逼出来。",
                    "hidden_tension": "之前压住的话终于要摊开。",
                    "scene_drive": "把局面从试探推进到逼问与摊牌。",
                    "expected_rhythm": "越聊越紧",
                    "forbidden_topics": "闲话",
                }
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "雨势更大，众人不得不转入花厅。"}],
            ):
                session = service.create_dialogue_session(
                    run["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                    scene_card_id=current_scene["card_id"],
                )
                service.reply_dialogue_turn(
                    run["run_id"],
                    session_id=session["session_id"],
                    message="雨势更大，众人不得不转入花厅。",
                    message_kind="narration",
                )

            payload = service.recommend_dialogue_scene_card(run["run_id"], session_id=session["session_id"])

            self.assertEqual(payload["current_scene_card_id"], current_scene["card_id"])
            self.assertEqual(payload["recommended_card_id"], next_scene["card_id"])
            self.assertNotEqual(payload["recommended_card_id"], current_scene["card_id"])
            self.assertTrue(payload["items"][0]["recommendation"]["reasons"])
            self.assertTrue(str(payload.get("recommended_transition_message", "")).strip())
            self.assertTrue(str(payload.get("recommended_auto_continue_message", "")).strip())
            self.assertTrue(payload["chain_suggestions"])
            self.assertGreaterEqual(len(payload["chain_suggestions"][0]["scenes"]), 2)
            self.assertTrue(str(payload["chain_suggestions"][0]["reason"]).strip())

    def test_dialogue_scene_card_recommendation_stays_in_same_location_when_beat_is_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            current_scene = service.save_scene_card(
                fields={
                    "title": "雨夜回廊",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "雨声压着话头",
                    "opening_situation": "两个人还站在檐下，谁都没把话说透。",
                    "public_goal": "先试出彼此来意。",
                    "hidden_tension": "有些旧话一碰就要翻出来。",
                    "scene_drive": "让试探再压低一层。",
                    "expected_rhythm": "慢热",
                    "forbidden_topics": "旧账",
                }
            )
            same_location = service.save_scene_card(
                fields={
                    "title": "回廊压低声气",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "静得能听见雨线擦过栏杆",
                    "opening_situation": "两个人谁也没走，反而把声音压得更低。",
                    "public_goal": "顺着刚才的话再往里探一步。",
                    "hidden_tension": "谁先心软谁就先露了底。",
                    "scene_drive": "让场面继续收紧，不急着换幕。",
                    "expected_rhythm": "缓慢加压",
                    "forbidden_topics": "外人",
                }
            )
            service.save_scene_card(
                fields={
                    "title": "转入花厅",
                    "time_hint": "夜深",
                    "location": "花厅",
                    "atmosphere": "人多却更安静",
                    "opening_situation": "雨势更大，众人被催着转到花厅落座。",
                    "public_goal": "先把场面稳住。",
                    "hidden_tension": "真正要问的话还压在心口。",
                    "scene_drive": "从试探转向更公开的拉扯。",
                    "expected_rhythm": "三句一推进",
                    "forbidden_topics": "旧案",
                }
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "回廊里只剩雨声和一句没说完的话。"}],
            ):
                session = service.create_dialogue_session(
                    run["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                    scene_card_id=current_scene["card_id"],
                )

            service.dialogue.update_scene_progress_state(
                run["run_id"],
                session["session_id"],
                {
                    "location": "回廊",
                    "time_hint": "深夜",
                    "atmosphere_summary": "雨声压着话头，谁都没有退开",
                    "beat_maturity": 22,
                    "should_offer_scene_shift": False,
                    "scene_shift_reason": "",
                    "world_tension_summary": "两个人都还在试探，还没到换场的时候",
                },
            )

            payload = service.recommend_dialogue_scene_card(run["run_id"], session_id=session["session_id"])

            self.assertEqual(payload["recommended_card_id"], same_location["card_id"])
            self.assertIn("生成一个自然开场", str(payload.get("recommended_auto_continue_message", "")).strip())

    def test_dialogue_scene_card_recommendation_uses_runtime_shift_reason_in_transition_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            current_scene = service.save_scene_card(
                fields={
                    "title": "雨夜回廊",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "雨声压得人心发紧",
                    "opening_situation": "两个人被雨隔在檐下，话已经逼到边上。",
                    "public_goal": "先稳住表面客气。",
                    "hidden_tension": "真正的问题已经快藏不住了。",
                    "scene_drive": "让试探逼近摊牌。",
                    "expected_rhythm": "慢热",
                    "forbidden_topics": "前尘",
                }
            )
            next_scene = service.save_scene_card(
                fields={
                    "title": "灯下入席",
                    "time_hint": "夜深",
                    "location": "花厅",
                    "atmosphere": "灯火亮着，谁都更难回避彼此",
                    "opening_situation": "雨脚催着众人换到花厅，落座后谁也没先碰茶。",
                    "public_goal": "把表面话撑到头。",
                    "hidden_tension": "下一句就可能把真正心思挑明。",
                    "scene_drive": "让局面顺势从回避转向正面相对。",
                    "expected_rhythm": "越聊越紧",
                    "forbidden_topics": "闲话",
                }
            )
            service.save_scene_card(
                fields={
                    "title": "回廊再压一拍",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "雨线更急，但还是没人挪步",
                    "opening_situation": "两个人还站在原地，只把语气压得更轻。",
                    "public_goal": "把上一句试探再咬紧一点。",
                    "hidden_tension": "谁先退让谁就输了这口气。",
                    "scene_drive": "继续在原地消磨彼此的耐心。",
                    "expected_rhythm": "慢压",
                    "forbidden_topics": "旁人",
                }
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "雨已经大到不得不换个地方把话说完。"}],
            ):
                session = service.create_dialogue_session(
                    run["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                    scene_card_id=current_scene["card_id"],
                )

            service.dialogue.update_scene_progress_state(
                run["run_id"],
                session["session_id"],
                {
                    "location": "回廊",
                    "time_hint": "深夜",
                    "atmosphere_summary": "雨势更重，回避已经压不住了",
                    "beat_maturity": 82,
                    "should_offer_scene_shift": True,
                    "scene_shift_reason": "雨势压得两人都没法再站在回廊里装作无事",
                    "world_tension_summary": "再拖一两句，局面就会逼到必须正面开口",
                },
            )

            payload = service.recommend_dialogue_scene_card(run["run_id"], session_id=session["session_id"])

            self.assertEqual(payload["recommended_card_id"], next_scene["card_id"])
            self.assertIn("雨势压得两人都没法再站在回廊里装作无事", payload["recommended_transition_message"])
            self.assertTrue(str(payload.get("recommended_auto_continue_message", "")).strip())

    def test_dialogue_scene_history_tracks_initial_scene_and_switches(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            first_scene = service.save_scene_card(
                fields={
                    "title": "回廊夜谈",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "安静发紧",
                    "opening_situation": "两人隔着雨声说话。",
                    "public_goal": "先探来意。",
                    "hidden_tension": "旧事随时会被挑开。",
                    "scene_drive": "把试探慢慢逼紧。",
                    "expected_rhythm": "慢热",
                    "forbidden_topics": "前尘",
                }
            )
            second_scene = service.save_scene_card(
                fields={
                    "title": "转入花厅",
                    "time_hint": "夜深",
                    "location": "花厅",
                    "atmosphere": "表面客套，暗地收紧",
                    "opening_situation": "雨势更大，众人不得不转入花厅。",
                    "public_goal": "先把场面稳住。",
                    "hidden_tension": "真正要问的话终于躲不过去。",
                    "scene_drive": "从试探推向摊牌。",
                    "expected_rhythm": "三句一推进",
                    "forbidden_topics": "旧账",
                }
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session = service.create_dialogue_session(
                    run["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                    scene_card_id=first_scene["card_id"],
                )

            switched = service.switch_dialogue_scene_card(
                run["run_id"],
                session_id=session["session_id"],
                scene_card_id=second_scene["card_id"],
                transition_message="雨势更大，众人转入花厅。",
            )

            history = switched["scene_history"]
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["title"], "回廊夜谈")
            self.assertEqual(history[1]["title"], "转入花厅")
            self.assertEqual(history[1]["transition_message"], "雨势更大，众人转入花厅。")
            self.assertEqual(history[1]["is_current"], "true")

    def test_switch_dialogue_scene_card_can_auto_continue_new_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            first_scene = service.save_scene_card(
                fields={
                    "title": "回廊夜谈",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "安静发紧",
                    "opening_situation": "两人隔着雨声说话。",
                    "public_goal": "先探来意。",
                    "hidden_tension": "旧事随时会被挑开。",
                    "scene_drive": "把试探慢慢逼紧。",
                    "expected_rhythm": "慢热",
                    "forbidden_topics": "前尘",
                }
            )
            second_scene = service.save_scene_card(
                fields={
                    "title": "转入花厅",
                    "time_hint": "夜深",
                    "location": "花厅",
                    "atmosphere": "表面客套，暗地收紧",
                    "opening_situation": "雨势更大，众人不得不转入花厅。",
                    "public_goal": "先把场面稳住。",
                    "hidden_tension": "真正要问的话终于躲不过去。",
                    "scene_drive": "从试探推向摊牌。",
                    "expected_rhythm": "三句一推进",
                    "forbidden_topics": "旧账",
                }
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                side_effect=[
                    [{"speaker": "场景提示", "message": "开场。"}],
                    [{"speaker": "林黛玉", "message": "（她抬眼看了看门外雨势）进了花厅，也未见得就好说。"}],
                ],
            ):
                session = service.create_dialogue_session(
                    run["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                    scene_card_id=first_scene["card_id"],
                )
                switched = service.switch_dialogue_scene_card(
                    run["run_id"],
                    session_id=session["session_id"],
                    scene_card_id=second_scene["card_id"],
                    transition_message="雨势更大，众人转入花厅。",
                    auto_continue=True,
                )

            transcript = list(switched.get("transcript", []) or [])
            self.assertEqual(switched["session_card"]["scene_card"]["title"], "转入花厅")
            self.assertTrue(any("众人转入花厅" in str(item.get("message", "")) for item in transcript))
            self.assertTrue(any(str(item.get("speaker", "")) == "林黛玉" for item in transcript))
            self.assertEqual(switched.get("status"), "ready")
            self.assertFalse(bool(switched.get("pending_turn")))

    def test_branch_dialogue_session_from_scene_creates_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            first_scene = service.save_scene_card(
                fields={
                    "title": "回廊夜谈",
                    "time_hint": "深夜",
                    "location": "回廊",
                    "atmosphere": "安静发紧",
                    "opening_situation": "两人隔着雨声说话。",
                    "public_goal": "先探来意。",
                    "hidden_tension": "旧事随时会被挑开。",
                    "scene_drive": "把试探慢慢逼紧。",
                    "expected_rhythm": "慢热",
                    "forbidden_topics": "前尘",
                }
            )
            second_scene = service.save_scene_card(
                fields={
                    "title": "花厅再会",
                    "time_hint": "夜深",
                    "location": "花厅",
                    "atmosphere": "表面松，暗地紧",
                    "opening_situation": "众人转入花厅，谁都还没真正把话挑明。",
                    "public_goal": "把场面先稳住。",
                    "hidden_tension": "真正要问的话已经逼到嘴边。",
                    "scene_drive": "把客套推成摊牌。",
                    "expected_rhythm": "三句一推进",
                    "forbidden_topics": "旧账",
                }
            )
            run = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session = service.create_dialogue_session(
                    run["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                    scene_card_id=first_scene["card_id"],
                )

            service.switch_dialogue_scene_card(
                run["run_id"],
                session_id=session["session_id"],
                scene_card_id=second_scene["card_id"],
                transition_message="雨势更大，众人转入花厅。",
            )
            branch = service.branch_dialogue_session_from_scene(
                run["run_id"],
                session_id=session["session_id"],
                scene_index=1,
            )

            self.assertNotEqual(branch["session_id"], session["session_id"])
            self.assertEqual(branch["session_card"]["scene_card"]["title"], "花厅再会")
            self.assertEqual(branch["session_card"]["scene_card"]["location"], "花厅")
            self.assertEqual(branch["scene_history"][0]["title"], "花厅再会")
            self.assertEqual(branch["branch_origin"]["scene_title"], "花厅再会")
            self.assertTrue(str(branch["session_memory_summary"]["recap"]).startswith("承接旧线："))

    def test_scene_card_crud_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)

            created = service.save_scene_card(
                fields={
                    "title": "雨夜探院",
                    "time_hint": "二更将尽",
                    "location": "偏院回廊",
                    "atmosphere": "雨声压低了人声，气氛发紧",
                    "opening_situation": "众人刚散，只有两个人被一场突雨逼回檐下。",
                    "public_goal": "先把这场偶遇说圆。",
                    "hidden_tension": "谁都知道这不是单纯偶遇，却都先不点破。",
                    "scene_drive": "让试探一步步变成摊牌。",
                    "expected_rhythm": "慢热试探，越聊越绷紧",
                    "forbidden_topics": "旧事；家中真正站队",
                }
            )

            self.assertTrue(created["card_id"])
            self.assertEqual(created["fields"]["title"], "雨夜探院")

            listed = service.list_scene_cards()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["card_id"], created["card_id"])

            fetched = service.get_scene_card(created["card_id"])
            self.assertEqual(fetched["fields"]["scene_drive"], "让试探一步步变成摊牌。")

            deleted = service.delete_scene_card(created["card_id"])
            self.assertEqual(deleted["status"], "deleted")
            self.assertEqual(service.list_scene_cards(), [])

    def test_self_card_crud_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)

            created = service.save_self_card(
                fields={
                    "display_name": "阿眠",
                    "scene_identity": "误入席间的来客",
                    "interaction_style": "先试探后松弛",
                    "core_identity": "机敏的局外人",
                    "story_role": "搅动静局的人",
                    "identity_anchor": "见招拆招，总要先摸清局面",
                    "temperament_type": "温醒带锋",
                    "soul_goal": "先活明白，再选站哪边",
                    "core_traits": "敏锐；会看人；嘴上留分寸",
                    "key_bonds": "自己；眼前局势",
                    "speech_style": "先轻后准，不把话说死",
                    "worldview": "局面比道理先到，真心却不能全赔进去。",
                    "belief_anchor": "再乱的场，也得先给自己留一条路。",
                    "moral_bottom_line": "不拿无辜的人去垫脚。",
                    "restraint_threshold": "被逼着选边站时才会真正翻脸。",
                    "stress_response": "越紧越会先把话说轻，再慢慢收口。",
                }
            )

            self.assertTrue(created["card_id"])
            self.assertEqual(created["fields"]["display_name"], "阿眠")

            listed = service.list_self_cards()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["card_id"], created["card_id"])

            fetched = service.get_self_card(created["card_id"])
            self.assertEqual(fetched["fields"]["core_identity"], "机敏的局外人")

            deleted = service.delete_self_card(created["card_id"])
            self.assertEqual(deleted["status"], "deleted")
            self.assertEqual(service.list_self_cards(), [])

    def test_opening_preset_crud_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)

            created = service.save_opening_preset(
                fields={
                    "title": "雨夜试探局",
                    "note": "三人慢慢试探，不要一开口就摊牌。",
                    "mode": "insert",
                    "participants": ["林黛玉", "贾宝玉", "薛宝钗"],
                    "controlled_character": "",
                    "scene_card_id": "",
                    "scene_card": {},
                    "self_card_id": "",
                    "self_card": {},
                    "self_name": "阿眠",
                    "self_identity": "借住府中的外客",
                    "self_style": "先轻后紧",
                }
            )

            self.assertTrue(created["card_id"])
            self.assertEqual(created["preview"]["title"], "雨夜试探局")
            self.assertEqual(created["preview"]["self_name"], "阿眠")

            listed = service.list_opening_presets()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["card_id"], created["card_id"])

            fetched = service.get_opening_preset(created["card_id"])
            self.assertEqual(fetched["fields"]["mode"], "insert")
            self.assertEqual(fetched["fields"]["participants"], ["林黛玉", "贾宝玉", "薛宝钗"])

            deleted = service.delete_opening_preset(created["card_id"])
            self.assertEqual(deleted["status"], "deleted")
            self.assertEqual(service.list_opening_presets(), [])

    def test_opening_preset_keeps_snapshots_after_cards_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)

            scene_card = service.save_scene_card(
                fields={
                    "title": "花厅夜宴",
                    "time_hint": "入夜",
                    "location": "花厅",
                    "atmosphere": "笑里带锋",
                    "opening_situation": "众人都在等谁先把话递出去。",
                    "public_goal": "先把席面稳住。",
                    "hidden_tension": "每个人都在看彼此站哪边。",
                    "scene_drive": "让试探慢慢逼近真话。",
                    "expected_rhythm": "慢热试探",
                    "forbidden_topics": "旧账",
                }
            )
            self_card = service.save_self_card(
                fields={
                    "display_name": "阿眠",
                    "scene_identity": "借住府中的外客",
                    "interaction_style": "先轻后紧",
                    "core_identity": "会看局的人",
                    "story_role": "外来变量",
                    "identity_anchor": "先看局面再递话",
                    "temperament_type": "轻醒克制",
                    "soul_goal": "给自己挣一块能站稳的地方",
                    "core_traits": "敏锐；留分寸；有后手",
                    "key_bonds": "自己；少数值得信的人",
                    "speech_style": "先轻描淡写，再慢慢收紧",
                    "worldview": "热闹背后总有人在算账。",
                    "belief_anchor": "先护住自己，才谈得上护别人。",
                    "moral_bottom_line": "不拿无辜人垫脚。",
                    "restraint_threshold": "被逼着替别人背锅时会翻脸。",
                    "stress_response": "越紧越像在闲谈。",
                }
            )

            preset = service.save_opening_preset(
                fields={
                    "title": "夜宴自己入席",
                    "note": "适合慢慢把气氛绷起来。",
                    "mode": "insert",
                    "participants": ["林黛玉", "贾宝玉"],
                    "scene_card_id": scene_card["card_id"],
                    "scene_card": {
                        "card_id": scene_card["card_id"],
                        "fields": scene_card["fields"],
                        "preview": scene_card["preview"],
                    },
                    "self_card_id": self_card["card_id"],
                    "self_card": {
                        "card_id": self_card["card_id"],
                        "fields": self_card["fields"],
                        "preview": self_card["preview"],
                    },
                    "self_name": "阿眠",
                    "self_identity": "借住府中的外客",
                    "self_style": "先轻后紧",
                }
            )

            service.delete_scene_card(scene_card["card_id"])
            service.delete_self_card(self_card["card_id"])

            fetched = service.get_opening_preset(preset["card_id"])
            self.assertEqual(fetched["preview"]["scene_title"], "花厅夜宴")
            self.assertEqual(fetched["preview"]["self_name"], "阿眠")
            self.assertEqual(fetched["fields"]["scene_card"]["fields"]["location"], "花厅")
            self.assertEqual(fetched["fields"]["self_card"]["fields"]["core_identity"], "会看局的人")

    def test_generate_self_card_returns_complete_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                return_value={
                    "content": json.dumps(
                        {
                            "display_name": "沈雾",
                            "scene_identity": "寄住高门的外来账房",
                            "interaction_style": "试探里带一点笑",
                            "core_identity": "善算局的外来人",
                            "story_role": "让旧局失衡的新变量",
                            "identity_anchor": "先看谁在装稳，再决定把话递给谁",
                            "temperament_type": "松弛机警",
                            "soul_goal": "替自己挣一条能站稳的路",
                            "hidden_desire": "想有人真正把她当自己人",
                            "inner_conflict": "既想靠近热闹，又怕真心被拿去做账",
                            "self_cognition": "知道自己最会看缝下针",
                            "private_self": "一个人时反而安静",
                            "speech_style": "先轻描淡写，再慢慢逼近重点",
                            "cadence": "句子不急，尾音常常收住",
                            "typical_lines": "这话也不必说满；容我再看一步",
                            "signature_phrases": "不急；再看一步",
                            "sentence_openers": "先；容我",
                            "sentence_endings": "也罢；就是了",
                            "social_mode": "见人下菜，却不轻贱人",
                            "thinking_style": "先拆局，再找最省力的入口",
                            "decision_rules": "先保余地；再押关键人",
                            "reward_logic": "肯把力气用在会回看自己的人身上",
                            "worldview": "局势会骗人，人心却总在细处漏底。",
                            "belief_anchor": "给自己留路，不等于先把心卖掉。",
                            "moral_bottom_line": "不把无辜者推到刀口前。",
                            "restraint_threshold": "被逼着替人背锅时会彻底翻脸。",
                            "core_traits": "敏锐；会周旋；不轻信",
                            "key_bonds": "自己；局中少数真心人",
                            "forbidden_behaviors": "替人白白送命；空口效忠",
                            "stress_response": "越乱越像在闲谈，其实脑子转得更快",
                            "emotion_model": "情绪不先上脸，先藏进字缝里",
                            "anger_style": "声音更轻，话却更准",
                            "joy_style": "笑意不大，却会多给一步台阶",
                            "grievance_style": "不立刻诉苦，反而更客气",
                            "others_impression": "看着和气，实则很会拿分寸",
                        },
                        ensure_ascii=False,
                    )
                }
            )

            with patch.object(service, "_build_runtime_parts", return_value=fake_parts):
                payload = service.generate_self_card()

            self.assertEqual(payload["fields"]["display_name"], "沈雾")
            self.assertEqual(payload["fields"]["core_identity"], "善算局的外来人")
            self.assertEqual(payload["preview"]["speech_style"], "先轻描淡写，再慢慢逼近重点")

    def test_create_dialogue_session_uses_selected_self_card_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            card = service.save_self_card(
                fields={
                    "display_name": "阿眠",
                    "scene_identity": "园中借住的外客",
                    "interaction_style": "初见试探",
                    "core_identity": "看得懂人情的局外人",
                    "story_role": "掀开静水的一只手",
                    "identity_anchor": "先看局，再决定要不要把真话说透",
                    "temperament_type": "轻醒克制",
                    "soul_goal": "给自己争一个不必仰人鼻息的位置",
                    "core_traits": "敏锐；稳口风；会留后手",
                    "key_bonds": "自己；少数值得信的人",
                    "speech_style": "柔声开口，话尾常带一点试探",
                    "worldview": "热闹场面里，真正要紧的总是没说出口的那句。",
                    "belief_anchor": "先护住自己，才谈得上护别人。",
                    "moral_bottom_line": "不借别人的血给自己铺路。",
                    "restraint_threshold": "被人逼着替错局收尾时会转硬。",
                    "stress_response": "越紧张越像在闲话家常。",
                }
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    payload["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session = service.create_dialogue_session(
                    payload["run_id"],
                    mode="insert",
                    participants=["林黛玉", "贾宝玉"],
                    self_card_id=card["card_id"],
                    self_profile={},
                )

            self.assertEqual(session["session_card"]["self_card_id"], card["card_id"])
            self.assertEqual(session["session_card"]["self_insert"]["display_name"], "阿眠")
            self.assertEqual(session["session_card"]["self_insert"]["core_identity"], "看得懂人情的局外人")

    def test_insert_session_keeps_snapshot_after_self_card_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            card = service.save_self_card(
                fields={
                    "display_name": "阿眠",
                    "scene_identity": "园中借住的外客",
                    "interaction_style": "初见试探",
                    "core_identity": "看得懂人情的局外人",
                    "story_role": "掀开静水的一只手",
                    "identity_anchor": "先看局，再决定要不要把真话说透",
                    "temperament_type": "轻醒克制",
                    "soul_goal": "给自己争一个不必仰人鼻息的位置",
                    "core_traits": "敏锐；稳口风；会留后手",
                    "key_bonds": "自己；少数值得信的人",
                    "speech_style": "柔声开口，话尾常带一点试探",
                    "worldview": "热闹场面里，真正要紧的总是没说出口的那句。",
                    "belief_anchor": "先护住自己，才谈得上护别人。",
                    "moral_bottom_line": "不借别人的血给自己铺路。",
                    "restraint_threshold": "被人逼着替错局收尾时会转硬。",
                    "stress_response": "越紧张越像在闲话家常。",
                }
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    payload["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ):
                session = service.create_dialogue_session(
                    payload["run_id"],
                    mode="insert",
                    participants=["林黛玉", "贾宝玉"],
                    self_card_id=card["card_id"],
                    self_profile={},
                )

            service.delete_self_card(card["card_id"])

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "林黛玉", "message": "你这话倒说得轻。"}],
            ):
                replied = service.reply_dialogue_turn(
                    payload["run_id"],
                    session_id=session["session_id"],
                    message="我只是先来看看风向。",
                )

            self.assertEqual(replied["session_card"]["self_insert"]["display_name"], "阿眠")
            self.assertEqual(replied["transcript"][-2]["speaker"], "阿眠")
            self.assertEqual(replied["transcript"][-1]["speaker"], "林黛玉")

    def test_session_keeps_scene_card_snapshot_after_scene_card_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            scene_card = service.save_scene_card(
                fields={
                    "title": "花厅夜宴",
                    "time_hint": "掌灯时分",
                    "location": "花厅暖阁",
                    "atmosphere": "灯火明亮，席间暗潮涌动",
                    "opening_situation": "席上看似热闹，真正要说的话却都压在杯盏间。",
                    "public_goal": "把场面撑得体面周全。",
                    "hidden_tension": "有人想借席间一句话逼出真正立场。",
                    "scene_drive": "从寒暄慢慢推到失手说破。",
                    "expected_rhythm": "前松后紧",
                    "forbidden_topics": "旧案；婚事",
                }
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    payload["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "花厅里酒气微暖。"}],
            ):
                session = service.create_dialogue_session(
                    payload["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                    scene_card_id=scene_card["card_id"],
                )

            service.delete_scene_card(scene_card["card_id"])

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "贾宝玉", "message": "这话怎么偏偏此刻提起。"}],
            ):
                replied = service.reply_dialogue_turn(
                    payload["run_id"],
                    session_id=session["session_id"],
                    message="门外忽然传来一阵急促脚步声。",
                    message_kind="narration",
                )

            self.assertEqual(replied["session_card"]["scene_card"]["title"], "花厅夜宴")
            self.assertEqual(replied["session_card"]["scene_card"]["location"], "花厅暖阁")

    def test_switch_dialogue_scene_card_updates_snapshot_and_appends_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            first_scene = service.save_scene_card(
                fields={
                    "title": "雨夜回廊",
                    "time_hint": "夜深",
                    "location": "回廊",
                    "atmosphere": "安静发紧",
                    "opening_situation": "两个人被雨声隔在檐下。",
                    "public_goal": "先把话探清。",
                    "hidden_tension": "谁也不愿先摊牌。",
                    "scene_drive": "从试探推向明说。",
                    "expected_rhythm": "慢热",
                    "forbidden_topics": "旧案",
                }
            )
            second_scene = service.save_scene_card(
                fields={
                    "title": "花厅对坐",
                    "time_hint": "掌灯后",
                    "location": "花厅",
                    "atmosphere": "表面客气，底下绷紧",
                    "opening_situation": "众人散后，只剩两盏灯和未尽的话。",
                    "public_goal": "把今晚的场面圆过去。",
                    "hidden_tension": "有人想逼出真正立场。",
                    "scene_drive": "把局势往摊牌再推一步。",
                    "expected_rhythm": "前松后紧",
                    "forbidden_topics": "婚事",
                }
            )
            payload = service.create_run(
                novel_name="hongloumeng.txt",
                novel_content_base64=base64.b64encode("林黛玉见了贾宝玉。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉", "贾宝玉"],
            )
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    payload["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "雨还没停。"}],
            ):
                session = service.create_dialogue_session(
                    payload["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                    scene_card_id=first_scene["card_id"],
                )

            switched = service.switch_dialogue_scene_card(
                payload["run_id"],
                session_id=session["session_id"],
                scene_card_id=second_scene["card_id"],
                transition_message="雨势更大，众人只得移进花厅，把未说完的话接着往下说。",
            )

            self.assertEqual(switched["session_card"]["scene_card_id"], second_scene["card_id"])
            self.assertEqual(switched["session_card"]["scene_card"]["title"], "花厅对坐")
            self.assertEqual(switched["transcript"][-1]["speaker"], "场景提示")
            self.assertIn("移进花厅", switched["transcript"][-1]["message"])
            self.assertIn("花厅对坐", switched["session_memory_summary"]["scene_frame"])

    def test_service_prefers_storage_root_env_when_explicit_root_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage_root = Path(tmp) / "custom-storage"
            with patch.dict(os.environ, {"ZAOMENG_STORAGE_DIR": str(storage_root)}, clear=False):
                service = WebRunService()

            self.assertEqual(service.storage_root, storage_root)
            self.assertEqual(service.runs_root, storage_root / "runs")
            self.assertEqual(service.settings_path, storage_root / "model_settings.json")
            self.assertTrue(service.runs_root.exists())

    def test_persona_web_references_filters_dictionary_like_results(self):
        fake_html = """
        <html><body>
          <li class="b_algo">
            <h2>江（汉语汉字）_百度百科</h2>
            <p>江，通用规范汉字，一级字，读作 jiang，常见于江河湖海的名称。</p>
          </li>
          <li class="b_algo">
            <h2>江澄角色介绍</h2>
            <p>江澄是《魔道祖师》中的重要角色，性格冷厉而重情，成长线鲜明。</p>
          </li>
        </body></html>
        """

        refs = collect_persona_web_references(
            character="江澄",
            novel_title="魔道祖师",
            fetch_text=lambda url, timeout: fake_html,
        )

        self.assertEqual(len(refs), 1)
        self.assertIn("江澄", refs[0]["title"])

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

    def test_get_app_update_status_ignores_non_utf8_launcher_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            fake_launcher = Path(tmp) / "zaomeng-binary"
            fake_launcher.write_bytes(b"\x00\xff\x00\xff")
            service._launcher_path_hint = str(fake_launcher)

            status = service.get_app_update_status(force_check=True)

            self.assertEqual(status["status"], "unsupported")
            self.assertFalse(status["supported"])
            self.assertEqual(status["launcher_path"], "")

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

    def test_list_runs_skips_partially_written_manifest(self):
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
            broken_dir = Path(tmp) / "runs" / "run-broken"
            broken_dir.mkdir(parents=True)
            (broken_dir / "run_manifest.json").write_text("{", encoding="utf-8")

            items = service.list_runs()

            self.assertEqual([item["run_id"] for item in items], [payload["run_id"]])

    def test_list_runs_tolerates_legacy_nested_payload_maps(self):
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
                novel_content_base64=base64.b64encode("王熙凤见了史湘云。晴雯与袭人也在场。".encode("utf-8")).decode("ascii"),
                characters=["王熙凤", "史湘云", "晴雯", "袭人"],
            )
            manifest_path = Path(tmp) / "runs" / payload["run_id"] / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.setdefault("artifacts", {}).setdefault("payloads", {})["distill_characters"] = {
                "王熙凤": r"D:\work2\Dreamforge\.zaomeng-web\runs\run-legacy\payloads\distill_王熙凤.json",
                "史湘云": r"D:\work2\Dreamforge\.zaomeng-web\runs\run-legacy\payloads\distill_史湘云.json",
                "晴雯": r"D:\work2\Dreamforge\.zaomeng-web\runs\run-legacy\payloads\distill_晴雯.json",
                "袭人": r"D:\work2\Dreamforge\.zaomeng-web\runs\run-legacy\payloads\distill_袭人.json",
            }
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            items = service.list_runs()

            self.assertEqual([item["run_id"] for item in items], [payload["run_id"]])
            self.assertIn("payload_distill", items[0]["file_urls"])
            self.assertNotIn("payload_distill_characters", items[0]["file_urls"])

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
            self.assertIn("增量蒸馏 2 人", refreshed["redistill"]["summary"])
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

    def test_restart_run_distill_requeues_selected_existing_characters_when_reusing_source(self):
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
            self.assertEqual(refreshed["redistill"]["resume_completed_characters"], [])
            self.assertEqual(refreshed["redistill"]["pending_characters"], ["林黛玉", "薛宝钗"])
            self.assertEqual(refreshed["progress"]["completed_characters"], [])
            self.assertEqual(refreshed["progress"]["completed_count"], 0)
            self.assertEqual(refreshed["summary"]["characters_completed"], 0)
            self.assertIn("增量蒸馏 2 人", refreshed["redistill"]["summary"])
            self.assertEqual(refreshed["capabilities"]["distill"]["outputs"]["update_mode"], "incremental")
            start_background_run.assert_called_once()

    def test_restart_run_distill_requeues_single_existing_character_for_incremental_redistill(self):
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
            (persona_dir / "PROFILE.generated.md").write_text("- name: 林黛玉\n- core_identity: 才女\n", encoding="utf-8")
            service.refresh_run(payload["run_id"])

            with patch.object(service, "_start_background_run") as start_background_run:
                refreshed = service.restart_run_distill(
                    payload["run_id"],
                    characters=["林黛玉"],
                    max_sentences=120,
                    max_chars=50000,
                )

            self.assertEqual(refreshed["redistill"]["existing_characters"], ["林黛玉"])
            self.assertEqual(refreshed["redistill"]["pending_characters"], ["林黛玉"])
            self.assertEqual(refreshed["redistill"]["resume_completed_characters"], [])
            self.assertIn("增量蒸馏 1 人", refreshed["redistill"]["summary"])
            start_background_run.assert_called_once()

    def test_suggest_redistill_segments_returns_dialogue_heavy_windows_for_weak_profile(self):
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
                novel_content_base64=base64.b64encode(
                    (
                        "林黛玉轻声道：“你怎么也在这里？”"
                        "贾宝玉笑道：“我正等你。”"
                        "林黛玉心想，这人说话轻浮，却又不全是假意。"
                        "林黛玉又问了两句，贾宝玉都接了话。"
                        "袭人远远看着，只觉两人气氛古怪。"
                    ).encode("utf-8")
                ).decode("ascii"),
                characters=["林黛玉"],
            )
            run_dir = Path(tmp) / "runs" / payload["run_id"]
            persona_dir = run_dir / "artifacts" / "characters" / "hongloumeng" / "林黛玉"
            persona_dir.mkdir(parents=True, exist_ok=True)
            (persona_dir / "PROFILE.generated.md").write_text(
                "- name: 林黛玉\n- core_identity: 贾府外来才女\n- story_role: 女主角之一\n- speech_style:\n- key_bonds:\n",
                encoding="utf-8",
            )
            service.refresh_run(payload["run_id"])

            suggested = service.suggest_redistill_segments(payload["run_id"], "林黛玉", max_segments=2)

            self.assertEqual(suggested["character"], "林黛玉")
            self.assertEqual(suggested["source_name"], "hongloumeng.txt")
            self.assertEqual(suggested["source_kind"], "initial")
            self.assertIn("speech_style", suggested["weak_fields"])
            self.assertTrue(suggested["segments"])
            first = suggested["segments"][0]
            self.assertGreaterEqual(first["dialogue_hits"], 1)
            self.assertIn("speech_style", first["estimated_fields"])
            self.assertIn("对白密度较高", first["reason"])
            self.assertTrue(str(first["preview"]).strip())

    def test_suggest_redistill_segments_reads_latest_incremental_source(self):
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
                novel_content_base64=base64.b64encode("第一章里林黛玉出场。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )

            with patch.object(service, "_start_background_run"):
                service.restart_run_distill(
                    payload["run_id"],
                    characters=["林黛玉", "薛宝钗"],
                    novel_name="hongloumeng-2.txt",
                    novel_content_base64=base64.b64encode(
                        (
                            "第二章里薛宝钗入府。"
                            "薛宝钗笑道：“早听过妹妹名声。”"
                            "林黛玉看了她一眼，没有立刻作声。"
                            "薛宝钗心想，先把话说软些。"
                        ).encode("utf-8")
                    ).decode("ascii"),
                )

            suggested = service.suggest_redistill_segments(payload["run_id"], "薛宝钗", max_segments=2)

            self.assertTrue(str(suggested["source_name"]).endswith("hongloumeng-2.txt"))
            self.assertEqual(suggested["source_kind"], "incremental_update")
            self.assertTrue(suggested["segments"])
            self.assertIn("speech_style", suggested["segments"][0]["estimated_fields"])

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
            self.assertEqual(stopped["progress"]["stage"], "characters_locked")
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

    def test_write_json_preserves_stop_requested_from_existing_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run_id = "run-preserve-stop"
            run_dir = Path(tmp) / "runs" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = run_dir / "run_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "status": "running",
                        "control": {
                            "stop_requested": True,
                            "stop_requested_at": "2026-05-11T10:00:00Z",
                            "stop_acknowledged_at": "",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            stale_payload = {
                "run_id": run_id,
                "status": "running",
                "control": {
                    "stop_requested": False,
                    "stop_requested_at": "",
                    "stop_acknowledged_at": "",
                },
            }
            service._write_json(manifest_path, stale_payload)
            merged = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertTrue(merged["control"]["stop_requested"])
            self.assertEqual(merged["control"]["stop_requested_at"], "2026-05-11T10:00:00Z")

    def test_stop_run_updates_latest_manifest_snapshot(self):
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

            manifest_path = Path(tmp) / "runs" / run["run_id"] / "run_manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload.setdefault("progress", {})["current_character"] = "林黛玉"
            payload["updated_at"] = "2026-05-11T12:00:00Z"
            manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            stale_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            stale_manifest["progress"]["current_character"] = ""
            stale_manifest["updated_at"] = "2000-01-01T00:00:00Z"
            stale_manifest.pop("events", None)

            with patch("src.web.service_facades.runs.stop_run_manifest", side_effect=lambda _manifest, *, utc_now: _manifest):
                with patch.object(service, "_load_manifest", return_value=stale_manifest):
                    stopped = service.stop_run(run["run_id"])

            self.assertEqual(stopped["progress"]["current_character"], "林黛玉")
            self.assertEqual(stopped["updated_at"], "2026-05-11T12:00:00Z")

    def test_update_manifest_uses_latest_file_snapshot_under_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run_id = "run-atomic-update"
            manifest_path = Path(tmp) / "runs" / run_id / "run_manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "status": "running",
                        "progress": {"current_character": "林黛玉"},
                        "updated_at": "2026-05-11T12:00:00Z",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            done = threading.Event()
            result_holder: dict[str, Any] = {}

            def writer() -> None:
                def updater(current: dict[str, Any]) -> dict[str, Any]:
                    current.setdefault("control", {})["stop_requested"] = True
                    return current

                result_holder["payload"] = service._update_manifest(manifest_path, updater)
                done.set()

            fresh_payload = {
                "run_id": run_id,
                "status": "running",
                "progress": {"current_character": "薛宝钗"},
                "updated_at": "2026-05-11T12:01:00Z",
            }
            with service._manifest_lock_context(manifest_path):
                worker = threading.Thread(target=writer)
                worker.start()
                manifest_path.write_text(json.dumps(fresh_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            done.wait(timeout=3)
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())

            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["progress"]["current_character"], "薛宝钗")
            self.assertEqual(persisted["updated_at"], "2026-05-11T12:01:00Z")
            self.assertTrue(bool(persisted.get("control", {}).get("stop_requested", False)))
            self.assertEqual(result_holder["payload"]["progress"]["current_character"], "薛宝钗")

    def test_start_background_run_uses_latest_manifest_snapshot_under_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run_id = "run-background-atomic"
            run_dir = Path(tmp) / "runs" / run_id
            manifest_path = run_dir / "run_manifest.json"
            novel_path = run_dir / "input" / "novel.txt"
            novel_path.parent.mkdir(parents=True, exist_ok=True)
            novel_path.write_text("Alpha meets Beta.", encoding="utf-8")
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "status": "running",
                        "progress": {"stage": "characters_locked", "message": "ready"},
                        "summary": {"status_text": "ready"},
                        "updated_at": "2026-05-11T12:00:00Z",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            finished = threading.Event()

            def worker() -> None:
                with patch("src.web.service_facades.runtime_support.start_background_thread"):
                    service._start_background_run(
                        manifest_path=manifest_path,
                        novel_path=novel_path,
                        locked_characters=["Alpha"],
                        max_sentences=120,
                        max_chars=50000,
                    )
                finished.set()

            with service._manifest_lock_context(manifest_path):
                thread = threading.Thread(target=worker)
                thread.start()
                manifest_path.write_text(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "status": "running",
                            "progress": {"stage": "characters_locked", "message": "fresh"},
                            "summary": {"status_text": "fresh"},
                            "latest_marker": "keep-me",
                            "updated_at": "2026-05-11T12:01:00Z",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            finished.wait(timeout=3)
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())

            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["latest_marker"], "keep-me")
            self.assertEqual(persisted["progress"]["stage"], "queued")
            self.assertEqual(persisted["summary"]["status_text"], "waiting_for_payloads")

    def test_process_relation_graph_preserves_latest_relation_repairs_during_prepare(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run_id = "run-relation-prepare"
            run_dir = Path(tmp) / "runs" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = run_dir / "run_manifest.json"
            payload_dir = run_dir / "payloads"
            payload_dir.mkdir(parents=True, exist_ok=True)
            novel_path = run_dir / "input" / "novel.txt"
            novel_path.parent.mkdir(parents=True, exist_ok=True)
            novel_path.write_text("Alpha meets Beta. Alpha distrusts Gamma.", encoding="utf-8")
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "novel_id": "novel",
                        "quality": {
                            "excerpt_focus": {"matched_characters": [], "missing_characters": [], "strategy": ""},
                            "stage_presence": [],
                            "character_focus": {},
                            "profile_repairs": {"count": 0, "characters": []},
                            "relation_repairs": {"count": 2, "pairs": ["Alpha_Beta", "Alpha_Gamma"]},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            def write_json(path: Path, payload: dict[str, object]) -> None:
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            def update_manifest(path: Path, updater):
                current = json.loads(path.read_text(encoding="utf-8"))
                updated = updater(dict(current))
                next_payload = current if updated is None else updated
                write_json(path, next_payload)
                return next_payload

            with self.assertRaisesRegex(RuntimeError, "stop after prepare"):
                process_relation_graph(
                    novel_path=novel_path,
                    graph_cast=["Alpha", "Beta"],
                    max_sentences=120,
                    max_chars=50000,
                    manifest_path=manifest_path,
                    payload_dir=payload_dir,
                    novel_id="novel",
                    parts=Mock(),
                    config=Mock(),
                    on_relation=lambda stage, payload: None,
                    assert_run_not_stopped=lambda *args, **kwargs: None,
                    write_json=write_json,
                    update_manifest=update_manifest,
                    build_quality_snapshot=service._build_quality_snapshot,
                    update_manifest_chunk_progress=update_manifest_chunk_progress,
                    generate_relation_markdown=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("stop after prepare")),
                    maybe_repair_generated_relations=lambda **kwargs: None,
                    load_relations_source=lambda path: {},
                    export_relations_source=lambda **kwargs: {},
                    utc_now=lambda: "2026-05-12T00:00:00Z",
                    relation_repairs_getter=lambda current: (current.get("quality", {}) or {}).get("relation_repairs", {}),
                    quality_matched=set(),
                    quality_missing=set(),
                    quality_focus={},
                    profile_repair_characters=[],
                )

            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["quality"]["relation_repairs"]["count"], 2)
            self.assertEqual(
                persisted["quality"]["relation_repairs"]["pairs"],
                ["Alpha_Beta", "Alpha_Gamma"],
            )

    def test_ingest_character_result_uses_latest_manifest_snapshot_atomic(self):
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
            run_id = payload["run_id"]
            manifest_path = Path(tmp) / "runs" / run_id / "run_manifest.json"
            latest = json.loads(manifest_path.read_text(encoding="utf-8"))
            latest["ingest_external_marker"] = "keep-character"
            manifest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            profile_text = "\n".join(
                [
                    "- name: 林黛玉",
                    "- novel_id: hongloumeng",
                    "- core_identity: 贾府外来才女",
                    "- speech_style: 清冷带刺",
                ]
            )
            refreshed = service.ingest_character_result(
                run_id,
                character="林黛玉",
                content_base64=base64.b64encode(profile_text.encode("utf-8")).decode("ascii"),
            )

            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed.get("ingest_external_marker"), "keep-character")
            self.assertEqual(persisted.get("ingest_external_marker"), "keep-character")

    def test_ingest_relation_result_uses_latest_manifest_snapshot_atomic(self):
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
            run_id = payload["run_id"]
            manifest_path = Path(tmp) / "runs" / run_id / "run_manifest.json"
            latest = json.loads(manifest_path.read_text(encoding="utf-8"))
            latest["ingest_external_marker"] = "keep-relation"
            manifest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
                run_id,
                content_base64=base64.b64encode(relations_text.encode("utf-8")).decode("ascii"),
                filename="hongloumeng_relations.md",
            )

            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed.get("ingest_external_marker"), "keep-relation")
            self.assertEqual(persisted.get("ingest_external_marker"), "keep-relation")

    def test_refresh_run_uses_latest_manifest_snapshot(self):
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
            run_id = payload["run_id"]
            manifest_path = Path(tmp) / "runs" / run_id / "run_manifest.json"

            latest = json.loads(manifest_path.read_text(encoding="utf-8"))
            latest["status"] = "running"
            latest["summary"] = {"status_text": "running"}
            latest["updated_at"] = "2026-05-12T08:00:00Z"
            manifest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            stale_payload = dict(latest)
            stale_payload["updated_at"] = "2000-01-01T00:00:00Z"
            stale_payload["summary"] = {"status_text": "stale"}

            with patch.object(service, "_load_manifest", return_value=stale_payload):
                refreshed = service.refresh_run(run_id)

            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertNotEqual(persisted["summary"]["status_text"], "stale")
            self.assertNotEqual(persisted["updated_at"], "2000-01-01T00:00:00Z")
            self.assertEqual(persisted["updated_at"], refreshed["updated_at"])

    def test_automatic_pipeline_finalize_uses_latest_manifest_snapshot(self):
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

            real_update_manifest = service._update_manifest
            injected_before_finalize = {"value": False}

            def wrapped_update_manifest(path: Path, updater, create_if_missing: bool = False):
                if Path(path) == manifest_path and hasattr(updater, "__code__"):
                    names = set(getattr(updater.__code__, "co_names", ()))
                    if {
                        "_apply_finalize_success_update",
                        "_apply_finalize_success_without_graph_update",
                    } & names:
                        latest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        latest["external_marker"] = "keep-me"
                        manifest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                        injected_before_finalize["value"] = True
                return real_update_manifest(path, updater, create_if_missing=create_if_missing)

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                with patch.object(service, "_maybe_repair_generated_profile", return_value=None):
                    with patch.object(service, "_maybe_repair_generated_relations", return_value=None):
                        with patch.object(service, "_update_manifest", side_effect=wrapped_update_manifest):
                            result = service._run_automatic_pipeline(
                                manifest_path=manifest_path,
                                novel_path=novel_path,
                                locked_characters=["Alpha"],
                                max_sentences=120,
                                max_chars=50000,
                            )

            self.assertTrue(result["success"])
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(injected_before_finalize["value"])
            self.assertEqual(persisted.get("external_marker"), "keep-me")

    def test_automatic_pipeline_steps_use_latest_manifest_snapshot(self):
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

            real_update_manifest = service._update_manifest
            injected_before_step_update = {"value": False}
            update_call_count = {"value": 0}

            def wrapped_update_manifest(path: Path, updater, create_if_missing: bool = False):
                if Path(path) == manifest_path:
                    update_call_count["value"] += 1
                    if update_call_count["value"] == 4 and not injected_before_step_update["value"]:
                        latest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        latest["step_external_marker"] = "keep-step"
                        manifest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                        injected_before_step_update["value"] = True
                return real_update_manifest(path, updater, create_if_missing=create_if_missing)

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts):
                with patch.object(service, "_maybe_repair_generated_profile", return_value=None):
                    with patch.object(service, "_maybe_repair_generated_relations", return_value=None):
                        with patch.object(service, "_update_manifest", side_effect=wrapped_update_manifest):
                            result = service._run_automatic_pipeline(
                                manifest_path=manifest_path,
                                novel_path=novel_path,
                                locked_characters=["Alpha"],
                                max_sentences=120,
                                max_chars=50000,
                            )

            self.assertTrue(result["success"])
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(injected_before_step_update["value"])
            self.assertGreaterEqual(update_call_count["value"], 4)
            self.assertEqual(persisted.get("step_external_marker"), "keep-step")

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

    def test_automatic_pipeline_redistills_selected_existing_characters_on_same_source_restart(self):
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
                if "- name: 林黛玉" in prompt:
                    return {
                        "content": "# PROFILE\n- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 敏感清醒之人\n- soul_goal: 守住自尊与真心\n- speech_style: 清冷里带锋芒\n- cadence: 轻快后忽然收紧\n- signature_phrases: 我自有我的想法；也不必如此\n- typical_lines: 我自有我的想法；也不必如此\n- sentence_openers: 我；你们\n- sentence_endings: 罢了；也就如此\n- worldview: 真心比热闹更要紧。\n- belief_anchor: 情意不能拿来敷衍。\n- moral_bottom_line: 不肯拿真心去换体面。\n- restraint_threshold: 伤到心时会立刻冷下来。\n- stress_response: 越难过越先把话收窄。\n"
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
            self.assertTrue((run_dir / "payloads" / "distill_林黛玉.json").exists())
            self.assertTrue((run_dir / "payloads" / "distill_薛宝钗.json").exists())
            first_payload = json.loads((run_dir / "payloads" / "distill_林黛玉.json").read_text(encoding="utf-8"))
            self.assertEqual(first_payload["request"]["update_mode"], "incremental")
            self.assertIn("林黛玉", first_payload["request"]["existing_profiles"])
            self.assertEqual(result["summary"]["characters_completed"], 2)
            self.assertCountEqual(
                [item["name"] for item in result["artifact_index"]["characters"]],
                ["林黛玉", "薛宝钗"],
            )
            self.assertTrue(result["redistill"]["recent_changes"])
            first_change = result["redistill"]["recent_changes"][0]
            self.assertEqual(first_change["character"], "林黛玉")
            self.assertGreaterEqual(first_change["changed_count"], 1)
            self.assertIn("core_identity", first_change["changed_fields"])
            self.assertTrue(
                any(
                    item.get("stage") == "redistill_character_updated" and item.get("character") == "林黛玉"
                    for item in result["events"]
                )
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
            repair_messages = next(
                call.args[0]
                for call in fake_parts.llm.chat_completion.call_args_list
                if "REPAIR_TASK" in call.args[0][1]["content"]
            )
            self.assertIn("REPAIR_TASK", repair_messages[1]["content"])
            self.assertIn("剧情碎句", repair_messages[1]["content"])

    def test_automatic_pipeline_surface_field_sanitizer_drops_transient_patch_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            profile_path = Path(tmp) / "PROFILE.generated.md"
            profile_path.write_text(
                "# PROFILE\n- name: 甲\n- novel_id: demo\n- appearance_feature: 证据不足\n- habit_action: 证据不足\n",
                encoding="utf-8",
            )

            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                return_value={
                    "content": "- appearance_feature: 只见他回头看了一眼，忽然转身就走\n- habit_action: 他说完就立刻转身离开\n"
                }
            )
            config = Mock(get=Mock(side_effect=lambda key, default=None: default))
            payload = {
                "prompt": "system",
                "references": {"output_schema": "", "style_differ": "", "logic_constraint": "", "validation_policy": ""},
                "request": {"excerpt": "甲回头看了一眼。", "excerpt_stages": {"start": "", "mid": "", "end": ""}},
                "meta": {"novel_id": "demo"},
            }

            repaired = service._maybe_repair_generated_profile(
                parts=fake_parts,
                config=config,
                payload=payload,
                character="甲",
                peer_characters=[],
                source_path=profile_path,
            )

            self.assertIsNotNone(repaired)
            self.assertIn("- appearance_feature: 证据不足", repaired)
            self.assertIn("- habit_action: 证据不足", repaired)

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

    def test_parse_dialogue_suggestion_rejects_generic_observe_wrapper(self):
        with self.assertRaisesRegex(ValueError, "explanation instead of a direct sendable line"):
            parse_dialogue_suggestion("要不先让他们把刚才那句接下去？")

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

    def test_generate_dialogue_suggestion_retries_with_compact_payload_after_bad_request(self):
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
                character="林黛玉",
                content_base64=base64.b64encode(
                    (
                        "- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 林府孤女\n"
                        "- story_role: 情感核心\n- speech_style: 轻冷带刺\n- temperament_type: 敏感自持\n"
                        "- stress_response: 越难受越把话说轻\n- key_bonds: 贾宝玉；贾母；紫鹃\n"
                    ).encode("utf-8")
                ).decode("ascii"),
            )
            service.ingest_character_result(
                run_id,
                character="贾宝玉",
                content_base64=base64.b64encode(
                    (
                        "- name: 贾宝玉\n- novel_id: hongloumeng\n- core_identity: 贾府公子\n"
                        "- story_role: 情感引线\n- speech_style: 软中带急\n- temperament_type: 多情敏感\n"
                        "- stress_response: 心急时话更碎\n- key_bonds: 林黛玉；薛宝钗；袭人\n"
                    ).encode("utf-8")
                ).decode("ascii"),
            )
            manifest = service._require_manifest(run_id)
            relation_path = Path(tmp) / "relations.md"
            relation_path.write_text("贾宝玉与林黛玉彼此牵挂。" * 400, encoding="utf-8")
            manifest["artifact_index"]["relation_graph"] = {"relations_file": str(relation_path)}
            (service.runs_root / run_id / "run_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            session = service.dialogue.create_session(
                manifest,
                mode="insert",
                participants=["林黛玉", "贾宝玉"],
                controlled_character="",
                self_profile={
                    "display_name": "阿眠",
                    "scene_identity": "误入园中的来客",
                    "interaction_style": "先软后稳",
                    "core_identity": "不肯轻易交底的来客",
                    "story_role": "意外闯入的变量",
                    "soul_goal": "先站稳再谈真心",
                    "speech_style": "先轻后准，不把话说死",
                    "worldview": "热闹场面里，没说出口的话更要紧。" * 20,
                    "belief_anchor": "先护住自己，才谈得上护别人。",
                    "stress_response": "越紧越先把语气放轻。",
                    "key_bonds": "自己；眼前局势；少数值得信的人；还没看透的人",
                },
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            raw_session["history"] = [
                {"speaker": "林黛玉", "message": f"第{i}句对话" * 20, "ts": "2026-05-09T00:00:00Z"}
                for i in range(8)
            ]
            service.dialogue._write_json(service.dialogue._session_file(run_id, session["session_id"]), raw_session)

            with patch("src.web.service_facades.dialogue.build_runtime_parts") as build_parts:
                fake_parts = Mock()
                fake_parts.llm.chat_completion.side_effect = [
                    LLMRequestError("LLM 请求失败: 400 Bad Request | prompt is too long"),
                    {"content": "你别急，我不是来添乱的。", "raw": {}},
                ]
                build_parts.return_value = fake_parts

                result = service.suggest_dialogue_turn(
                    run_id,
                    session_id=session["session_id"],
                    seed_text="我不是那个意思，我只是",
                )

            self.assertEqual(result["suggestion"], "你别急，我不是来添乱的。")
            self.assertEqual(fake_parts.llm.chat_completion.call_count, 2)
            first_prompt = fake_parts.llm.chat_completion.call_args_list[0].args[0][1]["content"]
            second_prompt = fake_parts.llm.chat_completion.call_args_list[1].args[0][1]["content"]
            self.assertLess(len(second_prompt), len(first_prompt))
            self.assertIn("误入园中的来客", second_prompt)

    def test_build_turn_payload_includes_memory_context_and_trims_relation_excerpt(self):
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
                        (
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n"
                            f"- story_role: 关键人物\n- speech_style: 有自己的语气\n- stress_response: 越急越压着说\n"
                        ).encode("utf-8")
                    ).decode("ascii"),
                )

            manifest = service._require_manifest(run_id)
            relation_path = Path(tmp) / "relations.md"
            relation_path.write_text(
                "\n".join(
                    [
                        "无关铺垫 " * 80,
                        "## 林黛玉_贾宝玉",
                        "- trust: 8",
                        "- evidence: 林黛玉与贾宝玉彼此牵挂，却都不肯把话说透。",
                        "- conflict: 一句轻话也容易拧成心事。",
                        "别的人物关系 " * 120,
                    ]
                ),
                encoding="utf-8",
            )
            manifest["artifact_index"]["relation_graph"] = {"relations_file": str(relation_path)}
            (service.runs_root / run_id / "run_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            session = service.dialogue.create_session(
                manifest,
                mode="observe",
                participants=["林黛玉", "贾宝玉"],
                scene_profile={
                    "title": "花厅夜谈",
                    "location": "花厅",
                    "public_goal": "把误会说开",
                    "hidden_tension": "两人嘴硬心软",
                },
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            raw_session["history"] = [
                {"speaker": "林黛玉", "message": "你不要把这句说得这样轻巧。", "ts": "2026-05-12T00:00:00Z"},
                {"speaker": "贾宝玉", "message": "我明晚会回来把误会说开。", "ts": "2026-05-12T00:00:01Z"},
            ]
            raw_session["state"] = {
                "memory": {
                    "summary": {
                        "summary": "两人前面已经因一句话生过闷气，但都还惦记对方。",
                        "key_points": ["林黛玉嘴上轻冷，心里还在意。", "贾宝玉想解释，却总把话说得更乱。"],
                        "compressed_turns": 18,
                        "recent_turns_kept": 24,
                    }
                }
            }
            service.dialogue._write_json(service.dialogue._session_file(run_id, session["session_id"]), raw_session)
            store = service.dialogue._resolve_memory_store(run_id)
            assert store is not None
            store.append_long_term_memory(
                session["session_id"],
                "林黛玉 -> 贾宝玉: 先前那句轻慢话已经成了两人之间的小心结。",
                metadata={"speaker": "林黛玉", "target": "贾宝玉", "kind": "dialogue"},
            )
            store.append_long_term_memory(
                session["session_id"],
                "场景旧线：他们早就约好要把误会摊开说清，只是谁也不肯先服软。",
                metadata={"speaker": "场景提示", "kind": "summary"},
            )

            payload = service.dialogue._build_turn_payload(
                manifest,
                raw_session,
                turn_id="turn-test",
                message="宝玉，你先别急着解释。",
            )

            memory_context = payload.get("memory_context", {})
            self.assertTrue(memory_context.get("session_summary", {}).get("recap"))
            self.assertTrue(memory_context.get("session_summary", {}).get("recent_conflicts"))
            self.assertTrue(memory_context.get("session_summary", {}).get("current_goal"))
            self.assertTrue(memory_context.get("session_summary", {}).get("unresolved_threads"))
            self.assertTrue(memory_context.get("session_summary", {}).get("current_location"))
            self.assertTrue(memory_context.get("session_summary", {}).get("current_companions"))
            self.assertTrue(memory_context.get("session_summary", {}).get("pending_commitments"))
            self.assertEqual(memory_context.get("archived_summary", {}).get("compressed_turns"), 18)
            self.assertTrue(memory_context.get("retrieved_memories"))
            retrieved_text = " ".join(str(item.get("text", "")) for item in memory_context["retrieved_memories"])
            self.assertIn("误会", retrieved_text)
            relation_excerpt = str(payload.get("relation_context", {}).get("relations_excerpt", ""))
            self.assertLess(len(relation_excerpt), 4000)
            self.assertIn("林黛玉_贾宝玉", relation_excerpt)

    def test_session_memory_summary_keeps_commitments_actions_and_major_beats(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="demo.txt",
                novel_content_base64=base64.b64encode("甲见了乙。".encode("utf-8")).decode("ascii"),
                characters=["甲", "乙"],
            )
            run_id = run["run_id"]
            for name in ("甲", "乙"):
                service.ingest_character_result(
                    run_id,
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: demo\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )
            manifest = service._require_manifest(run_id)
            session = service.dialogue.create_session(
                manifest,
                mode="observe",
                participants=["甲", "乙"],
                scene_profile={
                    "title": "雨夜回廊",
                    "location": "回廊",
                    "atmosphere": "压着话",
                    "scene_card_id": "scene-1",
                    "public_goal": "把误会摊开说清",
                    "hidden_tension": "乙其实并不信甲",
                },
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            raw_session["history"] = [
                {"speaker": "甲", "message": "我明天会回来，把这件事亲自说清。", "ts": "2026-05-12T00:00:00Z"},
                {"speaker": "乙", "message": "你不要再拿这种话来搪塞我。", "ts": "2026-05-12T00:00:01Z"},
                {"speaker": "甲", "message": "（转身看向门外）我没有想躲。", "ts": "2026-05-12T00:00:02Z"},
                {"speaker": "场景提示", "message": "雨声忽然压下来，回廊里安静得只剩呼吸。", "ts": "2026-05-12T00:00:03Z"},
            ]
            raw_session["state"] = service.dialogue._empty_session_state()
            raw_session["state"]["signals"] = {
                "recent": [
                    {"kind": "atmosphere_shift", "cue": "雨声忽然压下来，回廊里安静得只剩呼吸。"},
                ],
                "by_type": {},
                "updated_at": "2026-05-12T00:00:03Z",
            }
            summary = service.dialogue._build_session_memory_summary(run_id, raw_session, service.dialogue._serialize_transcript(raw_session))

            self.assertIn("明天会回来", summary.get("recent_commitments", ""))
            self.assertIn("不要再拿这种话来搪塞我", summary.get("recent_conflicts", ""))
            self.assertIn("转身看向门外", summary.get("recent_actions", ""))
            self.assertIn("雨声忽然压下来", summary.get("major_beats", ""))
            self.assertIn("把误会摊开说清", summary.get("current_goal", ""))
            self.assertIn("甲还挂着", summary.get("unresolved_threads", ""))
            self.assertIn("雨夜回廊", summary.get("current_location", ""))
            self.assertIn("甲、乙", summary.get("current_companions", ""))
            self.assertIn("待完成承诺", summary.get("pending_commitments", ""))

    def test_dialogue_relation_delta_and_character_snapshot_are_session_isolated(self):
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
                        (
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: {name}人物\n"
                            f"- story_role: {name}位置\n- speech_style: {name}自有口气\n- stress_response: {name}越急越压住\n"
                        ).encode("utf-8")
                    ).decode("ascii"),
                )

            relation_path = Path(tmp) / "relations.md"
            original_relation_text = "\n".join(
                [
                    "# RELATION_GRAPH",
                    "",
                    "## 林黛玉_贾宝玉",
                    "- trust: 8",
                    "- affection: 9",
                    "- hostility: 1",
                    "- ambiguity: 3",
                ]
            )
            relation_path.write_text(original_relation_text, encoding="utf-8")
            manifest = service._require_manifest(run_id)
            manifest["artifact_index"]["relation_graph"] = {"relations_file": str(relation_path)}
            (service.runs_root / run_id / "run_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            session_one = service.dialogue.create_session(manifest, mode="observe", participants=["林黛玉", "贾宝玉"])
            session_two = service.dialogue.create_session(manifest, mode="observe", participants=["林黛玉", "贾宝玉"])

            pending_payload = {
                "session_id": session_one["session_id"],
                "input": {
                    "speaker": "林黛玉",
                    "participants": ["林黛玉", "贾宝玉"],
                    "active_participants": ["林黛玉", "贾宝玉"],
                },
            }
            service._evolve_relations_from_turn(
                run_id,
                pending_payload,
                [{"speaker": "贾宝玉", "message": "谢谢你愿意陪我一起，我不是不在意你。"}],
            )

            raw_one = service.dialogue._read_json(service.dialogue._session_file(run_id, session_one["session_id"]))
            raw_two = service.dialogue._read_json(service.dialogue._session_file(run_id, session_two["session_id"]))

            delta = raw_one.get("state", {}).get("relations", {}).get("delta", {}).get("林黛玉_贾宝玉", {})
            self.assertEqual(delta.get("trust"), 1)
            self.assertEqual(delta.get("affection"), 1)
            self.assertEqual(delta.get("hostility"), -1)
            self.assertEqual(delta.get("last_actor"), "贾宝玉")
            self.assertEqual(delta.get("last_target"), "林黛玉")
            self.assertGreaterEqual(int(delta.get("momentum", 0) or 0), 1)
            snapshot = raw_one.get("state", {}).get("characters", {}).get("snapshots", {}).get("贾宝玉", {})
            self.assertEqual(snapshot.get("interaction_state"), "softening")
            self.assertEqual(snapshot.get("last_target"), "林黛玉")
            self.assertEqual(snapshot.get("present_state"), "onstage")
            self.assertTrue(bool(snapshot.get("updated_at", "")))

            self.assertEqual(raw_two.get("state", {}).get("relations", {}).get("delta", {}), {})
            untouched_snapshot = raw_two.get("state", {}).get("characters", {}).get("snapshots", {}).get("贾宝玉", {})
            self.assertEqual(untouched_snapshot.get("present_state"), "onstage")
            self.assertFalse(bool(untouched_snapshot.get("interaction_state", "")))
            self.assertEqual(relation_path.read_text(encoding="utf-8"), original_relation_text)

    def test_build_turn_payload_includes_session_relation_delta_and_snapshots(self):
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
                        (
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: {name}人物\n"
                            f"- story_role: {name}位置\n- soul_goal: {name}想护住眼前人\n"
                            f"- speech_style: {name}自有口气\n- stress_response: {name}越急越压住\n"
                        ).encode("utf-8")
                    ).decode("ascii"),
                )
            manifest = service._require_manifest(run_id)
            session = service.dialogue.create_session(
                manifest,
                mode="observe",
                participants=["林黛玉", "贾宝玉"],
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            raw_session["state"] = {
                **dict(raw_session.get("state", {}) or {}),
                "relations": {
                    "matrix": {
                        "林黛玉_贾宝玉": {"trust": 8, "affection": 8, "hostility": 1, "ambiguity": 3}
                    },
                    "delta": {
                        "林黛玉_贾宝玉": {
                            "trust": 1,
                            "affection": 1,
                            "last_event": "刚刚把话说软了下来。",
                            "evidence_lines": ["贾宝玉->林黛玉: 谢谢你愿意陪我一起。"],
                        }
                    },
                },
                "characters": {
                    "snapshots": {
                        "贾宝玉": {
                            "mood": "放松",
                            "interaction_state": "softening",
                            "focus": "林黛玉",
                            "last_target": "林黛玉",
                            "last_message": "谢谢你愿意陪我一起。",
                        }
                    }
                },
            }

            payload = service.dialogue._build_turn_payload(
                manifest,
                raw_session,
                turn_id="turn-session-delta",
                message="你继续说。",
            )

            memory_context = payload.get("memory_context", {})
            self.assertTrue(memory_context.get("relation_delta", {}).get("林黛玉_贾宝玉"))
            self.assertTrue(memory_context.get("character_snapshots", {}).get("贾宝玉"))
            relation_excerpt = str(payload.get("relation_context", {}).get("relations_excerpt", ""))
            self.assertIn("SESSION_RELATION_STATE", relation_excerpt)
            self.assertIn("session_delta", relation_excerpt)
            detail_map = {item["name"]: item for item in payload.get("persona_contexts", [])}
            self.assertEqual(detail_map["贾宝玉"]["session_snapshot"]["interaction_state"], "softening")
            serialized = service.dialogue._serialize_session(run_id, raw_session)
            overview = dict(serialized.get("runtime_state_overview", {}) or {})
            self.assertTrue(bool(overview.get("relation_rows", [])))

    def test_dialogue_session_state_uses_canonical_grouped_schema(self):
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

            session = service.dialogue.create_session(
                service._require_manifest(run_id),
                mode="observe",
                participants=["林黛玉", "贾宝玉"],
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            state = dict(raw_session.get("state", {}) or {})

            self.assertEqual(state.get("version"), 1)
            self.assertIn("scene", state)
            self.assertIn("presence", state)
            self.assertIn("progression", state)
            self.assertIn("relations", state)
            self.assertIn("characters", state)
            self.assertIn("signals", state)
            self.assertIn("memory", state)
            self.assertIn("atmosphere_summary", dict(state.get("scene", {}) or {}))
            self.assertIn("matrix", dict(state.get("relations", {}) or {}))
            self.assertIn("delta", dict(state.get("relations", {}) or {}))
            self.assertIn("snapshots", dict(state.get("characters", {}) or {}))
            self.assertIn("beat_maturity", dict(state.get("progression", {}) or {}))
            self.assertIn("world_tension_summary", dict(state.get("progression", {}) or {}))
            overview = dict(session.get("runtime_state_overview", {}) or {})
            self.assertIn("present", overview)
            self.assertIn("offstage", overview)
            self.assertIn("pills", overview)
            self.assertIn("character_rows", overview)
            self.assertIn("relation_rows", overview)
            self.assertIn("event_rows", overview)
            self.assertIn("status_line", overview)
            self.assertIn("next_hint", overview)
            self.assertIn("current_location", overview)
            self.assertIn("current_companions", overview)
            self.assertIn("pending_commitments", overview)

    def test_dialogue_relation_state_llm_can_lightly_refine_session_delta(self):
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

            session = service.dialogue.create_session(
                service._require_manifest(run_id),
                mode="observe",
                participants=["林黛玉", "贾宝玉"],
            )
            pending_payload = {
                "session_id": session["session_id"],
                "input": {
                    "speaker": "林黛玉",
                    "participants": ["林黛玉", "贾宝玉"],
                    "active_participants": ["林黛玉", "贾宝玉"],
                },
            }
            with patch.object(
                service,
                "_generate_dialogue_relation_state",
                return_value={
                    "relation_delta": {
                        "林黛玉_贾宝玉": {
                            "trust": 2,
                            "affection": 1,
                            "last_event": "这次道谢让两人之间明显更松了一步。",
                        }
                    },
                    "character_snapshots": {
                        "贾宝玉": {
                            "mood": "放松",
                            "interaction_state": "softening",
                            "focus": "林黛玉",
                            "last_target": "林黛玉",
                        }
                    },
                },
            ):
                service._evolve_relations_from_turn(
                    run_id,
                    pending_payload,
                    [{"speaker": "贾宝玉", "message": "谢谢你愿意陪我一起。"}],
                )

            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            delta = raw_session.get("state", {}).get("relations", {}).get("delta", {}).get("林黛玉_贾宝玉", {})
            self.assertEqual(delta.get("trust"), 2)
            self.assertEqual(delta.get("affection"), 1)
            self.assertIn("明显更松", str(delta.get("last_event", "")))
            snapshot = raw_session.get("state", {}).get("characters", {}).get("snapshots", {}).get("贾宝玉", {})
            self.assertEqual(snapshot.get("interaction_state"), "softening")

    def test_dialogue_event_signals_capture_scene_and_inline_action_categories(self):
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
                characters=["林黛玉", "贾宝玉", "薛宝钗"],
            )
            run_id = run["run_id"]
            for name in ("林黛玉", "贾宝玉", "薛宝钗"):
                service.ingest_character_result(
                    run_id,
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            session = service.dialogue.create_session(
                service._require_manifest(run_id),
                mode="observe",
                participants=["林黛玉", "贾宝玉", "薛宝钗"],
            )
            pending_payload = {
                "session_id": session["session_id"],
                "input": {
                    "speaker": "场景提示",
                    "message": "夜里雨更大了，众人转入花厅，薛宝钗先回房。",
                    "message_kind": "narration",
                    "participants": ["林黛玉", "贾宝玉", "薛宝钗"],
                    "active_participants": ["林黛玉", "贾宝玉", "薛宝钗"],
                },
            }
            with patch.object(service, "_generate_dialogue_relation_state", return_value={}):
                service._evolve_relations_from_turn(
                    run_id,
                    pending_payload,
                    responses=[
                        {"speaker": "林黛玉", "message": "（低头笑了笑）那就进屋再说。"},
                        {"speaker": "贾宝玉", "message": "屋里一下安静下来，我陪你进去。"},
                    ],
                )

            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            event_signals = dict(raw_session.get("state", {}).get("signals", {}) or {})
            recent = list(event_signals.get("recent", []) or [])
            kinds = {str(item.get("kind", "")).strip() for item in recent}
            overview = dict(service.dialogue._serialize_session(run_id, raw_session).get("runtime_state_overview", {}) or {})
            event_rows = list(overview.get("event_rows", []) or [])

            self.assertIn("time_change", kinds)
            self.assertIn("environment_change", kinds)
            self.assertIn("scene_transition", kinds)
            self.assertIn("cast_exit", kinds)
            self.assertIn("micro_action", kinds)
            self.assertIn("atmosphere_shift", kinds)
            self.assertTrue(event_rows)

            micro_action = next(item for item in recent if str(item.get("kind", "")).strip() == "micro_action")
            self.assertEqual(micro_action.get("actor"), "林黛玉")
            self.assertTrue(bool(micro_action.get("should_inline", False)))

    def test_build_turn_payload_prioritizes_active_personas_for_full_context(self):
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
                characters=["林黛玉", "贾宝玉", "薛宝钗", "王熙凤", "史湘云", "探春"],
            )
            run_id = run["run_id"]
            for name in ("林黛玉", "贾宝玉", "薛宝钗", "王熙凤", "史湘云", "探春"):
                service.ingest_character_result(
                    run_id,
                    character=name,
                    content_base64=base64.b64encode(
                        (
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: {name}人物\n"
                            "- story_role: 核心角色\n- soul_goal: 各有心事\n- speech_style: 有自己的口气\n"
                            "- temperament_type: 有锋芒\n- social_mode: 见人见招\n- reward_logic: 先护住在意的人\n"
                            "- stress_response: 越急越收着说\n- key_bonds: 若干旧人\n"
                        ).encode("utf-8")
                    ).decode("ascii"),
                )
            manifest = service._require_manifest(run_id)
            session = service.dialogue.create_session(
                manifest,
                mode="observe",
                participants=["林黛玉", "贾宝玉", "薛宝钗", "王熙凤", "史湘云", "探春"],
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            raw_session["history"] = [
                {"speaker": "旁白", "message": "薛宝钗告退回房，先离开了。", "ts": "2026-05-12T00:00:00Z"},
                {"speaker": "林黛玉", "message": "那便先由我们说。", "ts": "2026-05-12T00:00:01Z"},
                {"speaker": "王熙凤", "message": "你们慢慢说，我在旁边听着。", "ts": "2026-05-12T00:00:02Z"},
            ]

            payload = service.dialogue._build_turn_payload(
                manifest,
                raw_session,
                turn_id="turn-active-persona",
                message="你们接着说。",
            )

            persona_contexts = payload["persona_contexts"]
            detail_map = {item["name"]: item for item in persona_contexts}
            self.assertEqual(detail_map["林黛玉"]["detail_level"], "full")
            self.assertEqual(detail_map["贾宝玉"]["detail_level"], "full")
            self.assertEqual(detail_map["王熙凤"]["detail_level"], "full")
            self.assertEqual(detail_map["史湘云"]["detail_level"], "full")
            self.assertEqual(detail_map["薛宝钗"]["detail_level"], "compact")
            self.assertEqual(detail_map["探春"]["detail_level"], "compact")
            self.assertIn("soul_goal", detail_map["林黛玉"]["profile"])
            self.assertNotIn("soul_goal", detail_map["探春"]["profile"])

    def test_build_suggestion_payload_keeps_controlled_character_full_persona_in_act_mode(self):
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
                characters=["林黛玉", "贾宝玉", "薛宝钗"],
            )
            run_id = run["run_id"]
            for name in ("林黛玉", "贾宝玉", "薛宝钗"):
                service.ingest_character_result(
                    run_id,
                    character=name,
                    content_base64=base64.b64encode(
                        (
                            f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: {name}人物\n"
                            f"- story_role: {name}位置\n- soul_goal: {name}想护住当前局面\n"
                            f"- speech_style: {name}自有口气\n- temperament_type: {name}性情分明\n"
                            f"- social_mode: {name}看人下话\n- reward_logic: {name}有自己偏向\n"
                            f"- stress_response: {name}越急越压住\n- key_bonds: 旧人旧事\n"
                        ).encode("utf-8")
                    ).decode("ascii"),
                )
            manifest = service._require_manifest(run_id)
            session = service.dialogue.create_session(
                manifest,
                mode="act",
                participants=["林黛玉", "贾宝玉", "薛宝钗"],
                controlled_character="林黛玉",
            )

            payload = service.dialogue.build_suggestion_payload(
                manifest,
                session_id=session["session_id"],
                seed_text="你先听我说完。",
            )

            controlled = next(item for item in payload["persona_contexts"] if item["name"] == "林黛玉")
            self.assertEqual(controlled["detail_level"], "full")
            self.assertEqual(payload["user_persona"]["source"], "controlled_character_persona")
            self.assertEqual(payload["user_persona"]["profile"]["soul_goal"], "林黛玉想护住当前局面")

    def test_compact_dialogue_suggestion_payload_trims_memory_context(self):
        payload = {
            "input": {"message": "我想说很多很多话" * 30},
            "history": [{"speaker": "林黛玉", "message": "旧对话" * 40}] * 6,
            "relation_context": {"relations_excerpt": "关系" * 1000},
            "memory_context": {
                "session_summary": {
                    "recap": "最近一拍" * 80,
                    "world": "情绪还绷着" * 80,
                    "current_goal": "把误会摊开说清" * 20,
                    "unresolved_threads": "甲还挂着要回来说清真相" * 20,
                    "current_location": "雨夜回廊 · 回廊 · 夜里" * 10,
                    "current_companions": "当前同行：甲、乙；暂未同场：丙" * 10,
                    "pending_commitments": "待完成承诺：甲明晚会回来把误会说清" * 10,
                },
                "archived_summary": {
                    "summary": "旧冲突摘要" * 120,
                    "key_points": ["要点一" * 40, "要点二" * 40, "要点三" * 40, "要点四" * 40],
                    "compressed_turns": 48,
                },
                "retrieved_memories": [
                    {"text": "命中的长期记忆" * 60, "speaker": "林黛玉", "target": "贾宝玉", "kind": "dialogue"},
                    {"text": "第二条长期记忆" * 60, "speaker": "贾宝玉", "target": "林黛玉", "kind": "dialogue"},
                    {"text": "第三条长期记忆" * 60},
                ],
            },
            "persona_contexts": [],
            "user_persona": {},
        }

        compact = compact_dialogue_suggestion_payload(payload)

        compact_memory = compact.get("memory_context", {})
        self.assertTrue(compact_memory.get("session_summary", {}).get("recap"))
        self.assertTrue(compact_memory.get("session_summary", {}).get("current_goal"))
        self.assertTrue(compact_memory.get("session_summary", {}).get("unresolved_threads"))
        self.assertTrue(compact_memory.get("session_summary", {}).get("current_location"))
        self.assertTrue(compact_memory.get("session_summary", {}).get("current_companions"))
        self.assertTrue(compact_memory.get("session_summary", {}).get("pending_commitments"))
        self.assertLessEqual(len(compact_memory.get("archived_summary", {}).get("summary", "")), 181)
        self.assertLessEqual(len(compact_memory.get("retrieved_memories", [])), 2)

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
                    "core_identity": "不肯轻易交底的来客",
                    "soul_goal": "先站稳再谈真心",
                    "speech_style": "先轻后准，不把话说死",
                    "worldview": "热闹场面里，没说出口的话更要紧",
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
            self.assertEqual(payload["user_persona"]["profile"]["core_identity"], "不肯轻易交底的来客")
            self.assertEqual(payload["user_persona"]["profile"]["soul_goal"], "先站稳再谈真心")

    def test_build_dialogue_suggestion_messages_emphasize_self_insert_persona_priority(self):
        payload = {
            "mode": "insert",
            "input": {
                "speaker": "阿眠",
                "message": "我不是那个意思",
                "participants": ["林黛玉", "贾宝玉"],
            },
            "history": [{"speaker": "林黛玉", "message": "你这话倒轻巧。"}],
            "persona_contexts": [],
            "relation_context": {"relations_excerpt": ""},
            "instructions": {
                "generation_goal": "Draft one short, natural, directly sendable next user line that fits the current scene, relationships, and persona voices.",
                "mode_rule": "Draft the user's next line as the self-insert identity inside the scene.",
                "speaker_rule": "Treat the user message as spoken by 阿眠 who enters the scene as 误入园中的来客.",
                "response_style": "Prefer one concise line that sounds like the self-insert user speaking naturally in the scene, as final sendable wording.",
            },
            "host_action": {
                "expected_output": {"suggestion": "一句可直接发送的话"},
                "output_rule": "Keep it short, in-scene, directly sendable, and never explanatory.",
            },
            "host_prompt_brief": "Help the user speak as 阿眠 inside the current scene with one natural next line.",
            "user_persona": {
                "mode": "insert",
                "speaker": "阿眠",
                "source": "self_insert_profile",
                "must_follow": "Write as the self-insert user, keeping their full role card, identity, motives, and speaking flavor consistent.",
                "profile": {
                    "display_name": "阿眠",
                    "scene_identity": "误入园中的来客",
                    "interaction_style": "先软后稳",
                    "core_identity": "不肯轻易交底的来客",
                    "soul_goal": "先站稳再谈真心",
                    "speech_style": "先轻后准，不把话说死",
                    "worldview": "热闹场面里，没说出口的话更要紧",
                    "belief_anchor": "先护住自己，才谈得上护别人",
                },
            },
        }

        messages = WebRunService._build_dialogue_suggestion_llm_messages(payload)

        self.assertIn("不只参考上下文和别人刚才的回复", messages[0]["content"])
        self.assertIn("优先服从 self-insert 的核心身份、故事位置、灵魂目标", messages[0]["content"])

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
            self.assertTrue(payload["user_persona"]["profile"]["avoid_patterns"])
            self.assertIn("pushes the plot forward", payload["instructions"]["response_style"])

    def test_build_suggestion_payload_observe_mode_carries_scene_shift_pressure(self):
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
            service.dialogue.update_scene_progress_state(
                run_id,
                session["session_id"],
                {
                    "location": "回廊",
                    "time_hint": "夜深",
                    "beat_maturity": 85,
                    "should_offer_scene_shift": True,
                    "scene_shift_reason": "雨势更大，再站在回廊里已经接不下去了",
                    "world_tension_summary": "两个人都知道下一句就该把局面带进新的地方",
                },
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(run_id, session["session_id"]))
            raw_session["history"] = [
                {"speaker": "林黛玉", "message": "你总要把这句话说清。", "ts": "2026-05-12T00:00:00Z"},
                {"speaker": "贾宝玉", "message": "我明明有话，却还是迟了一拍。", "ts": "2026-05-12T00:00:01Z"},
            ]
            service.dialogue._write_json(service.dialogue._session_file(run_id, session["session_id"]), raw_session)

            payload = service.dialogue.build_suggestion_payload(
                manifest,
                session_id=session["session_id"],
                seed_text="",
            )

            self.assertIn("turn the scene into its next beat naturally", payload["user_persona"]["profile"]["preferred_moves"])
            self.assertEqual(payload["user_persona"]["profile"]["scene_shift_reason"], "雨势更大，再站在回廊里已经接不下去了")
            self.assertTrue(payload["user_persona"]["profile"]["anchor_lines"])
            joined_anchors = " ".join(payload["user_persona"]["profile"]["anchor_lines"])
            self.assertIn("回廊", joined_anchors)
            self.assertIn("naturally turns this scene into its next beat", payload["host_prompt_brief"])
            self.assertIn("Current transition pressure", payload["host_prompt_brief"])

    def test_build_dialogue_suggestion_messages_use_scene_progress_for_observe_mode(self):
        payload = {
            "mode": "observe",
            "input": {
                "speaker": "User",
                "message": "",
                "participants": ["林黛玉", "贾宝玉"],
            },
            "persona_contexts": [],
            "user_persona": {
                "mode": "observe",
                "speaker": "User",
                "source": "observer_hint",
                "must_follow": "Write as a scene observer giving a short in-world nudge.",
                "profile": {
                    "goal": "push_plot_forward",
                    "preferred_moves": ["turn the scene into its next beat naturally"],
                    "anchor_lines": ["把误会摊开说清", "甲还挂着要回来说清真相"],
                },
            },
            "relation_context": {"relations_excerpt": ""},
            "history": [],
            "memory_context": {"scene_progress": {"offstage_participants": ["薛宝钗"]}},
            "scene_progress": {
                "time_hint": "夜深",
                "location": "回廊",
                "offstage_participants": ["薛宝钗"],
                "should_offer_scene_shift": True,
                "scene_shift_reason": "这幕已经够满，可以顺势切到花厅",
            },
            "instructions": {
                "generation_goal": "Draft one short, natural, directly sendable next user line that fits the current scene, relationships, and persona voices.",
                "mode_rule": "Draft the user's next line as a short scene-steering utterance.",
                "speaker_rule": "Treat the user message as a scene steering hint.",
                "response_style": "Prefer one short scene-driving prompt that pushes the plot forward immediately.",
                "scene_rule": "Keep the scene anchored.",
            },
            "host_action": {
                "expected_output": {"suggestion": "一句可直接发送的话"},
                "output_rule": "Keep it short, in-scene, directly sendable, and never explanatory.",
            },
            "host_prompt_brief": "Help the user guide 林黛玉, 贾宝玉 with one short prompt that naturally turns this scene into its next beat.",
            "scene_card": {},
        }

        messages = WebRunService._build_dialogue_suggestion_llm_messages(payload)

        self.assertIn("scene_progress", messages[1]["content"])
        self.assertIn("这一拍已经成熟、适合转场", messages[0]["content"])
        self.assertIn("offstage_participants", messages[0]["content"])
        self.assertIn("下一下已经发生了", messages[0]["content"])
        self.assertIn("要不先让他们把刚才那句接下去", messages[1]["content"])


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

    def test_persona_review_save_records_review_event_metadata(self):
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
            service.ingest_character_result(
                payload["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: hongloumeng\n- core_identity: 贾府外来才女\n- speech_style: 清冷带刺\n".encode("utf-8")
                ).decode("ascii"),
            )

            service.save_persona_review(
                payload["run_id"],
                "林黛玉",
                {
                    "core_identity": "自尊极重的外来才女",
                    "speech_style": "轻冷含刺，真心一动就更薄更快。",
                    "review_source": "character_overview_autofill",
                    "review_note": "model_knowledge",
                },
            )

            run = service.get_run(payload["run_id"])
            review_event = next(
                item for item in reversed(run["events"]) if item.get("stage") == "persona_review_saved" and item.get("character") == "林黛玉"
            )
            self.assertEqual(review_event["review_source"], "character_overview_autofill")
            self.assertEqual(review_event["review_note"], "model_knowledge")
            self.assertEqual(review_event["message"], "林黛玉 的人物补全已写回")
            self.assertEqual(review_event["changed_fields"], ["core_identity", "speech_style"])

    def test_persona_field_autofill_uses_web_references_and_does_not_force_save(self):
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
                novel_content_base64=base64.b64encode("林黛玉初入贾府。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: 红楼梦\n- core_identity: 贾府外来才女\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                side_effect=[
                    {"content": '{"status":"insufficient","value":"","reason":"我对这个角色的把握不够稳定。"}'},
                    {"content": '{"status":"filled","value":"对真心极敏感，也极重自尊。","reason":"多条人物分析都强调其真心与自尊。"}'},
                ]
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                return_value=[
                    {"title": "林黛玉人物分析", "snippet": "林黛玉敏感而自尊极重，极重真情。", "source": "Bing", "query": "林黛玉 红楼梦 人物分析"}
                ],
            ):
                payload = service.suggest_persona_field(run["run_id"], "林黛玉", "identity_anchor")

            self.assertEqual(payload["status"], "filled")
            self.assertIn("真心", payload["value"])
            self.assertEqual(payload["source_mode"], "web_fallback")
            self.assertEqual(fake_parts.llm.chat_completion.call_count, 2)
            review = service.get_persona_review(run["run_id"], "林黛玉")
            self.assertEqual(review["fields"]["identity_anchor"], "")

    def test_persona_field_autofill_returns_insufficient_when_web_refs_missing(self):
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
                novel_content_base64=base64.b64encode("林黛玉初入贾府。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: 红楼梦\n- core_identity: 贾府外来才女\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                return_value={"content": '{"status":"insufficient","value":"","reason":"我对这个角色的把握不够稳定。"}'}
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                return_value=[],
            ):
                payload = service.suggest_persona_field(run["run_id"], "林黛玉", "identity_anchor")

            self.assertEqual(payload["status"], "insufficient")
            self.assertIn("把握不够稳定", payload["message"])
            self.assertEqual(payload["source_mode"], "none")
            fake_parts.llm.chat_completion.assert_called_once()

    def test_persona_field_autofill_prefers_model_knowledge_before_web_lookup(self):
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
                novel_content_base64=base64.b64encode("林黛玉初入贾府。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: 红楼梦\n- core_identity: 贾府外来才女\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                return_value={"content": '{"status":"filled","value":"把真心和自尊看得极重。","reason":"经典角色知识稳定。"}'}
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                side_effect=AssertionError("web fallback should not run when model knowledge succeeds"),
            ):
                payload = service.suggest_persona_field(run["run_id"], "林黛玉", "identity_anchor")

            self.assertEqual(payload["status"], "filled")
            self.assertEqual(payload["source_mode"], "model_knowledge")
            self.assertIn("模型知识", payload["message"])
            fake_parts.llm.chat_completion.assert_called_once()

    def test_persona_field_autofill_accepts_plaintext_model_completion(self):
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
                novel_content_base64=base64.b64encode("林黛玉初入贾府。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: 红楼梦\n- core_identity: 贾府外来才女\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(return_value={"content": "把真心和自尊看得极重。"})

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                side_effect=AssertionError("web fallback should not run when plaintext model knowledge succeeds"),
            ):
                payload = service.suggest_persona_field(run["run_id"], "林黛玉", "identity_anchor")

            self.assertEqual(payload["status"], "filled")
            self.assertIn("真心", payload["value"])
            self.assertEqual(payload["source_mode"], "model_knowledge")

    def test_persona_field_autofill_retries_after_broken_brace_response(self):
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
                novel_content_base64=base64.b64encode("林黛玉初入贾府。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: 红楼梦\n- core_identity: 贾府外来才女\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                side_effect=[
                    {"content": "{"},
                    {"content": "把真心和自尊看得极重。"},
                ]
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                side_effect=AssertionError("web fallback should not run when retry succeeds"),
            ):
                payload = service.suggest_persona_field(run["run_id"], "林黛玉", "identity_anchor")

            self.assertEqual(payload["status"], "filled")
            self.assertIn("真心", payload["value"])
            self.assertEqual(payload["source_mode"], "model_knowledge")
            self.assertEqual(fake_parts.llm.chat_completion.call_count, 2)

    def test_persona_field_autofill_retries_after_broken_value_fragment_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="modao.txt",
                novel_content_base64=base64.b64encode("江澄站在船头。".encode("utf-8")).decode("ascii"),
                characters=["江澄"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="江澄",
                content_base64=base64.b64encode(
                    "- name: 江澄\n- novel_id: 魔道祖师\n- core_identity: 云梦江氏宗主\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                side_effect=[
                    {"content": '"value": "魏无羡（前师弟/宿敌）；江厌离（姐姐）；金凌（外甥）；蓝忘机（对立者/前'},
                    {"content": "魏无羡（前师弟/宿敌）；江厌离（姐姐/精神支柱）；金凌（外甥）；蓝忘机（对立者）。"},
                ]
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                side_effect=AssertionError("web fallback should not run when retry succeeds"),
            ):
                payload = service.suggest_persona_field(run["run_id"], "江澄", "key_bonds")

            self.assertEqual(payload["status"], "filled")
            self.assertNotIn('"value":', payload["value"])
            self.assertIn("魏无羡", payload["value"])
            self.assertEqual(fake_parts.llm.chat_completion.call_count, 2)

    def test_persona_field_autofill_extracts_final_candidate_from_meta_reasoning(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="modao.txt",
                novel_content_base64=base64.b64encode("江澄站在船头。".encode("utf-8")).decode("ascii"),
                characters=["江澄"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="江澄",
                content_base64=base64.b64encode(
                    "- name: 江澄\n- novel_id: 魔道祖师\n- core_identity: 云梦江氏宗主\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                return_value={
                    "content": "我们被要求为江澄这个角色补全“重要牵系”字段。我知道《魔道祖师》是墨香铜臭的作品。可以给出：魏无羡（师弟/宿敌）；金凌（外甥）；江厌离（亡姐）；虞紫鸢（亡母）；蓝忘机（对立者）。理由：我对这个角色比较熟悉。"
                }
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                side_effect=AssertionError("web fallback should not run when extraction succeeds"),
            ):
                payload = service.suggest_persona_field(run["run_id"], "江澄", "key_bonds")

            self.assertEqual(payload["status"], "filled")
            self.assertIn("魏无羡", payload["value"])
            self.assertNotIn("我们被要求", payload["value"])

    def test_persona_field_autofill_retries_when_meta_reasoning_has_no_final_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            run = service.create_run(
                novel_name="modao.txt",
                novel_content_base64=base64.b64encode("江澄站在船头。".encode("utf-8")).decode("ascii"),
                characters=["江澄"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="江澄",
                content_base64=base64.b64encode(
                    "- name: 江澄\n- novel_id: 魔道祖师\n- core_identity: 云梦江氏宗主\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                side_effect=[
                    {"content": "我们被要求补全江澄的重要牵系。我知道他和魏无羡、金凌、江厌离关系都很重要。我觉得需要提取最关键的那些。"},
                    {"content": "魏无羡（师弟/宿敌）；金凌（外甥）；江厌离（亡姐）；虞紫鸢（亡母）。"},
                ]
            )

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                side_effect=AssertionError("web fallback should not run when retry succeeds"),
            ):
                payload = service.suggest_persona_field(run["run_id"], "江澄", "key_bonds")

            self.assertEqual(payload["status"], "filled")
            self.assertIn("魏无羡", payload["value"])
            self.assertEqual(payload["source_mode"], "model_knowledge")
            self.assertEqual(fake_parts.llm.chat_completion.call_count, 2)

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

    def test_relation_details_patch_updates_relation_and_conflicts(self):
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
                    "- trust: 8",
                    "- affection: 8",
                    "- hostility: 1",
                    "- relationship_type: 牵连",
                    "- typical_interaction: 试探",
                ]
            )
            service.ingest_relation_result(
                payload["run_id"],
                content_base64=base64.b64encode(relations_text.encode("utf-8")).decode("ascii"),
                filename="hongloumeng_relations.md",
            )
            client = TestClient(create_app(service))
            patched = client.patch(
                f"/api/web/runs/{payload['run_id']}/relations/{'林黛玉_贾宝玉'}",
                json={
                    "hostility": 7,
                    "relationship_type": "拉扯",
                    "conflict_point": "真心反噬",
                },
            )
            self.assertEqual(patched.status_code, 200)
            data = patched.json()
            self.assertEqual(data["items"][0]["relationship_type"], "拉扯")
            self.assertGreaterEqual(data["conflict_count"], 1)

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
            self.assertEqual(prepared["pending_turn_summary"]["message_kind"], "dialogue")

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
            memory_summary = completed.get("session_memory_summary", {})
            self.assertEqual(memory_summary.get("mode"), "insert")
            self.assertIn("最近一拍", memory_summary.get("recap", ""))
            self.assertIn("当前主要在场", memory_summary.get("cast", ""))
            self.assertTrue(memory_summary.get("relation_drift"))
            self.assertIn("你以", memory_summary.get("perspective", ""))
            self.assertTrue(memory_summary.get("world"))

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
                    "review_source": "character_overview_autofill",
                    "review_note": "web_fallback",
                },
            )

            self.assertEqual(response.status_code, 200)
            fields = response.json()["fields"]
            self.assertIn("真心", fields["identity_anchor"])
            self.assertIn("贾母", fields["key_bonds"])
            self.assertIn("冷意", fields["anger_style"])
            run_payload = service.get_run(run["run_id"])
            review_event = next(
                item for item in reversed(run_payload["events"]) if item.get("stage") == "persona_review_saved" and item.get("character") == "林黛玉"
            )
            self.assertEqual(review_event["review_source"], "character_overview_autofill")
            self.assertEqual(review_event["review_note"], "web_fallback")

    def test_persona_field_autofill_route_returns_generated_value(self):
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
                novel_content_base64=base64.b64encode("林黛玉初入贾府。".encode("utf-8")).decode("ascii"),
                characters=["林黛玉"],
            )
            service.ingest_character_result(
                run["run_id"],
                character="林黛玉",
                content_base64=base64.b64encode(
                    "- name: 林黛玉\n- novel_id: 红楼梦\n- core_identity: 贾府外来才女\n".encode("utf-8")
                ).decode("ascii"),
            )
            fake_parts = Mock()
            fake_parts.llm.chat_completion = Mock(
                return_value={"content": '{"status":"filled","value":"对真心极敏感，也极重自尊。","reason":"证据足够。"}'}
            )
            client = TestClient(create_app(service))

            with patch("src.web.workflow.build_runtime_parts", return_value=fake_parts), patch(
                "src.web.service_facades.artifacts.collect_persona_web_references",
                return_value=[
                    {"title": "林黛玉人物分析", "snippet": "林黛玉敏感而自尊极重，极重真情。", "source": "Bing", "query": "林黛玉 红楼梦 人物分析"}
                ],
            ):
                response = client.post(
                    f"/api/web/runs/{run['run_id']}/personas/林黛玉/suggest-field",
                    json={"field": "identity_anchor"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "filled")
            self.assertIn("真心", response.json()["value"])

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
            first = sessions_response.json()["items"][0]
            self.assertIn("last_entry_preview", first)
            self.assertTrue(str(first["last_entry_preview"]).strip())

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

    def test_redistill_recommend_route_reads_latest_incremental_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            service.save_model_settings(
                provider="openai-compatible",
                model="deepseek-chat",
                base_url="https://example.com/v1",
                api_key="sk-test",
            )
            app = create_app(service)
            client = TestClient(app)
            create_response = client.post(
                "/api/web/runs",
                json={
                    "novel_name": "hongloumeng-1.txt",
                    "novel_content_base64": base64.b64encode("第一章里林黛玉出场。".encode("utf-8")).decode("ascii"),
                    "characters": ["林黛玉"],
                },
            )
            payload = create_response.json()

            with patch.object(service, "_start_background_run"):
                restarted = service.restart_run_distill(
                    payload["run_id"],
                    characters=["林黛玉", "薛宝钗"],
                    novel_name="hongloumeng-2.txt",
                    novel_content_base64=base64.b64encode(
                        (
                            "第二章里薛宝钗入府。"
                            "薛宝钗笑道：“早听过妹妹名声。”"
                            "林黛玉看了她一眼，没有立刻作声。"
                            "薛宝钗又缓缓说道：“若你不嫌，我愿陪你说会儿话。”"
                        ).encode("utf-8")
                    ).decode("ascii"),
                )

            response = client.post(
                f"/api/web/runs/{restarted['run_id']}/redistill/recommend",
                json={"character": "薛宝钗", "max_segments": 2},
            )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["character"], "薛宝钗")
            self.assertTrue(str(data["source_name"]).endswith("hongloumeng-2.txt"))
            self.assertEqual(data["source_kind"], "incremental_update")
            self.assertTrue(data["segments"])
            self.assertLessEqual(len(data["segments"]), 2)

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
                    json={"message": "你们先聊几句。", "message_kind": "narration"},
                )

            self.assertEqual(reply_response.status_code, 200)
            payload = reply_response.json()
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["transcript"][-1]["speaker"], "林黛玉")

    def test_dialogue_reply_route_can_suppress_transcript_message(self):
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
                        "participants": ["林黛玉", "贾宝玉"],
                        "controlled_character": "",
                        "self_profile": {},
                    },
                )
            session = session_response.json()

            with patch.object(
                WebRunService,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "贾宝玉", "message": "那我先接一句。"}],
            ):
                reply_response = client.post(
                    f"/api/web/runs/{run['run_id']}/dialogue/sessions/{session['session_id']}/reply",
                    json={
                        "message": "继续聊。",
                        "message_kind": "narration",
                        "suppress_transcript_message": True,
                    },
                )

            self.assertEqual(reply_response.status_code, 200)
            payload = reply_response.json()
            transcript = list(payload.get("transcript", []) or [])
            self.assertEqual(payload.get("status"), "ready")
            self.assertEqual(transcript[-1]["speaker"], "贾宝玉")
            self.assertFalse(any(str(item.get("message", "")).strip() == "继续聊。" for item in transcript))

    def test_dialogue_reply_uses_shared_long_term_memory_store(self):
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
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    run["run_id"],
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
                    run["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                )

            with patch.object(
                service,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "林黛玉", "message": "我们的目标还没改，你先别急。"}],
            ):
                replied = service.reply_dialogue_turn(
                    run["run_id"],
                    session_id=session["session_id"],
                    message="那就继续往目标走。",
                    message_kind="narration",
                )

            config = service._build_runtime_config_for_run(run_dir=service.runs_root / run["run_id"])
            parts = service._build_runtime_parts(config)
            hits = parts.session_store.search_long_term_memory(session["session_id"], "目标", top_k=5)

            self.assertTrue(hits)
            hit_texts = " ".join(str(item.get("text", "")) for item in hits)
            self.assertIn("目标", hit_texts)
            self.assertIn("长期记忆", replied["session_memory_summary"]["relation_drift"])

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


class RunPackageTests(unittest.TestCase):
    def _build_ready_run(self, service: WebRunService) -> dict[str, Any]:
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
        for name in ("林黛玉", "贾宝玉"):
            service.ingest_character_result(
                run["run_id"],
                character=name,
                content_base64=base64.b64encode(
                    f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                ).decode("ascii"),
            )
        manifest_path = service._manifest_path(run["run_id"])
        service._update_manifest(
            manifest_path,
            lambda current: {
                **current,
                "status": "ready",
                "success": True,
                "updated_at": "2026-05-13T00:00:00Z",
                "summary": {
                    **dict(current.get("summary", {}) or {}),
                    "status_text": "workflow_complete",
                },
            },
        )
        return service.get_run(run["run_id"])

    def test_export_and_import_run_package_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run = self._build_ready_run(service)

            exported = service.export_run_package(run["run_id"])
            self.assertTrue(Path(exported["path"]).exists())
            self.assertTrue(str(exported["filename"]).endswith(".zaomeng-run.zip"))

            encoded = base64.b64encode(Path(exported["path"]).read_bytes()).decode("ascii")
            imported = service.import_run_package(
                filename=exported["filename"],
                content_base64=encoded,
            )

            self.assertNotEqual(imported["run_id"], run["run_id"])
            self.assertEqual(imported["novel_id"], run["novel_id"])
            self.assertEqual(imported["status"], "ready")
            self.assertEqual(len(imported["artifact_index"]["characters"]), 2)
            self.assertFalse((Path(imported["webui"]["run_dir"]) / "dialogue").exists())

    def test_list_and_clone_builtin_novels(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run = self._build_ready_run(service)
            exported = service.export_run_package(run["run_id"], builtin=True)
            builtin_path = service.builtin_novels_root / exported["filename"]
            shutil.copy2(exported["path"], builtin_path)

            items = service.list_builtin_novels()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["novel_id"], "hongloumeng")

            cloned = service.clone_builtin_novel(items[0]["package_id"])
            self.assertNotEqual(cloned["run_id"], run["run_id"])
            self.assertEqual(cloned["entrypoint"], "builtin")
            self.assertEqual(cloned["status"], "ready")

    def test_publish_run_as_builtin_copies_package_into_builtin_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            run = self._build_ready_run(service)

            published = service.publish_run_as_builtin(run["run_id"])

            target = Path(published["package_path"])
            self.assertTrue(target.exists())
            self.assertEqual(target.parent, service.builtin_novels_root.resolve())
            items = service.list_builtin_novels()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["novel_id"], "hongloumeng")

    @unittest.skipIf(TestClient is None or create_app is None, "fastapi test client not installed")
    def test_run_package_routes_support_builtin_list_clone_import_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            app = create_app(service)
            client = TestClient(app)
            run = self._build_ready_run(service)
            exported = service.export_run_package(run["run_id"], builtin=True)
            builtin_path = service.builtin_novels_root / exported["filename"]
            shutil.copy2(exported["path"], builtin_path)

            builtin_response = client.get("/api/web/builtin-novels")
            self.assertEqual(builtin_response.status_code, 200)
            items = builtin_response.json()["items"]
            self.assertEqual(len(items), 1)

            clone_response = client.post(f"/api/web/builtin-novels/{items[0]['package_id']}/clone")
            self.assertEqual(clone_response.status_code, 200)
            self.assertEqual(clone_response.json()["entrypoint"], "builtin")

            export_response = client.get(f"/api/web/runs/{run['run_id']}/export")
            self.assertEqual(export_response.status_code, 200)
            self.assertEqual(export_response.headers["content-type"], "application/zip")

            import_response = client.post(
                "/api/web/runs/import",
                json={
                    "filename": exported["filename"],
                    "content_base64": base64.b64encode(Path(exported["path"]).read_bytes()).decode("ascii"),
                },
            )
            self.assertEqual(import_response.status_code, 200)
            self.assertEqual(import_response.json()["novel_id"], "hongloumeng")

            publish_response = client.post(f"/api/web/runs/{run['run_id']}/publish-builtin")
            self.assertEqual(publish_response.status_code, 200)
            self.assertTrue(Path(publish_response.json()["package_path"]).exists())


class DialogueTurnBehaviorTests(unittest.TestCase):
    def test_dialogue_prompt_prefers_inline_parenthetical_actions_over_standalone_narration(self):
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
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    payload["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            manifest = service._require_manifest(payload["run_id"])
            session = service.dialogue.create_session(
                manifest,
                mode="observe",
                participants=["林黛玉", "贾宝玉"],
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(payload["run_id"], session["session_id"]))
            turn_payload = service.dialogue._build_turn_payload(
                manifest,
                raw_session,
                turn_id="turn-inline-action",
                message="你们继续说。",
            )
            llm_messages = service._build_dialogue_llm_messages(turn_payload, retry_on_empty=False)
            system_prompt = llm_messages[0]["content"]

            self.assertIn("括号动作", system_prompt)
            self.assertIn("不要单独写成旁白或场景提示", system_prompt)

    def test_prepare_turn_narration_sets_scene_speaker_and_kind(self):
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
                characters=["林黛玉", "贾宝玉", "薛宝钗"],
            )
            for name in ("林黛玉", "贾宝玉", "薛宝钗"):
                service.ingest_character_result(
                    payload["run_id"],
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
                    payload["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉", "薛宝钗"],
                )

            prepared = service.prepare_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                message="门外忽然传来脚步声，屋里人都静了一拍。",
                message_kind="narration",
            )
            pending = prepared.get("pending_turn_summary", {})
            self.assertEqual(pending.get("message_kind"), "narration")
            self.assertEqual(pending.get("speaker"), "场景提示")
            self.assertTrue(2 <= int(pending.get("response_limit_hint", 0)) <= 5)

    def test_prepare_turn_filters_departed_participants_from_active_pool(self):
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
                characters=["林黛玉", "贾宝玉", "薛宝钗"],
            )
            for name in ("林黛玉", "贾宝玉", "薛宝钗"):
                service.ingest_character_result(
                    payload["run_id"],
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
                    payload["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉", "薛宝钗"],
                )

            service.prepare_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                message="先铺一下场子。",
                message_kind="narration",
            )
            service.ingest_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                responses=[
                    {"speaker": "旁白", "message": "薛宝钗告退回房，先离开了。"},
                    {"speaker": "林黛玉", "message": "那便先由我们说。"},
                ],
            )
            prepared = service.prepare_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                message="你们接着说。",
            )
            active = prepared.get("pending_turn_summary", {}).get("active_participants", [])
            self.assertIn("林黛玉", active)
            self.assertIn("贾宝玉", active)
            self.assertNotIn("薛宝钗", active)

    def test_ingest_turn_updates_scene_progress_and_future_active_participants(self):
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
                characters=["林黛玉", "贾宝玉", "薛宝钗"],
            )
            for name in ("林黛玉", "贾宝玉", "薛宝钗"):
                service.ingest_character_result(
                    payload["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                service,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ), patch.object(service, "_generate_dialogue_scene_progress", return_value={}):
                session = service.create_dialogue_session(
                    payload["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉", "薛宝钗"],
                )

            service.prepare_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                message="你们先去私人影院，我晚点回家。",
            )
            with patch.object(
                service,
                "_generate_dialogue_scene_progress",
                return_value={
                    "present_participants": ["林黛玉", "贾宝玉"],
                    "offstage_participants": ["薛宝钗"],
                    "time_hint": "夜里",
                    "location": "私人影院",
                    "progression_note": "地点已经转到私人影院，只剩林黛玉和贾宝玉同场，薛宝钗暂时留在家中。",
                    "should_offer_scene_shift": False,
                    "scene_shift_reason": "",
                },
            ):
                updated = service.ingest_dialogue_turn(
                    payload["run_id"],
                    session_id=session["session_id"],
                    responses=[
                        {"speaker": "林黛玉", "message": "那便只我们先过去。"},
                        {"speaker": "贾宝玉", "message": "我陪你一起。"},
                    ],
                )

            self.assertEqual(updated["scene_progress"]["location"], "私人影院")
            self.assertEqual(updated["scene_progress"]["time_hint"], "夜里")
            self.assertEqual(updated["scene_progress"]["present_participants"], ["林黛玉", "贾宝玉"])
            self.assertEqual(updated["scene_progress"]["offstage_participants"], ["薛宝钗"])
            self.assertTrue(updated["scene_progress"]["atmosphere_summary"])
            self.assertGreater(updated["scene_progress"]["beat_maturity"], 0)
            self.assertTrue(updated["scene_progress"]["world_tension_summary"])
            self.assertIn("夜里", updated["session_memory_summary"]["scene_frame"])
            self.assertIn("薛宝钗", updated["session_memory_summary"]["cast"])

            prepared = service.prepare_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                message="你们继续看电影。",
            )
            active = prepared.get("pending_turn_summary", {}).get("active_participants", [])
            self.assertEqual(active, ["林黛玉", "贾宝玉"])

    def test_scene_progress_can_flag_natural_scene_shift_after_longer_turn(self):
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
            for name in ("林黛玉", "贾宝玉"):
                service.ingest_character_result(
                    payload["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )

            with patch.object(
                service,
                "_generate_dialogue_responses",
                return_value=[{"speaker": "场景提示", "message": "开场。"}],
            ), patch.object(service, "_generate_dialogue_scene_progress", return_value={}):
                session = service.create_dialogue_session(
                    payload["run_id"],
                    mode="observe",
                    participants=["林黛玉", "贾宝玉"],
                )

            service.prepare_dialogue_turn(
                payload["run_id"],
                session_id=session["session_id"],
                message="这一幕差不多说开了。",
            )
            with patch.object(
                service,
                "_generate_dialogue_scene_progress",
                return_value={
                    "present_participants": ["林黛玉", "贾宝玉"],
                    "offstage_participants": [],
                    "time_hint": "夜深",
                    "location": "花厅",
                    "progression_note": "这一幕已经把话说透，适合顺势转入下一幕。",
                    "should_offer_scene_shift": True,
                    "scene_shift_reason": "情绪和信息都已经落定，适合自然切到下一幕。",
                },
            ):
                updated = service.ingest_dialogue_turn(
                    payload["run_id"],
                    session_id=session["session_id"],
                    responses=[
                        {"speaker": "林黛玉", "message": "那这句话便到这里。"},
                        {"speaker": "贾宝玉", "message": "我们也该换个地方再说。"},
                    ],
                )

            self.assertTrue(updated["scene_progress"]["should_offer_scene_shift"])
            self.assertIn("下一幕", updated["scene_progress"]["scene_shift_reason"])
            self.assertGreaterEqual(updated["scene_progress"]["beat_maturity"], 70)
            self.assertTrue(updated["scene_progress"]["world_tension_summary"])
            self.assertIn("转场提示", updated["session_memory_summary"]["scene_frame"])

    def test_scene_progress_keeps_offstage_cast_until_explicit_return(self):
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
                characters=["林黛玉", "贾宝玉", "薛宝钗"],
            )
            for name in ("林黛玉", "贾宝玉", "薛宝钗"):
                service.ingest_character_result(
                    payload["run_id"],
                    character=name,
                    content_base64=base64.b64encode(
                        f"- name: {name}\n- novel_id: hongloumeng\n- core_identity: 人物\n".encode("utf-8")
                    ).decode("ascii"),
                )
            manifest = service._require_manifest(payload["run_id"])
            session = service.dialogue.create_session(
                manifest,
                mode="observe",
                participants=["林黛玉", "贾宝玉", "薛宝钗"],
            )
            raw_session = service.dialogue._read_json(service.dialogue._session_file(payload["run_id"], session["session_id"]))
            raw_session["history"] = [
                {"speaker": "场景提示", "message": "薛宝钗先回房，只剩林黛玉和贾宝玉在花厅。", "ts": "2026-05-12T00:00:00Z"},
                {"speaker": "林黛玉", "message": "我们先把这句话说完。", "ts": "2026-05-12T00:00:01Z"},
            ]
            service.dialogue._set_session_scene_progress(
                raw_session,
                {
                    "present_participants": ["林黛玉", "贾宝玉"],
                    "offstage_participants": ["薛宝钗"],
                    "location": "花厅",
                    "time_hint": "夜里",
                },
            )

            merged = service.dialogue._merge_scene_progress_state(
                raw_session,
                {
                    "present_participants": ["林黛玉", "贾宝玉", "薛宝钗"],
                    "offstage_participants": [],
                    "location": "花厅",
                },
            )

            self.assertEqual(merged["present_participants"], ["林黛玉", "贾宝玉"])
            self.assertEqual(merged["offstage_participants"], ["薛宝钗"])

    def test_scene_progress_time_hint_moves_forward_without_regressing(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            session = {
                "participants": ["林黛玉", "贾宝玉"],
                "scene_card": {"time_hint": "傍晚"},
                "history": [
                    {"speaker": "场景提示", "message": "过了一会，灯都亮了。", "ts": "2026-05-12T00:00:00Z"},
                ],
                "state": service.dialogue._empty_session_state(),
            }
            service.dialogue._set_session_scene_progress(
                session,
                {
                    "present_participants": ["林黛玉", "贾宝玉"],
                    "offstage_participants": [],
                    "time_hint": "傍晚",
                    "location": "花厅",
                },
            )

            advanced = service.dialogue._merge_scene_progress_state(session, {"time_hint": ""})
            self.assertEqual(advanced["time_hint"], "晚上")

            regressed = service.dialogue._merge_scene_progress_state(
                session,
                {"time_hint": "下午", "present_participants": ["林黛玉", "贾宝玉"]},
            )
            self.assertEqual(regressed["time_hint"], "晚上")

    def test_scene_progress_restores_offstage_cast_after_explicit_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            session = {
                "participants": ["林黛玉", "贾宝玉", "薛宝钗"],
                "history": [
                    {"speaker": "场景提示", "message": "薛宝钗先回房，只剩林黛玉和贾宝玉在花厅。", "ts": "2026-05-12T00:00:00Z"},
                    {"speaker": "场景提示", "message": "过了一会，薛宝钗推门进来，轻声问他们可说完了。", "ts": "2026-05-12T00:01:00Z"},
                ],
                "state": service.dialogue._empty_session_state(),
            }
            service.dialogue._set_session_scene_progress(
                session,
                {
                    "present_participants": ["林黛玉", "贾宝玉"],
                    "offstage_participants": ["薛宝钗"],
                    "location": "花厅",
                    "time_hint": "夜里",
                },
            )

            merged = service.dialogue._merge_scene_progress_state(
                session,
                {
                    "present_participants": ["林黛玉", "贾宝玉", "薛宝钗"],
                    "offstage_participants": [],
                    "location": "花厅",
                },
            )

            self.assertEqual(merged["present_participants"], ["林黛玉", "贾宝玉", "薛宝钗"])
            self.assertEqual(merged["offstage_participants"], [])

    def test_scene_progress_offers_scene_shift_after_departure_reduces_cast(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WebRunService(tmp)
            session = {
                "participants": ["林黛玉", "贾宝玉", "薛宝钗"],
                "history": [
                    {"speaker": "场景提示", "message": "薛宝钗先回房，只剩林黛玉与贾宝玉留在花厅。", "ts": "2026-05-12T00:00:00Z"},
                    {"speaker": "林黛玉", "message": "那便到这里吧。", "ts": "2026-05-12T00:00:01Z"},
                    {"speaker": "贾宝玉", "message": "我送你回去。", "ts": "2026-05-12T00:00:02Z"},
                    {"speaker": "场景提示", "message": "花厅里一下静了下来。", "ts": "2026-05-12T00:00:03Z"},
                ],
                "state": service.dialogue._empty_session_state(),
            }
            service.dialogue._set_session_event_signals(
                session,
                {
                    "recent": [
                        {
                            "kind": "cast_exit",
                            "scope": "scene",
                            "actor": "薛宝钗",
                            "target": "",
                            "cue": "薛宝钗离场",
                            "source": "runtime",
                            "should_inline": False,
                            "ts": "2026-05-12T00:00:00Z",
                        }
                    ],
                    "by_type": {},
                    "updated_at": "2026-05-12T00:00:00Z",
                },
            )
            service.dialogue._set_session_scene_progress(
                session,
                {
                    "present_participants": ["林黛玉", "贾宝玉"],
                    "offstage_participants": ["薛宝钗"],
                    "time_hint": "夜里",
                    "location": "花厅",
                    "progression_note": "",
                    "should_offer_scene_shift": False,
                    "scene_shift_reason": "",
                },
            )

            derived = service.dialogue._derive_scene_progress_state(session, service.dialogue._serialize_transcript(session))

            self.assertTrue(derived["should_offer_scene_shift"])
            self.assertIn("薛宝钗已经离场", derived["scene_shift_reason"])


if __name__ == "__main__":
    unittest.main()
