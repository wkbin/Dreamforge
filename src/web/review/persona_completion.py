from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


PERSONA_REVIEW_FIELD_LABELS = {
    "core_identity": "核心身份",
    "story_role": "故事位置",
    "identity_anchor": "身份锚点",
    "temperament_type": "气质底色",
    "gender": "性别",
    "age_stage": "年龄阶段",
    "appearance_feature": "外貌辨识",
    "habit_action": "习惯动作",
    "soul_goal": "灵魂目标",
    "hidden_desire": "隐秘渴望",
    "inner_conflict": "内在冲突",
    "self_cognition": "自我认知",
    "private_self": "私下的一面",
    "speech_style": "说话方式",
    "cadence": "语句节奏",
    "typical_lines": "代表句",
    "signature_phrases": "口头禅",
    "sentence_openers": "起句习惯",
    "sentence_endings": "句尾习惯",
    "social_mode": "社交模式",
    "thinking_style": "思考方式",
    "decision_rules": "决策规则",
    "reward_logic": "回报逻辑",
    "worldview": "世界观",
    "belief_anchor": "信念支点",
    "moral_bottom_line": "道德底线",
    "restraint_threshold": "失控阈值",
    "core_traits": "核心特质",
    "key_bonds": "重要牵系",
    "preference_like": "偏好喜好",
    "dislike_hate": "明显厌恶",
    "forbidden_behaviors": "不会做的事",
    "stress_response": "应激反应",
    "emotion_model": "情绪底模",
    "anger_style": "发怒方式",
    "joy_style": "开心方式",
    "grievance_style": "委屈方式",
    "others_impression": "他人观感",
}

PERSONA_REVIEW_KEY_FIELDS = (
    "core_identity",
    "identity_anchor",
    "temperament_type",
    "gender",
    "age_stage",
    "appearance_feature",
    "habit_action",
    "soul_goal",
    "core_traits",
    "key_bonds",
    "speech_style",
    "worldview",
)

PERSONA_REVIEW_ADVANCED_GROUPS = (
    (
        "定位与外显",
        (
            "story_role",
            "social_mode",
            "others_impression",
            "preference_like",
            "dislike_hate",
        ),
    ),
    (
        "内核细调",
        (
            "hidden_desire",
            "inner_conflict",
            "self_cognition",
            "private_self",
            "thinking_style",
            "decision_rules",
            "reward_logic",
            "belief_anchor",
            "moral_bottom_line",
        ),
    ),
    (
        "对白细调",
        (
            "cadence",
            "typical_lines",
            "signature_phrases",
            "sentence_openers",
            "sentence_endings",
        ),
    ),
    (
        "情绪细调",
        (
            "forbidden_behaviors",
            "restraint_threshold",
            "stress_response",
            "emotion_model",
            "anger_style",
            "joy_style",
            "grievance_style",
        ),
    ),
)

PERSONA_AUTOFILLABLE_FIELDS = {
    "core_identity",
    "story_role",
    "identity_anchor",
    "temperament_type",
    "gender",
    "age_stage",
    "appearance_feature",
    "habit_action",
    "soul_goal",
    "hidden_desire",
    "inner_conflict",
    "self_cognition",
    "private_self",
    "speech_style",
    "social_mode",
    "thinking_style",
    "worldview",
    "belief_anchor",
    "moral_bottom_line",
    "core_traits",
    "key_bonds",
    "preference_like",
    "dislike_hate",
    "others_impression",
}

_LIST_STYLE_FIELDS = {"core_traits", "key_bonds", "preference_like", "dislike_hate"}
_USER_AGENT = "zaomeng-persona-review/1.0 (+https://github.com/wkbin/zaomeng)"


def _field_completion_extra_guidance(field: str) -> list[str]:
    mapping = {
        "core_identity": ["只写客观身份与社会定位，不要混入剧情职能或自我宣言。"],
        "story_role": ["只写角色在剧情里承担的职能，不要重复核心身份。"],
        "identity_anchor": ["只写角色主观上的自我定位、立场抓手或行动凭据。"],
        "inner_conflict": ["只写角色内部拉扯，不要把自我评价或隐藏面混进来。"],
        "self_cognition": ["只写角色如何看待自己，不要改写成外界评价。"],
        "private_self": ["只写不对外展示的一面，不要重复内在冲突或自我认知。"],
    }
    return list(mapping.get(field, []))


