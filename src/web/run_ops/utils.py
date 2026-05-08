from __future__ import annotations

import base64
from uuid import uuid4


def normalize_characters(characters: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in characters:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        ordered.append(name)
        seen.add(name)
    return ordered


def decode_base64_text(value: str) -> bytes:
    try:
        return base64.b64decode(str(value or ""), validate=True)
    except Exception as exc:  # pragma: no cover - exact decoder error is not important
        raise ValueError("Novel content is not valid base64.") from exc


def new_run_id() -> str:
    return f"run-{uuid4().hex[:12]}"
