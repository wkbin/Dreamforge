from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _normalize_review_source(fields: dict[str, Any]) -> str:
    return str(fields.get("review_source", "") or "").strip()


def _normalize_review_note(fields: dict[str, Any]) -> str:
    return str(fields.get("review_note", "") or "").strip()


def _collect_changed_review_fields(
    *,
    previous_fields: dict[str, str],
    next_fields: dict[str, str],
    requested_fields: dict[str, Any],
) -> list[str]:
    changed: list[str] = []
    for field, next_value in next_fields.items():
        if field not in requested_fields:
            continue
        previous_value = str(previous_fields.get(field, "") or "").strip()
        current_value = str(next_value or "").strip()
        if previous_value != current_value:
            changed.append(field)
    return changed


def _build_persona_review_saved_event(
    *,
    character: str,
    review_source: str,
    review_note: str,
    changed_fields: list[str],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    is_autofill_save = review_source == "character_overview_autofill"
    return {
        "stage": "persona_review_saved",
        "status": "running",
        "message": f"{character} 的人物补全已写回" if is_autofill_save else f"{character} 的人物校对已保存",
        "character": character,
        "capability": "materialize",
        "timestamp": utc_now(),
        "review_source": review_source,
        "review_note": review_note,
        "changed_fields": list(changed_fields),
    }


def get_persona_review_payload(
    *,
    run_id: str,
    character: str,
    persona_dir: Path,
    resolve_persona_review_source: Callable[[Path], tuple[Path, Path, Path]],
    load_profile_source: Callable[[Path], dict[str, Any]],
    read_persona_review_fields: Callable[[dict[str, Any]], dict[str, str]],
) -> dict[str, Any]:
    editable_path, generated_path, source_path = resolve_persona_review_source(persona_dir)
    if not source_path.exists():
        raise FileNotFoundError(character)
    profile = load_profile_source(source_path)
    return {
        "run_id": run_id,
        "character": str(profile.get("name", "")).strip() or character,
        "persona_dir": str(persona_dir.resolve()),
        "editable_profile_path": str(editable_path.resolve()) if editable_path.exists() else "",
        "generated_profile_path": str(generated_path.resolve()) if generated_path.exists() else "",
        "fields": read_persona_review_fields(profile),
    }


def save_persona_review_payload(
    *,
    run_id: str,
    character: str,
    fields: dict[str, str],
    manifest: dict[str, Any],
    persona_dir: Path,
    resolve_persona_review_source: Callable[[Path], tuple[Path, Path, Path]],
    load_profile_source: Callable[[Path], dict[str, Any]],
    read_persona_review_fields: Callable[[dict[str, Any]], dict[str, str]],
    apply_persona_review_updates: Callable[[dict[str, Any], dict[str, str]], None],
    write_persona_profile: Callable[[Path, dict[str, Any]], Path],
    discover_artifacts: Callable[[dict[str, Any]], dict[str, Any]],
    get_persona_review: Callable[[str, str], dict[str, Any]],
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    editable_path, _, source_path = resolve_persona_review_source(persona_dir)
    if not source_path.exists():
        raise FileNotFoundError(character)
    profile = load_profile_source(source_path)
    previous_fields = read_persona_review_fields(profile)
    apply_persona_review_updates(profile, fields)
    next_fields = read_persona_review_fields(profile)
    review_source = _normalize_review_source(fields)
    review_note = _normalize_review_note(fields)
    changed_fields = _collect_changed_review_fields(
        previous_fields=previous_fields,
        next_fields=next_fields,
        requested_fields=fields,
    )
    editable_path = write_persona_profile(persona_dir, profile)
    refreshed = discover_artifacts(manifest)
    refreshed["updated_at"] = utc_now()
    refreshed.setdefault("events", []).append(
        _build_persona_review_saved_event(
            character=character,
            review_source=review_source,
            review_note=review_note,
            changed_fields=changed_fields,
            utc_now=utc_now,
        )
    )
    payload = get_persona_review(run_id, character)
    payload["editable_profile_path"] = str(editable_path.resolve())
    return {
        "manifest": refreshed,
        "payload": payload,
    }
