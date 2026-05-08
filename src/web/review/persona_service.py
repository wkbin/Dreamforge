from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


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
    apply_persona_review_updates(profile, fields)
    editable_path = write_persona_profile(persona_dir, profile)
    refreshed = discover_artifacts(manifest)
    refreshed["updated_at"] = utc_now()
    refreshed.setdefault("events", []).append(
        {
            "stage": "persona_review_saved",
            "status": "running",
            "message": f"{character} 的人物校对已保存",
            "character": character,
            "capability": "materialize",
            "timestamp": utc_now(),
        }
    )
    payload = get_persona_review(run_id, character)
    payload["editable_profile_path"] = str(editable_path.resolve())
    return {
        "manifest": refreshed,
        "payload": payload,
    }
