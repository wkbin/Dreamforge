from __future__ import annotations

import re
import unicodedata
from typing import Any

from src.skill_support.novel_preparation import CHARACTER_VARIANT_MAP, MATCH_IGNORED_PATTERN
from src.web.review.profile_evidence import looks_like_dialogue_sentence, looks_like_thought_or_evaluation_sentence


_SPEECH_LIST_FIELDS = {
    "signature_phrases",
    "sentence_openers",
    "connective_tokens",
    "sentence_endings",
    "forbidden_fillers",
}
_EMOTION_FIELDS = {"anger_style", "joy_style", "grievance_style"}
_DIALOGUE_EVIDENCE_LIMIT = 12
_CANONICAL_GENDER_VALUES = (
    ("女性", ("女性", "女子", "女孩", "少女", "女郎", "姑娘", "妇人", "夫人", "娘子")),
    ("男性", ("男性", "男子", "男孩", "少年", "郎君", "公子", "少爷", "老爷")),
)
_CANONICAL_AGE_STAGE_VALUES = (
    ("孩童", ("孩童", "幼童", "小童", "稚子", "童子", "儿童")),
    ("少年", ("少年", "少男")),
    ("少女", ("少女",)),
    ("及笄前后", ("及笄",)),
    ("豆蔻前后", ("豆蔻",)),
    ("弱冠前后", ("弱冠",)),
    ("青年", ("青年", "年轻", "年少", "年纪尚轻")),
    ("中年", ("中年",)),
    ("长者", ("长者", "老者", "年长", "暮年", "老年")),
)
_PROFILE_META_INFERENCE_TOKENS = ("应该", "大概", "像是", "推测", "推断", "从称呼看", "看起来像", "更像是")
_TRANSIENT_APPEARANCE_TOKENS = ("忽然", "突然", "只见", "转过", "回头", "看了", "看向", "走了出来", "冲过来")
_TRANSIENT_HABIT_TOKENS = ("忽然", "突然", "立刻", "连忙", "转身就", "说完就", "随即", "只见", "便", "于是")


def collect_profile_repair_targets(
    profile: dict[str, Any],
    *,
    rewrite_fields: tuple[str, ...],
    dialogue_evidence: list[str] | None = None,
) -> dict[str, str]:
    issues: dict[str, str] = {}
    for field in rewrite_fields:
        value = str(profile.get(field, "")).strip()
        if not value:
            issues[field] = "为空"
            continue
        if value == "证据不足":
            continue
        if looks_like_unstable_profile_scalar(value):
            issues[field] = f"像剧情碎句或叙述片段 -> {value}"
            continue
        if len(value) <= 4:
            issues[field] = f"过短，像未完成结论 -> {value}"
    if dialogue_evidence:
        speech_style = str(profile.get("speech_style", "")).strip()
        cadence = str(profile.get("cadence", "")).strip() or str(
            (profile.get("speech_habits", {}) or {}).get("cadence", "")
        ).strip()
        signature_phrases = profile_list_value(profile, "signature_phrases")
        typical_lines = profile_list_value(profile, "typical_lines")
        sentence_openers = profile_list_value(profile, "sentence_openers")
        sentence_endings = profile_list_value(profile, "sentence_endings")

        if not speech_style or looks_generic_style_scalar(speech_style):
            issues["speech_style"] = f"太泛，缺少对白味道 -> {speech_style or '空'}"
        if not cadence:
            issues["cadence"] = "为空"
        if len(signature_phrases) == 0 and len(typical_lines) < 2:
            issues["signature_phrases"] = "太少，口头禅不够"
            issues["typical_lines"] = "太少，代表句不够"
        if len(sentence_openers) == 0 and len(sentence_endings) == 0:
            issues["sentence_openers"] = "缺少稳定的起句习惯"
            issues["sentence_endings"] = "缺少稳定的收尾习惯"
    return issues


def collect_profile_completion_groups(
    profile: dict[str, Any],
    *,
    completion_groups: tuple[tuple[str, tuple[str, ...]], ...],
    repair_targets: dict[str, str] | None = None,
) -> list[tuple[str, tuple[str, ...], dict[str, str]]]:
    groups: list[tuple[str, tuple[str, ...], dict[str, str]]] = []
    repair_lookup = dict(repair_targets or {})
    for group_name, fields in completion_groups:
        missing = tuple(field for field in fields if profile_field_is_effectively_empty(profile, field))
        group_repairs = {field: repair_lookup[field] for field in fields if field in repair_lookup}
        target_fields = tuple(dict.fromkeys([*group_repairs.keys(), *missing]))
        if target_fields:
            groups.append((group_name, target_fields, group_repairs))
    return groups


