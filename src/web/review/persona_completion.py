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
    "story_role",
    "identity_anchor",
    "temperament_type",
    "soul_goal",
    "core_traits",
    "key_bonds",
    "speech_style",
    "worldview",
    "belief_anchor",
    "moral_bottom_line",
    "restraint_threshold",
    "stress_response",
)

PERSONA_REVIEW_ADVANCED_GROUPS = (
    (
        "内核细调",
        (
            "hidden_desire",
            "inner_conflict",
            "self_cognition",
            "private_self",
            "social_mode",
            "thinking_style",
            "decision_rules",
            "reward_logic",
            "others_impression",
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
    "others_impression",
}

_LIST_STYLE_FIELDS = {"core_traits", "key_bonds"}
_USER_AGENT = "zaomeng-persona-review/1.0 (+https://github.com/wkbin/zaomeng)"


def build_persona_field_completion_messages(
    *,
    character: str,
    field: str,
    novel_title: str,
    current_fields: dict[str, str],
    references: list[dict[str, str]],
) -> list[dict[str, str]]:
    label = PERSONA_REVIEW_FIELD_LABELS.get(field, field)
    profile_summary = _render_profile_summary(current_fields, exclude_field=field)
    reference_text = _render_reference_summary(references)
    list_hint = "如果该字段适合多项值，请用全角分号“；”分隔。" if field in _LIST_STYLE_FIELDS else "只输出一个可直接落表单的自然中文结论。"
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
            list_hint,
            "不要编造，不要把剧情长摘要塞进字段。",
            "严格返回 JSON：{\"status\":\"filled\"|\"insufficient\",\"value\":\"...\",\"reason\":\"...\"}",
        ]
    )
    return [
        {
            "role": "system",
            "content": (
                "你是人物资料补全助手。任务是根据给定的网页摘录，为单个角色字段生成可直接写入表单的短内容。"
                "只有在网页摘录能支撑时才可填写；只要证据不足，就必须返回 insufficient。"
            ),
        },
        {"role": "user", "content": user_prompt},
    ]


def parse_persona_field_completion_response(text: str) -> dict[str, str]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL).strip()
    payload = _extract_json_object(cleaned)
    if payload is None:
        return {"status": "insufficient", "value": "", "reason": "模型返回格式不完整。"}
    status = str(payload.get("status", "")).strip().lower()
    value = str(payload.get("value", "")).strip()
    reason = str(payload.get("reason", "")).strip()
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
        for item in _search_bing(query, timeout_seconds=timeout_seconds, fetch_text=fetcher):
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
    references = collect_references(character, novel_title)
    if not references:
        return {
            "run_id": run_id,
            "character": character,
            "field": normalized_field,
            "label": PERSONA_REVIEW_FIELD_LABELS.get(normalized_field, normalized_field),
            "status": "insufficient",
            "value": "",
            "message": "人物信息补全无法生成：暂时没有查到足够可靠的网络资料。",
            "references": [],
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
    success = parsed["status"] == "filled"
    return {
        "run_id": run_id,
        "character": character,
        "field": normalized_field,
        "label": PERSONA_REVIEW_FIELD_LABELS.get(normalized_field, normalized_field),
        "status": parsed["status"],
        "value": parsed["value"],
        "message": "已生成补全内容，请记得保存人物校对。" if success else "人物信息补全无法生成。",
        "reason": parsed["reason"],
        "references": references,
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
        f"{base} {book} 人物介绍".strip(),
        f"{base} {book} 人物分析".strip(),
        f"{base} {book} 性格特点".strip(),
        f"{base} 人物介绍".strip(),
        f"{base} 性格特点".strip(),
    ]
    return [item for item in dict.fromkeys(queries) if item]


def _search_bing(
    query: str,
    *,
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
