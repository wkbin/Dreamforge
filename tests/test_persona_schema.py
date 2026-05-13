import unittest

from src.web.chat.helpers import compact_dialogue_suggestion_payload
from src.web.chat.service import DialogueService
from src.web.review.persona import apply_persona_review_updates, read_persona_review_fields
from src.web.review.persona_completion import build_persona_field_completion_messages
from src.web.review.profile_repair import sanitize_profile_identity_fields, sanitize_profile_surface_fields


class PersonaSchemaTests(unittest.TestCase):
    def test_persona_review_roundtrip_supports_embodiment_fields(self):
        profile = {
            "core_identity": "云梦少主",
            "gender": "男性",
            "age_stage": "青年",
            "appearance_feature": "眉目凌厉，常着紫衣",
            "habit_action": "说重话前会先攥紧指节",
            "preference_like": ["湖风", "练剑"],
            "dislike_hate": ["失控", "被人踩线"],
        }

        fields = read_persona_review_fields(profile)

        self.assertEqual(fields["gender"], "男性")
        self.assertEqual(fields["age_stage"], "青年")
        self.assertEqual(fields["appearance_feature"], "眉目凌厉，常着紫衣")
        self.assertEqual(fields["habit_action"], "说重话前会先攥紧指节")
        self.assertEqual(fields["preference_like"], "湖风；练剑")
        self.assertEqual(fields["dislike_hate"], "失控；被人踩线")

        updated = apply_persona_review_updates(
            {},
            {
                "gender": "女性",
                "age_stage": "及笄前后",
                "appearance_feature": "眉眼清冷，身形纤细",
                "habit_action": "说到要紧处会先垂眼",
                "preference_like": "花香；清茶",
                "dislike_hate": "喧闹；失礼",
            },
        )

        self.assertEqual(updated["gender"], "女性")
        self.assertEqual(updated["age_stage"], "及笄前后")
        self.assertEqual(updated["appearance_feature"], "眉眼清冷，身形纤细")
        self.assertEqual(updated["habit_action"], "说到要紧处会先垂眼")
        self.assertEqual(updated["preference_like"], ["花香", "清茶"])
        self.assertEqual(updated["dislike_hate"], ["喧闹", "失礼"])

    def test_persona_profile_payload_includes_embodiment_and_preferences(self):
        payload = DialogueService._persona_profile_payload(
            {
                "core_identity": "云梦少主",
                "story_role": "矛盾推动者",
                "gender": "男性",
                "age_stage": "青年",
                "appearance_feature": "眉目凌厉，紫衣束发",
                "habit_action": "不耐时会先偏开视线",
                "speech_style": "冷声短句",
                "temperament_type": "外硬内热",
                "stress_response": "越乱越先压低声音",
                "key_bonds": ["魏无羡"],
                "soul_goal": "守住江家",
                "worldview": "有些责任不能后退",
                "social_mode": "亲疏分明",
                "preference_like": ["清净", "秩序"],
                "dislike_hate": ["背叛", "失控"],
                "reward_logic": "肯扛事的人才值得护",
            },
            detailed=True,
        )

        self.assertEqual(payload["gender"], "男性")
        self.assertEqual(payload["age_stage"], "青年")
        self.assertEqual(payload["appearance_feature"], "眉目凌厉，紫衣束发")
        self.assertEqual(payload["habit_action"], "不耐时会先偏开视线")
        self.assertEqual(payload["preference_like"], ["清净", "秩序"])
        self.assertEqual(payload["dislike_hate"], ["背叛", "失控"])
        self.assertEqual(payload["worldview"], "有些责任不能后退")

    def test_compact_dialogue_payload_keeps_new_high_value_persona_fields(self):
        compact = compact_dialogue_suggestion_payload(
            {
                "history": [],
                "input": {"message": "你怎么突然不说话了"},
                "relation_context": {"relations_excerpt": ""},
                "memory_context": {},
                "persona_contexts": [
                    {
                        "name": "江澄",
                        "preview": {
                            "display_name": "江澄",
                            "core_identity": "云梦少主",
                            "speech_style": "冷声短句",
                            "appearance_feature": "紫衣束发，神色凌厉",
                        },
                        "profile": {
                            "core_identity": "云梦少主",
                            "story_role": "矛盾推动者",
                            "gender": "男性",
                            "age_stage": "青年",
                            "appearance_feature": "紫衣束发，神色凌厉",
                            "habit_action": "情绪起时会先攥指节",
                            "speech_style": "冷声短句",
                            "temperament_type": "外硬内热",
                            "stress_response": "越乱越先压低声音",
                            "key_bonds": ["魏无羡"],
                            "preference_like": ["清净"],
                            "dislike_hate": ["失控"],
                        },
                        "session_snapshot": {},
                    }
                ],
                "user_persona": {
                    "profile": {
                        "display_name": "我",
                        "scene_identity": "借住客人",
                        "core_identity": "局外来客",
                        "gender": "女性",
                        "age_stage": "青年",
                        "appearance_feature": "衣着素净",
                        "habit_action": "思考时会轻敲杯沿",
                        "speech_style": "轻声试探",
                        "worldview": "先看清再站位",
                        "key_bonds": ["黛玉"],
                        "preference_like": ["安静"],
                        "dislike_hate": ["失礼"],
                    },
                    "scene_card": {},
                },
            }
        )

        persona_profile = compact["persona_contexts"][0]["profile"]
        user_profile = compact["user_persona"]["profile"]

        self.assertEqual(persona_profile["appearance_feature"], "紫衣束发，神色凌厉")
        self.assertEqual(persona_profile["habit_action"], "情绪起时会先攥指节")
        self.assertEqual(persona_profile["preference_like"], ["清净"])
        self.assertEqual(persona_profile["dislike_hate"], ["失控"])
        self.assertEqual(user_profile["gender"], "女性")
        self.assertEqual(user_profile["age_stage"], "青年")
        self.assertEqual(user_profile["appearance_feature"], "衣着素净")
        self.assertEqual(user_profile["habit_action"], "思考时会轻敲杯沿")

    def test_sanitize_profile_identity_fields_normalizes_or_falls_back(self):
        profile = {
            "gender": "男",
            "age_stage": "年纪尚轻",
        }
        sanitize_profile_identity_fields(profile)
        self.assertEqual(profile["gender"], "男性")
        self.assertEqual(profile["age_stage"], "青年")

        unstable_profile = {
            "gender": "从称呼看更像是个年轻男子，应该是男",
            "age_stage": "只见他转过来时仍带着少年人的意气",
        }
        sanitize_profile_identity_fields(unstable_profile)
        self.assertEqual(unstable_profile["gender"], "证据不足")
        self.assertEqual(unstable_profile["age_stage"], "证据不足")

    def test_sanitize_profile_surface_fields_keeps_stable_and_drops_transient_values(self):
        profile = {
            "appearance_feature": "紫衣束发，神色凌厉",
            "habit_action": "情绪起时会先攥紧指节",
        }
        sanitize_profile_surface_fields(profile)
        self.assertEqual(profile["appearance_feature"], "紫衣束发，神色凌厉")
        self.assertEqual(profile["habit_action"], "情绪起时会先攥紧指节")

        transient_profile = {
            "appearance_feature": "只见他回头看了一眼，忽然转身就走",
            "habit_action": "他说完就立刻转身离开",
        }
        sanitize_profile_surface_fields(transient_profile)
        self.assertEqual(transient_profile["appearance_feature"], "证据不足")
        self.assertEqual(transient_profile["habit_action"], "证据不足")

    def test_persona_field_completion_messages_add_overlap_guidance_for_sensitive_fields(self):
        messages = build_persona_field_completion_messages(
            character="王熙凤",
            field="story_role",
            novel_title="红楼梦",
            current_fields={},
            references=[],
            use_model_knowledge=True,
        )
        self.assertIn("只写角色在剧情里承担的职能，不要重复核心身份。", messages[1]["content"])

        messages = build_persona_field_completion_messages(
            character="王熙凤",
            field="private_self",
            novel_title="红楼梦",
            current_fields={},
            references=[],
            use_model_knowledge=True,
        )
        self.assertIn("只写不对外展示的一面，不要重复内在冲突或自我认知。", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