def profile_field_is_effectively_empty(profile: dict[str, Any], field: str) -> bool:
    if field == "cadence":
        value = str((profile.get("speech_habits", {}) or {}).get("cadence", "")).strip() or str(profile.get("cadence", "")).strip()
        return (not value) or value == "证据不足"
    if field in _SPEECH_LIST_FIELDS:
        values = profile_list_value(profile, field)
        return len(values) == 0 or values == ["证据不足"]
    if field in _EMOTION_FIELDS:
        value = str((profile.get("emotion_profile", {}) or {}).get(field, "")).strip() or str(profile.get(field, "")).strip()
        return (not value) or value == "证据不足"
    value = profile.get(field, "")
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return len(items) == 0 or items == ["证据不足"]
    if isinstance(value, dict):
        return not bool(value)
    text = str(value or "").strip()
    return (not text) or text == "证据不足"


def merge_profile_patch(
    profile: dict[str, Any],
    patch_text: str,
    *,
    profile_list_fields: set[str],
    profile_map_fields: set[str],
) -> None:
    for raw_line in str(patch_text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        field, raw_value = line[2:].split(":", 1)
        key = str(field or "").strip()
        value_text = str(raw_value or "").strip()
        if not key:
            continue
        if key in profile_map_fields:
            parsed_map = parse_profile_metric_map(value_text)
            if parsed_map:
                profile["values"] = parsed_map
            continue
        if key in profile_list_fields:
            items = split_profile_list_value(value_text)
            profile[key] = items or (["证据不足"] if value_text == "证据不足" else [])
            if key in _SPEECH_LIST_FIELDS:
                profile.setdefault("speech_habits", {})
                profile["speech_habits"][key] = list(profile[key])
            continue
        profile[key] = value_text
        if key == "cadence":
            profile.setdefault("speech_habits", {})
            profile["speech_habits"]["cadence"] = value_text
        elif key in _EMOTION_FIELDS:
            profile.setdefault("emotion_profile", {})
            profile["emotion_profile"][key] = value_text


def apply_profile_missing_fallbacks(
    profile: dict[str, Any],
    *,
    completion_fields: tuple[str, ...],
    profile_list_fields: set[str],
    profile_map_fields: set[str],
) -> None:
    for field in completion_fields:
        if not profile_field_is_effectively_empty(profile, field):
            continue
        if field in profile_map_fields:
            continue
        if field in profile_list_fields:
            profile[field] = ["证据不足"]
            if field in _SPEECH_LIST_FIELDS:
                profile.setdefault("speech_habits", {})
                profile["speech_habits"][field] = ["证据不足"]
            continue
        profile[field] = "证据不足"
        if field == "cadence":
            profile.setdefault("speech_habits", {})
            profile["speech_habits"]["cadence"] = "证据不足"
        elif field in _EMOTION_FIELDS:
            profile.setdefault("emotion_profile", {})
            profile["emotion_profile"][field] = "证据不足"


def sanitize_profile_identity_fields(profile: dict[str, Any]) -> None:
    gender = _sanitize_gender_value(profile.get("gender", ""))
    age_stage = _sanitize_age_stage_value(profile.get("age_stage", ""))
    if gender:
        profile["gender"] = gender
    elif "gender" in profile and str(profile.get("gender", "")).strip():
        profile["gender"] = "证据不足"
    if age_stage:
        profile["age_stage"] = age_stage
    elif "age_stage" in profile and str(profile.get("age_stage", "")).strip():
        profile["age_stage"] = "证据不足"


def sanitize_profile_surface_fields(profile: dict[str, Any]) -> None:
    appearance_feature = _sanitize_appearance_feature_value(profile.get("appearance_feature", ""))
    habit_action = _sanitize_habit_action_value(profile.get("habit_action", ""))
    if appearance_feature:
        profile["appearance_feature"] = appearance_feature
    elif "appearance_feature" in profile and str(profile.get("appearance_feature", "")).strip():
        profile["appearance_feature"] = "证据不足"
    if habit_action:
        profile["habit_action"] = habit_action
    elif "habit_action" in profile and str(profile.get("habit_action", "")).strip():
        profile["habit_action"] = "证据不足"


def split_profile_list_value(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"\s*[；;]\s*", text) if item.strip()]