def build_persona_field_completion_messages(
    *,
    character: str,
    field: str,
    novel_title: str,
    current_fields: dict[str, str],
    references: list[dict[str, str]] | None = None,
    use_model_knowledge: bool = False,
) -> list[dict[str, str]]:
    label = PERSONA_REVIEW_FIELD_LABELS.get(field, field)
    profile_summary = _render_profile_summary(current_fields, exclude_field=field)
    reference_text = _render_reference_summary(references or [])
    list_hint = "如果该字段适合多项值，请用全角分号“；”分隔。" if field in _LIST_STYLE_FIELDS else "只输出一个可直接落表单的自然中文结论。"
    extra_guidance = _field_completion_extra_guidance(field)
    if use_model_knowledge:
        user_prompt = "\n".join(
            [
                f"人物：{character}",
                f"作品：{novel_title or '未知作品'}",
                f"目标字段：{label} ({field})",
                "",
                "当前已知人物档案：",
                profile_summary or "（暂无其他已知字段）",
                "",
                "请先只依据你对该作品和角色的已有知识来判断能否补全这个字段。",
                "如果这是常见作品、经典角色、或你对该角色有稳定把握，可以直接给出适合写入人物校对表单的内容。",
                "如果你拿不准、记忆模糊、或只能靠猜测，请明确拒绝生成。",
                *extra_guidance,
                list_hint,
                "value 字段只能放最终要写入表单的内容，不能包含“我们要求”“需要从”“已知有”“可以根据”等分析过程。",
                "不要编造，不要输出剧情摘要，不要伪装成查到网页资料。",
                "严格返回 JSON：{\"status\":\"filled\"|\"insufficient\",\"value\":\"...\",\"reason\":\"...\"}",
            ]
        )
        system_content = (
            "你是人物资料补全助手。任务是优先根据模型已有知识，为单个角色字段生成可直接写入表单的短内容。"
            "只有在你对角色有稳定把握时才可填写；只要不确定，就必须返回 insufficient。"
            "禁止在 value 中复述任务、解释推理、列出要求，value 必须是可直接粘贴进表单的最终中文。"
        )
    else:
        user_prompt = "\n".join(
            [
                f"人物：{character}",
                f"作品：{novel_title or '未知作品'}",
                f"目标字段：{label} ({field})",
                "",
                "当前已知人物档案：",
                profile_summary or "（暂无其他已知字段）",
                "",
                "联网检索摘录：",
                reference_text or "（暂无可用网页摘录）",
                "",
                "请只根据联网摘录判断能否补全这个字段。",
                "如果资料足够，返回一段适合直接写入人物校对表单的内容。",
                "如果资料不足、互相矛盾、或只能靠脑补，请明确拒绝生成。",
                *extra_guidance,
                list_hint,
                "value 字段只能放最终要写入表单的内容，不能包含“我们要求”“需要从”“已知有”“可以根据”等分析过程。",
                "不要编造，不要把剧情长摘要塞进字段。",
                "严格返回 JSON：{\"status\":\"filled\"|\"insufficient\",\"value\":\"...\",\"reason\":\"...\"}",
            ]
        )
        system_content = (
            "你是人物资料补全助手。任务是根据给定的网页摘录，为单个角色字段生成可直接写入表单的短内容。"
            "只有在网页摘录能支撑时才可填写；只要证据不足，就必须返回 insufficient。"
            "禁止在 value 中复述任务、解释推理、列出要求，value 必须是可直接粘贴进表单的最终中文。"
        )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]


