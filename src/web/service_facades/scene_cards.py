from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from src.web.artifacts import load_profile_source, render_profile_md
from src.web.review import (
    build_random_scene_card_messages,
    delete_scene_card_payload,
    list_scene_cards_payload,
    load_scene_card_payload,
    parse_random_scene_card_response,
    recommend_scene_cards,
    save_scene_card_payload,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class SceneCardServiceMixin:
    def list_scene_cards(self) -> list[dict[str, Any]]:
        return list_scene_cards_payload(
            self.scene_cards_root,
            load_profile_source=load_profile_source,
        )

    def get_scene_card(self, card_id: str) -> dict[str, Any]:
        return load_scene_card_payload(
            self.scene_cards_root,
            card_id,
            load_profile_source=load_profile_source,
        )

    def save_scene_card(self, *, card_id: str = "", fields: dict[str, Any]) -> dict[str, Any]:
        payload = save_scene_card_payload(
            self.scene_cards_root,
            card_id=card_id,
            fields=fields,
            render_profile_md=render_profile_md,
            utc_now=_utc_now,
        )
        return self.get_scene_card(payload["card_id"])

    def delete_scene_card(self, card_id: str) -> dict[str, str]:
        return delete_scene_card_payload(self.scene_cards_root, card_id)

    def generate_scene_card(self) -> dict[str, Any]:
        if not self.model_is_configured():
            raise ValueError("Model is not configured yet.")
        config = self._build_runtime_config_for_run(run_dir=self.storage_root)
        parts = self._build_runtime_parts(config)
        llm_result = parts.llm.chat_completion(
            build_random_scene_card_messages(),
            temperature=0.95,
            max_tokens=1600,
        )
        fields = parse_random_scene_card_response(str(llm_result.get("content", "")))
        return {
            "fields": fields,
            "preview": {
                "title": fields["title"],
                "time_hint": fields["time_hint"],
                "location": fields["location"],
                "atmosphere": fields["atmosphere"],
                "opening_situation": fields["opening_situation"],
                "scene_drive": fields["scene_drive"],
                "expected_rhythm": fields["expected_rhythm"],
            },
        }

    def recommend_scene_cards(self, *, mode: str, participants: list[str] | None = None) -> dict[str, Any]:
        cards = self.list_scene_cards()
        return recommend_scene_cards(cards, mode=mode, participants=participants or [])

    def recommend_dialogue_scene_card(self, run_id: str, *, session_id: str) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        session = self.dialogue.get_session(run_id, session_id)
        cards = self.list_scene_cards()
        mode = str(session.get("mode", "") or session.get("session_card", {}).get("mode", "observe")).strip() or "observe"
        participants = list(session.get("session_card", {}).get("participants", []) or [])
        current_scene = dict(session.get("session_card", {}).get("scene_card", {}) or {})
        runtime_overview = dict(session.get("runtime_state_overview", {}) or {})
        current_scene_snapshot = _merge_current_scene_snapshot(current_scene, runtime_overview)
        current_scene_id = str(session.get("session_card", {}).get("scene_card_id", "")).strip()
        recent_text = "\n".join(
            str(item.get("message", "")).strip()
            for item in list(session.get("transcript", []) or [])[-6:]
            if str(item.get("message", "")).strip()
        )
        payload = recommend_scene_cards(cards, mode=mode, participants=participants)
        reranked_items: list[dict[str, Any]] = []
        for item in list(payload.get("items", []) or []):
            recommendation = dict(item.get("recommendation", {}) or {})
            score = int(recommendation.get("score", 0) or 0)
            reasons = [str(reason).strip() for reason in list(recommendation.get("reasons", []) or []) if str(reason).strip()]
            item_card_id = str(item.get("card_id", "")).strip()
            fields = dict(item.get("fields", {}) or {})

            if current_scene_id and item_card_id == current_scene_id:
                score -= 5
                reasons.insert(0, "当前已经在这幕里，优先换一拍")
            else:
                current_location = str(current_scene_snapshot.get("location", "")).strip()
                candidate_location = str(fields.get("location", "")).strip()
                if current_location and candidate_location and candidate_location != current_location:
                    score += 1
                    reasons.append("地点切换更明显，适合转场")

                overlap = _scene_text_overlap_score(fields, recent_text)
                if overlap:
                    score += overlap
                    reasons.append("和最近这几句的气口更接")

                state_bonus, state_reasons = _score_scene_card_with_runtime_state(
                    fields,
                    runtime_overview=runtime_overview,
                    current_scene=current_scene_snapshot,
                    participants=participants,
                    recent_text=recent_text,
                )
                score += state_bonus
                reasons.extend(state_reasons)

            reranked_items.append(
                {
                    **item,
                    "recommendation": {
                        "score": score,
                        "reasons": reasons[:4] or ["适合承接当前会话"],
                    },
                }
            )

        reranked_items.sort(
            key=lambda item: (
                int(item.get("recommendation", {}).get("score", 0) or 0),
                str(item.get("updated_at", "")),
                str(item.get("card_id", "")),
            ),
            reverse=True,
        )
        recommended_card_id = str(reranked_items[0].get("card_id", "")).strip() if reranked_items else ""
        top_fields = dict(reranked_items[0].get("fields", {}) or {}) if reranked_items else {}
        chain_suggestions = _build_scene_chain_suggestions(
            current_scene=current_scene_snapshot,
            current_scene_id=current_scene_id,
            reranked_items=reranked_items,
            recent_text=recent_text,
            runtime_overview=runtime_overview,
        )
        return {
            "mode": mode,
            "participants": participants,
            "current_scene_card_id": current_scene_id,
            "recommended_card_id": recommended_card_id,
            "recommended_transition_message": _build_transition_message_hint(
                current_scene=current_scene_snapshot,
                next_scene=top_fields,
                recent_text=recent_text,
                runtime_overview=runtime_overview,
            ),
            "chain_suggestions": chain_suggestions,
            "items": reranked_items,
        }


def _merge_current_scene_snapshot(current_scene: dict[str, Any], runtime_overview: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current_scene or {})
    if str(runtime_overview.get("location", "")).strip():
        merged["location"] = str(runtime_overview.get("location", "")).strip()
    if str(runtime_overview.get("time_hint", "")).strip():
        merged["time_hint"] = str(runtime_overview.get("time_hint", "")).strip()
    if str(runtime_overview.get("atmosphere", "")).strip():
        merged["atmosphere"] = str(runtime_overview.get("atmosphere", "")).strip()
    return merged


def _scene_text_overlap_score(fields: dict[str, Any], recent_text: str) -> int:
    compact_recent = str(recent_text or "").strip()
    if not compact_recent:
        return 0
    phrases: list[str] = []
    for key in ("location", "atmosphere", "opening_situation", "scene_drive", "public_goal", "hidden_tension"):
        raw = str(fields.get(key, "") or "").strip()
        if not raw:
            continue
        for part in re.split(r"[，,。；;、：:\s]+", raw):
            text = part.strip()
            if 2 <= len(text) <= 8 and text not in phrases:
                phrases.append(text)
    overlap = sum(1 for phrase in phrases[:12] if phrase in compact_recent)
    return min(3, overlap)


def _score_scene_card_with_runtime_state(
    fields: dict[str, Any],
    *,
    runtime_overview: dict[str, Any],
    current_scene: dict[str, Any],
    participants: list[str],
    recent_text: str,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    current_location = str(current_scene.get("location", "")).strip()
    candidate_location = str(fields.get("location", "")).strip()
    current_time = str(runtime_overview.get("time_hint", "") or current_scene.get("time_hint", "")).strip()
    candidate_time = str(fields.get("time_hint", "")).strip()
    beat_maturity = max(0, min(100, int(runtime_overview.get("beat_maturity", 0) or 0)))
    should_shift = bool(runtime_overview.get("should_offer_scene_shift", False))
    shift_reason = str(runtime_overview.get("scene_shift_reason", "")).strip()
    tension = str(runtime_overview.get("tension", "")).strip()
    next_hint = str(runtime_overview.get("next_hint", "")).strip()
    atmosphere = str(runtime_overview.get("atmosphere", "")).strip()
    event_rows = list(runtime_overview.get("event_rows", []) or [])
    recent_event = str((event_rows[-1] or {}).get("copy", "")).strip() if event_rows else ""

    if should_shift:
        if current_location and candidate_location and candidate_location != current_location:
            score += 4
            reasons.append("这一拍已接近收束，更适合换场推进")
        elif current_location and candidate_location and candidate_location == current_location:
            score -= 2
            reasons.append("这一拍已经该收住了，不必继续原地打转")
        elif candidate_location:
            score += 1
            reasons.append("当前已经适合往下一拍走")
    elif beat_maturity and beat_maturity < 45 and current_location and candidate_location == current_location:
        score += 2
        reasons.append("这一拍还没聊满，先在同场景续火更顺")

    if current_time and candidate_time:
        if candidate_time == current_time:
            score += 1
            reasons.append("时间承接自然")
        elif should_shift or beat_maturity >= 55:
            score += 2
            reasons.append("时间推进能带出下一拍")

    state_overlap = _state_overlap_score(
        fields,
        state_texts=[atmosphere, tension, next_hint, recent_event, recent_text],
    )
    if state_overlap:
        score += state_overlap
        reasons.append("能接住本局气氛和悬念")

    if len(participants) >= 3 and candidate_location and any(token in candidate_location for token in ("厅", "堂", "席", "园", "院")):
        score += 1
        reasons.append("多人局切到这个场面更容易铺开")

    if shift_reason:
        shift_tokens = [part for part in re.split(r"[，,。；;、：:\s]+", shift_reason) if 2 <= len(part.strip()) <= 8]
        if any(token and token in "\n".join(str(fields.get(key, "")).strip() for key in ("opening_situation", "scene_drive", "hidden_tension")) for token in shift_tokens[:4]):
            score += 2
            reasons.append("和当前这拍的收束理由接得上")

    return score, reasons


def _state_overlap_score(fields: dict[str, Any], *, state_texts: list[str]) -> int:
    compact_state = "\n".join(text.strip() for text in state_texts if str(text).strip())
    if not compact_state:
        return 0
    phrases: list[str] = []
    for key in ("atmosphere", "opening_situation", "public_goal", "hidden_tension", "scene_drive"):
        raw = str(fields.get(key, "")).strip()
        if not raw:
            continue
        for part in re.split(r"[，,。；;、：:\s]+", raw):
            text = part.strip()
            if 2 <= len(text) <= 8 and text not in phrases:
                phrases.append(text)
    overlap = sum(1 for phrase in phrases[:14] if phrase in compact_state)
    return min(4, overlap)


def _build_transition_message_hint(
    *,
    current_scene: dict[str, Any],
    next_scene: dict[str, Any],
    recent_text: str,
    runtime_overview: dict[str, Any] | None = None,
) -> str:
    runtime_overview = dict(runtime_overview or {})
    next_location = str(next_scene.get("location", "")).strip()
    next_title = str(next_scene.get("title", "")).strip()
    next_opening = str(next_scene.get("opening_situation", "")).strip()
    next_atmosphere = str(next_scene.get("atmosphere", "")).strip()
    current_location = str(current_scene.get("location", "")).strip()
    next_time = str(next_scene.get("time_hint", "")).strip()
    current_time = str(runtime_overview.get("time_hint", "") or current_scene.get("time_hint", "")).strip()
    shift_reason = str(runtime_overview.get("scene_shift_reason", "")).strip()
    tension = str(runtime_overview.get("tension", "")).strip()
    should_shift = bool(runtime_overview.get("should_offer_scene_shift", False))

    if shift_reason and should_shift and current_location and next_location and current_location != next_location:
        anchor = next_title or next_location
        return f"{shift_reason}，场面顺势从{current_location}转到{anchor}。"

    if next_time and current_time and next_time != current_time:
        destination = next_location or next_title or "下一幕"
        if tension:
            return f"带着这股{_trim_transition_text(tension, 18)}，时间已经推到{next_time}，场面也转进了{destination}。"
        return f"这一拍不知不觉拖到了{next_time}，场面也顺势转进了{destination}。"

    if next_opening:
        first_sentence = re.split(r"[。！？!?]", next_opening, maxsplit=1)[0].strip()
        if first_sentence:
            if not re.search(r"[。！？!?]$", first_sentence):
                first_sentence = f"{first_sentence}。"
            return first_sentence

    if current_location and next_location and current_location != next_location:
        anchor = next_title or next_location
        return f"局面一转，众人从{current_location}挪到{anchor}，气氛也跟着变了。"

    compact_recent = str(recent_text or "").strip()
    if tension and next_atmosphere:
        return f"刚才那股{_trim_transition_text(tension, 18)}还吊着，场面已经慢慢转成了{next_atmosphere}。"
    if compact_recent and next_atmosphere:
        return f"刚才那股{compact_recent[-12:]}的余波还没散，场面已经转成了{next_atmosphere}。"

    if next_location and next_atmosphere:
        return f"这一拍顺势转到{next_location}，场面也慢慢收成了{next_atmosphere}。"
    if next_location:
        return f"这一拍顺势转到{next_location}。"
    if next_title:
        return f"这一拍顺势转入「{next_title}」。"
    return ""


def _build_scene_chain_suggestions(
    *,
    current_scene: dict[str, Any],
    current_scene_id: str,
    reranked_items: list[dict[str, Any]],
    recent_text: str,
    runtime_overview: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    candidates = [
        item
        for item in reranked_items
        if str(item.get("card_id", "")).strip() and str(item.get("card_id", "")).strip() != current_scene_id
    ][:5]
    chains: list[dict[str, Any]] = []
    for first_index, first in enumerate(candidates):
        for second_index, second in enumerate(candidates):
            if second_index == first_index:
                continue
            chain_items = [first, second]
            chains.append(
                _build_chain_payload(
                    current_scene=current_scene,
                    items=chain_items,
                    recent_text=recent_text,
                    runtime_overview=runtime_overview,
                )
            )
            for third_index, third in enumerate(candidates):
                if third_index in {first_index, second_index}:
                    continue
                chains.append(
                    _build_chain_payload(
                        current_scene=current_scene,
                        items=[first, second, third],
                        recent_text=recent_text,
                        runtime_overview=runtime_overview,
                    )
                )
    chains.sort(key=lambda item: (int(item.get("score", 0) or 0), len(item.get("scenes", []) or [])), reverse=True)
    deduped: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for chain in chains:
        scene_ids = [str(scene.get("card_id", "")).strip() for scene in list(chain.get("scenes", []) or [])]
        key = "->".join(scene_ids)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(chain)
        if len(deduped) >= 3:
            break
    return deduped


def _build_chain_payload(
    *,
    current_scene: dict[str, Any],
    items: list[dict[str, Any]],
    recent_text: str,
    runtime_overview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenes: list[dict[str, str]] = []
    previous_scene = dict(current_scene or {})
    current_runtime = dict(runtime_overview or {})
    total_score = 0
    locations: list[str] = []
    for index, item in enumerate(items):
        fields = dict(item.get("fields", {}) or {})
        score = int(dict(item.get("recommendation", {}) or {}).get("score", 0) or 0)
        total_score += max(0, score) * max(1, 4 - index)
        location = str(fields.get("location", "")).strip()
        if location:
            locations.append(location)
        scenes.append(
            {
                "card_id": str(item.get("card_id", "")).strip(),
                "title": str(item.get("preview", {}).get("title", "") or fields.get("title", "")).strip(),
                "location": location,
                "atmosphere": str(fields.get("atmosphere", "")).strip(),
                "scene_drive": str(fields.get("scene_drive", "")).strip(),
                "transition_message": _build_transition_message_hint(
                    current_scene=previous_scene,
                    next_scene=fields,
                    recent_text=recent_text if index == 0 else str(previous_scene.get("scene_drive", "")).strip(),
                    runtime_overview=current_runtime if index == 0 else None,
                ),
            }
        )
        previous_scene = fields
        current_runtime = {}
    if len(set(locations)) >= 2:
        total_score += 4
    if _chain_has_progressive_drive(scenes):
        total_score += 3
    return {
        "chain_id": " -> ".join(scene.get("card_id", "") for scene in scenes),
        "score": total_score,
        "reason": _build_chain_reason(scenes),
        "scenes": scenes,
    }


def _chain_has_progressive_drive(scenes: list[dict[str, str]]) -> bool:
    drives = [str(scene.get("scene_drive", "")).strip() for scene in scenes if str(scene.get("scene_drive", "")).strip()]
    if len(drives) < 2:
        return False
    strong_tokens = ("试探", "转折", "摊牌", "揭", "逼", "变局", "收紧")
    hit_count = sum(1 for drive in drives if any(token in drive for token in strong_tokens))
    return hit_count >= 2


def _build_chain_reason(scenes: list[dict[str, str]]) -> str:
    if not scenes:
        return "这条线能顺着往下接。"
    locations = [scene.get("location", "") for scene in scenes if scene.get("location", "")]
    if len(scenes) >= 3 and len(set(locations)) >= 2:
        return "先换场再收紧，后面还有继续推进的余地。"
    if len(scenes) >= 2 and len(set(locations)) >= 2:
        return "地点会连续变化，戏路层次更明显。"
    if _chain_has_progressive_drive(scenes):
        return "每一幕的推进方向都比较明确，适合顺着往下压。"
    first_title = str(scenes[0].get("title", "")).strip() or "这条线"
    return f"可以先接「{first_title}」，后面还有顺势承接的下一拍。"


def _trim_transition_text(text: str, limit: int) -> str:
    compact = str(text or "").strip()
    if len(compact) <= limit:
        return compact
    return f"{compact[: max(1, limit - 1)]}…"