def parse_profile_metric_map(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    parsed: dict[str, Any] = {}
    for part in re.split(r"\s*[；;]\s*", text):
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        key_text = key.strip()
        raw_text = raw.strip()
        if not key_text:
            continue
        try:
            parsed[key_text] = int(raw_text)
        except ValueError:
            parsed[key_text] = raw_text
    return parsed


def profile_list_value(profile: dict[str, Any], key: str) -> list[str]:
    direct = profile.get(key, [])
    if isinstance(direct, list):
        return [str(item).strip() for item in direct if str(item).strip()]
    speech_habits = profile.get("speech_habits", {})
    if isinstance(speech_habits, dict):
        nested = speech_habits.get(key, [])
        if isinstance(nested, list):
            return [str(item).strip() for item in nested if str(item).strip()]
    return []


def looks_generic_style_scalar(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    generic_tokens = (
        "冷静",
        "克制",
        "温和",
        "直接",
        "理性",
        "简短",
        "平静",
        "含蓄",
        "尖锐",
        "轻声",
    )
    return len(text) <= 8 and any(token in text for token in generic_tokens)


def extract_dialogue_evidence(payload: dict[str, Any], *, character: str) -> list[str]:
    request = dict(payload.get("request", {}) or {})
    excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
    blocks = [
        excerpt_stages.get("start", ""),
        excerpt_stages.get("mid", ""),
        excerpt_stages.get("end", ""),
        request.get("excerpt", ""),
    ]
    ranked_lines: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    order = 0
    for block in blocks:
        for raw_line in str(block or "").splitlines():
            line = raw_line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            mentions_character = _line_mentions_character(line, character)
            is_dialogue = looks_like_dialogue_sentence(line)
            is_thought = looks_like_thought_or_evaluation_sentence(line)
            if not (mentions_character or is_dialogue or is_thought):
                continue
            if mentions_character and is_dialogue:
                priority = 0
            elif mentions_character and is_thought:
                priority = 1
            elif mentions_character:
                priority = 2
            elif is_dialogue:
                priority = 3
            else:
                priority = 4
            ranked_lines.append((priority, order, line))
            order += 1
    ranked_lines.sort(key=lambda item: (item[0], item[1]))
    return [line for _, _, line in ranked_lines[:_DIALOGUE_EVIDENCE_LIMIT]]


def _line_mentions_character(line: str, character: str) -> bool:
    match_tokens = _character_match_tokens(character)
    if not match_tokens:
        return False
    normalized_line = _normalize_match_text(line)
    return any(token in normalized_line for token in match_tokens)


def _character_match_tokens(character: str) -> tuple[str, ...]:
    normalized_character = _normalize_match_text(character)
    if not normalized_character:
        return ()
    tokens = [normalized_character]
    if len(normalized_character) >= 3:
        tokens.append(normalized_character[1:])
        tokens.append(normalized_character[-2:])
    ordered: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return tuple(ordered)


def _normalize_match_text(text: str) -> str:
    sample = unicodedata.normalize("NFKC", str(text or "")).translate(CHARACTER_VARIANT_MAP)
    return MATCH_IGNORED_PATTERN.sub("", sample).lower()


def looks_like_unstable_profile_scalar(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if any(token in text for token in ('"', "“", "”", "‘", "’", "「", "」")):
        return True
    if text.endswith(("：", ":", "，", ",", "；", ";", "、")):
        return True
    if len(text) > 46:
        return True
    return bool(
        re.search(
            r"(只见|忽见|回头|转过|只听|听见|听得|说道|笑道|问道|喝道|骂道|叹道|叫道|大家想着|心里还自|拍着手|走了出来|看了.*一眼|旧诗有云|薛蟠)",
            text,
        )
    )


def _sanitize_gender_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "证据不足":
        return text
    if looks_like_unstable_profile_scalar(text) or len(text) > 8:
        return ""
    normalized = text.replace(" ", "")
    if normalized in {"男", "男性"}:
        return "男性"
    if normalized in {"女", "女性"}:
        return "女性"
    matches = [label for label, tokens in _CANONICAL_GENDER_VALUES if any(token in normalized for token in tokens)]
    return matches[0] if len(set(matches)) == 1 else ""


def _sanitize_age_stage_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "证据不足":
        return text
    if looks_like_unstable_profile_scalar(text) or len(text) > 16:
        return ""
    normalized = text.replace(" ", "")
    if re.fullmatch(r"(少年|少女|青年|中年|长者|孩童|及笄前后|豆蔻前后|弱冠前后)", normalized):
        return normalized
    matches = [label for label, tokens in _CANONICAL_AGE_STAGE_VALUES if any(token in normalized for token in tokens)]
    return matches[0] if len(set(matches)) == 1 else ""


def _sanitize_appearance_feature_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "证据不足":
        return text
    normalized = text.replace(" ", "")
    if (
        looks_like_unstable_profile_scalar(text)
        or len(text) > 32
        or any(token in text for token in _PROFILE_META_INFERENCE_TOKENS)
        or any(token in text for token in _TRANSIENT_APPEARANCE_TOKENS)
    ):
        return ""
    return text


def _sanitize_habit_action_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "证据不足":
        return text
    if (
        looks_like_unstable_profile_scalar(text)
        or len(text) > 40
        or any(token in text for token in _PROFILE_META_INFERENCE_TOKENS)
        or any(token in text for token in _TRANSIENT_HABIT_TOKENS)
    ):
        return ""
    if not any(token in text for token in ("常", "总", "会", "习惯", "每逢", "动辄", "先", "下意识")):
        return ""
    return text