def build_persona_field_retry_messages(
    *,
    character: str,
    field: str,
    novel_title: str,
    current_fields: dict[str, str],
    references: list[dict[str, str]] | None = None,
    use_model_knowledge: bool = False,
) -> list[dict[str, str]]:
    label = PERSONA_REVIEW_FIELD_LABELS.get(field, field)
    profile_summary = _render_profile_summary(current_fields, exclude_field=field)
    reference_text = _render_reference_summary(references or [])
    extra_guidance = _field_completion_extra_guidance(field)
    if use_model_knowledge:
        user_prompt = "\n".join(
            [
                f"人物：{character}",
                f"作品：{novel_title or '未知作品'}",
                f"目标字段：{label} ({field})",
                "",
                "当前已知人物档案：",
                profile_summary or "（暂无其他已知字段）",
                "",
                "上一轮输出格式不对。",
                "现在不要 JSON，不要代码块，不要解释。",
                *extra_guidance,
                "如果你对该角色有稳定把握，只返回一句可直接写入表单的中文内容。",
                "如果你拿不准，就只返回：证据不足",
            ]
        )
    else:
        user_prompt = "\n".join(
            [
                f"人物：{character}",
                f"作品：{novel_title or '未知作品'}",
                f"目标字段：{label} ({field})",
                "",
                "当前已知人物档案：",
                profile_summary or "（暂无其他已知字段）",
                "",
                "联网检索摘录：",
                reference_text or "（暂无可用网页摘录）",
                "",
                "上一轮输出格式不对。",
                "现在不要 JSON，不要代码块，不要解释。",
                *extra_guidance,
                "如果这些摘录足够支持结论，只返回一句可直接写入表单的中文内容。",
                "如果仍然不足，就只返回：证据不足",
            ]
        )
    return [
        {"role": "system", "content": "你是人物资料补全助手。只返回最终结果本身，不要附加格式。"},
        {"role": "user", "content": user_prompt},
    ]


def parse_persona_field_completion_response(text: str) -> dict[str, str]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL).strip()
    payload = _extract_json_object(cleaned)
    if payload is None:
        return _infer_plaintext_completion(cleaned)
    status = str(payload.get("status", "")).strip().lower()
    raw_value = str(payload.get("value", "")).strip()
    value = _clean_completion_value(raw_value)
    reason = str(payload.get("reason", "")).strip()
    if status == "filled" and not value:
        return {"status": "insufficient", "value": "", "reason": "模型没有返回可直接写入表单的最终内容。"}
    if status != "filled" or not value:
        return {"status": "insufficient", "value": "", "reason": reason or "资料不足，无法可靠补全。"}
    return {"status": "filled", "value": value, "reason": reason}


def collect_persona_web_references(
    *,
    character: str,
    novel_title: str = "",
    timeout_seconds: float = 8.0,
    fetch_text: Callable[[str, float], str] | None = None,
) -> list[dict[str, str]]:
    fetcher = fetch_text or _fetch_text
    queries = _build_search_queries(character=character, novel_title=novel_title)
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for query in queries:
        for item in _search_bing(
            query,
            character=character,
            novel_title=novel_title,
            timeout_seconds=timeout_seconds,
            fetch_text=fetcher,
        ):
            key = (item.get("title", ""), item.get("snippet", ""))
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= 6:
                return results
    return results


