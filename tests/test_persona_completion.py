from src.web.review.persona_completion import (
    build_persona_field_completion_messages,
    parse_persona_field_completion_response,
)


def test_completion_prompt_restricts_value_to_final_form_text():
    messages = build_persona_field_completion_messages(
        character="沈照",
        field="key_bonds",
        novel_title="雾港旧事",
        current_fields={"core_identity": "失势家族的临时掌账人"},
        use_model_knowledge=True,
    )

    joined = "\n".join(message["content"] for message in messages)

    assert "value 字段只能放最终要写入表单的内容" in joined
    assert "不能包含“我们要求”“需要从”“已知有”“可以根据”等分析过程" in joined


def test_completion_parser_rejects_truncated_meta_reasoning_candidate():
    parsed = parse_persona_field_completion_response(
        "我们要求只返回一句可直接写入表单的中文内容，关于沈照的“重要牵系”。"
        "需要从已知信息中提取。已知有“核心身份：失势家族的临时掌账人”。"
        "可以根据已知信息写：与旧主、账房同僚、"
    )

    assert parsed["status"] == "insufficient"
    assert parsed["value"] == ""
    assert "思考过程" in parsed["reason"]


def test_completion_parser_cleans_meta_reasoning_inside_json_value():
    parsed = parse_persona_field_completion_response(
        '{"status":"filled","value":"我们要求只返回一句可直接写入表单的中文内容。'
        '可以根据已知信息写：旧主；账房同僚；追债人","reason":"证据足够。"}'
    )

    assert parsed["status"] == "filled"
    assert parsed["value"] == "旧主；账房同僚；追债人"
    assert "我们要求" not in parsed["value"]