def suggest_persona_field_payload(
    *,
    run_id: str,
    character: str,
    field: str,
    persona_dir: Path,
    manifest: dict[str, Any],
    resolve_persona_review_source: Callable[[Path], tuple[Path, Path, Path]],
    load_profile_source: Callable[[Path], dict[str, Any]],
    read_persona_review_fields: Callable[[dict[str, Any]], dict[str, str]],
    collect_references: Callable[[str, str], list[dict[str, str]]],
    chat_completion: Callable[[list[dict[str, str]], float, int], dict[str, Any]],
) -> dict[str, Any]:
    normalized_field = str(field or "").strip()
    if normalized_field not in PERSONA_AUTOFILLABLE_FIELDS:
        raise ValueError("This field does not support AI autofill.")
    _, _, source_path = resolve_persona_review_source(persona_dir)
    if not source_path.exists():
        raise FileNotFoundError(character)
    profile = load_profile_source(source_path)
    current_fields = read_persona_review_fields(profile)
    novel_title = _resolve_novel_title(manifest=manifest, profile=profile)
    model_result = chat_completion(
        build_persona_field_completion_messages(
            character=character,
            field=normalized_field,
            novel_title=novel_title,
            current_fields=current_fields,
            use_model_knowledge=True,
        ),
        0.1,
        220,
    )
    model_parsed = parse_persona_field_completion_response(str(model_result.get("content", "")))
    if _needs_plaintext_retry(model_parsed):
        retry_result = chat_completion(
            build_persona_field_retry_messages(
                character=character,
                field=normalized_field,
                novel_title=novel_title,
                current_fields=current_fields,
                use_model_knowledge=True,
            ),
            0.1,
            120,
        )
        model_parsed = parse_persona_field_completion_response(str(retry_result.get("content", "")))
    if model_parsed["status"] == "filled":
        return {
            "run_id": run_id,
            "character": character,
            "field": normalized_field,
            "label": PERSONA_REVIEW_FIELD_LABELS.get(normalized_field, normalized_field),
            "status": "filled",
            "value": model_parsed["value"],
            "message": "已按模型知识生成补全内容，请记得保存人物校对。",
            "reason": model_parsed["reason"],
            "references": [],
            "source_mode": "model_knowledge",
        }

    references = collect_references(character, novel_title)
    if not references:
        base_reason = model_parsed["reason"] or "当前模型知识不足，且没有查到足够可靠的网络资料。"
        return {
            "run_id": run_id,
            "character": character,
            "field": normalized_field,
            "label": PERSONA_REVIEW_FIELD_LABELS.get(normalized_field, normalized_field),
            "status": "insufficient",
            "value": "",
            "message": f"人物信息补全无法生成：{base_reason}",
            "reason": base_reason,
            "references": [],
            "source_mode": "none",
        }
    llm_result = chat_completion(
        build_persona_field_completion_messages(
            character=character,
            field=normalized_field,
            novel_title=novel_title,
            current_fields=current_fields,
            references=references,
        ),
        0.1,
        220,
    )
    parsed = parse_persona_field_completion_response(str(llm_result.get("content", "")))
    if _needs_plaintext_retry(parsed):
        retry_result = chat_completion(
            build_persona_field_retry_messages(
                character=character,
                field=normalized_field,
                novel_title=novel_title,
                current_fields=current_fields,
                references=references,
                use_model_knowledge=False,
            ),
            0.1,
            120,
        )
        parsed = parse_persona_field_completion_response(str(retry_result.get("content", "")))
    success = parsed["status"] == "filled"
    failure_reason = parsed["reason"] or "当前网页摘要不足以支持这个字段。"
    return {
        "run_id": run_id,
        "character": character,
        "field": normalized_field,
        "label": PERSONA_REVIEW_FIELD_LABELS.get(normalized_field, normalized_field),
        "status": parsed["status"],
        "value": parsed["value"],
        "message": "模型知识不足，已改用联网参考生成补全内容，请记得保存人物校对。" if success else f"人物信息补全无法生成：{failure_reason}",
        "reason": parsed["reason"],
        "references": references,
        "source_mode": "web_fallback",
    }


def _resolve_novel_title(*, manifest: dict[str, Any], profile: dict[str, Any]) -> str:
    for candidate in (
        profile.get("novel_title"),
        manifest.get("novel_name"),
        profile.get("novel_id"),
        manifest.get("novel_id"),
    ):
        text = str(candidate or "").strip()
        if text:
            return re.sub(r"\.(txt|md|text|epub)$", "", text, flags=re.IGNORECASE)
    return ""


def _render_profile_summary(fields: dict[str, str], *, exclude_field: str) -> str:
    lines: list[str] = []
    for key, label in PERSONA_REVIEW_FIELD_LABELS.items():
        if key == exclude_field:
            continue
        value = str(fields.get(key, "")).strip()
        if value:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines[:14])


def _render_reference_summary(references: list[dict[str, str]]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(references[:6], start=1):
        title = str(item.get("title", "")).strip() or f"结果 {index}"
        snippet = str(item.get("snippet", "")).strip()
        source = str(item.get("source", "")).strip()
        if not snippet:
            continue
        blocks.append(f"[{index}] {title}\n来源: {source or '网页摘要'}\n摘要: {snippet}")
    return "\n\n".join(blocks)


def _build_search_queries(*, character: str, novel_title: str) -> list[str]:
    base = str(character or "").strip()
    book = str(novel_title or "").strip()
    queries = [
        f"\"{base}\" \"{book}\" 人物介绍 角色".strip(),
        f"\"{base}\" \"{book}\" 人物分析 角色设定".strip(),
        f"\"{base}\" \"{book}\" 性格特点 人物".strip(),
        f"\"{base}\" \"{book}\" 角色介绍".strip(),
        f"\"{base}\" 人物介绍 {book}".strip(),
        f"\"{base}\" 角色设定 {book}".strip(),
    ]
    return [item for item in dict.fromkeys(queries) if item]


def _search_bing(
    query: str,
    *,
    character: str,
    novel_title: str,
    timeout_seconds: float,
    fetch_text: Callable[[str, float], str],
) -> list[dict[str, str]]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=zh-Hans"
    try:
        page = fetch_text(url, timeout_seconds)
    except Exception:
        return []
    blocks = re.findall(r'<li class="b_algo".*?</li>', page, flags=re.DOTALL | re.IGNORECASE)
    results: list[dict[str, str]] = []
    for block in blocks:
        title_match = re.search(r"<h2[^>]*>(.*?)</h2>", block, flags=re.DOTALL | re.IGNORECASE)
        snippet_match = re.search(r"<p[^>]*>(.*?)</p>", block, flags=re.DOTALL | re.IGNORECASE)
        title = _html_to_text(title_match.group(1)) if title_match else ""
        snippet = _html_to_text(snippet_match.group(1)) if snippet_match else ""
        if len(snippet) < 18:
            continue
        if _looks_like_dictionary_result(title=title, snippet=snippet):
            continue
        if not _looks_like_character_result(
            title=title,
            snippet=snippet,
            character=character,
            novel_title=novel_title,
        ):
            continue
        results.append(
            {
                "title": title,
                "snippet": snippet,
                "source": "Bing",
                "query": query,
            }
        )
        if len(results) >= 4:
            break
    return results


def _fetch_text(url: str, timeout_seconds: float) -> str:
    request = Request(url, headers={"User-Agent": _USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def _html_to_text(value: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", str(value or ""), flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _looks_like_dictionary_result(*, title: str, snippet: str) -> bool:
    haystack = f"{title}\n{snippet}".lower()
    junk_keywords = (
        "汉语字典",
        "汉语词典",
        "词典",
        "字典",
        "康熙字典",
        "汉典",
        "每日一字",
        "部首",
        "拼音",
        "笔画",
        "释义",
        "字义",
        "怎么读",
        "什么意思",
        "通用规范汉字",
        "一级字",
        "二级字",
        "三级字",
    )
    return any(keyword in haystack for keyword in junk_keywords)


def _looks_like_character_result(*, title: str, snippet: str, character: str, novel_title: str) -> bool:
    joined = f"{title}\n{snippet}"
    normalized_character = str(character or "").strip()
    normalized_novel = str(novel_title or "").strip()
    if normalized_character and normalized_character not in joined:
        return False
    if len(normalized_character) <= 1 and normalized_novel and normalized_novel not in joined:
        return False
    if normalized_novel:
        novel_hit = normalized_novel in joined
        role_hit = any(token in joined for token in ("人物", "角色", "主角", "配角", "设定", "性格"))
        return novel_hit or role_hit
    return True


def _extract_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _infer_plaintext_completion(text: str) -> dict[str, str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return {"status": "insufficient", "value": "", "reason": "模型没有返回可用内容。"}
    normalized = cleaned.replace("\r", "")
    if _looks_like_broken_json_value_fragment(normalized):
        return {"status": "insufficient", "value": "", "reason": "模型返回格式不完整。"}
    refusal_markers = (
        "证据不足",
        "资料不足",
        "信息不足",
        "无法可靠",
        "无法判断",
        "不确定",
        "拿不准",
        "把握不够",
        "记忆模糊",
        "不能确定",
        "无法生成",
        "insufficient",
    )
    if any(marker in normalized for marker in refusal_markers):
        return {"status": "insufficient", "value": "", "reason": cleaned}

    extracted = _extract_completion_candidate_from_meta_text(normalized)
    if extracted:
        return {"status": "filled", "value": extracted, "reason": "已从分析式返回中提取最终结果。"}

    value_match = re.search(r'(?:^|\n)(?:value|答案|建议|可写为|可填写|补全建议)\s*[:：]\s*(.+)', normalized, flags=re.IGNORECASE)
    if value_match:
        candidate = value_match.group(1).strip()
    else:
        lines = [line.strip(" -\t") for line in normalized.splitlines() if line.strip()]
        candidate = lines[0] if lines else normalized

    candidate = _clean_completion_value(candidate)
    if not candidate and _looks_like_meta_reasoning(normalized):
        return {"status": "insufficient", "value": "", "reason": "模型返回了思考过程，没有直接给出最终结果。"}
    if not candidate:
        return {"status": "insufficient", "value": "", "reason": "模型返回格式不完整。"}
    return {"status": "filled", "value": candidate, "reason": "已从自然语言返回中提取结果。"}


def _clean_completion_value(text: str) -> str:
    candidate = str(text or "").strip()
    if not candidate:
        return ""
    extracted = _extract_completion_candidate_from_meta_text(candidate)
    if extracted:
        candidate = extracted
    candidate = re.sub(r"^(可以写成|可写成|建议填写|建议写为|可填写|可写为|答案|建议)\s*[:：]?\s*", "", candidate).strip()
    candidate = candidate.strip('"').strip("“”")
    candidate = re.sub(r"\s+", " ", candidate)
    if _looks_like_meta_reasoning(candidate):
        return ""
    if _looks_like_truncated_completion_value(candidate):
        return ""
    if not _looks_like_usable_completion_value(candidate):
        return ""
    return candidate


def _looks_like_usable_completion_value(value: str) -> bool:
    text = str(value or "").strip()
    if len(text) < 2:
        return False
    if re.fullmatch(r"[\{\}\[\]\(\):：,，.;；'\"`]+", text):
        return False
    if _looks_like_broken_json_value_fragment(text):
        return False
    if _looks_like_truncated_completion_value(text):
        return False
    return True


def _looks_like_truncated_completion_value(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.endswith(("、", "，", ",", "；", ";", "：", ":", "/", "（", "(", "《", "“", "\"")):
        return True
    if text.count("（") > text.count("）"):
        return True
    if text.count("(") > text.count(")"):
        return True
    return False


def _looks_like_broken_json_value_fragment(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if re.search(r'["\']value["\']\s*:', normalized, flags=re.IGNORECASE):
        return True
    if re.search(r'["\'](?:status|reason)["\']\s*:', normalized, flags=re.IGNORECASE):
        return True
    return False


def _looks_like_meta_reasoning(text: str) -> bool:
    normalized = str(text or "").strip()
    meta_markers = (
        "我们被要求",
        "我们要求",
        "我知道",
        "我觉得",
        "我会给出",
        "我认为",
        "需要提取",
        "需要从",
        "已知有",
        "既然是",
        "理由：",
        "理由:",
        "可以提供",
        "可以根据",
        "我对这个角色",
    )
    return any(marker in normalized for marker in meta_markers)


def _extract_completion_candidate_from_meta_text(text: str) -> str:
    normalized = str(text or "").strip()
    patterns = (
        r"(?:可以根据[^。；\n]{0,60}写|可根据[^。；\n]{0,60}写)\s*[:：]\s*(.+?)(?:。理由[:：]|理由[:：]|$)",
        r"(?:可以给出|可给出|建议写成|建议填写|可写为|可填写)\s*[:：]\s*(.+?)(?:。理由[:：]|理由[:：]|$)",
        r"(?:最终答案|最终可写为|最终建议)\s*[:：]\s*(.+?)(?:。理由[:：]|理由[:：]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.DOTALL)
        if not match:
            continue
        candidate = match.group(1).strip().strip('"').strip("“”")
        candidate = re.sub(r"\s+", " ", candidate)
        if (
            _looks_like_usable_completion_value(candidate)
            and not _looks_like_meta_reasoning(candidate)
            and not _looks_like_truncated_completion_value(candidate)
        ):
            return candidate

    list_like_match = re.search(r"([^。；\n]*；[^。]*)(?:。|$)", normalized)
    if list_like_match:
        candidate = list_like_match.group(1).strip()
        candidate = re.sub(r"^(?:我觉得我可以给出|可以给出|我会给出)\s*[:：]?\s*", "", candidate)
        if (
            _looks_like_usable_completion_value(candidate)
            and not _looks_like_meta_reasoning(candidate)
            and not _looks_like_truncated_completion_value(candidate)
        ):
            return candidate
    return ""


def _needs_plaintext_retry(parsed: dict[str, str]) -> bool:
    if str(parsed.get("status", "")).strip().lower() == "filled":
        return False
    reason = str(parsed.get("reason", "")).strip()
    return reason in {
        "模型返回格式不完整。",
        "模型没有返回可用内容。",
        "模型返回了思考过程，没有直接给出最终结果。",
        "模型没有返回可直接写入表单的最终内容。",
    }
