from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from src.core.config import Config


def build_runtime_config_for_run(
    *,
    run_dir: Path,
    project_root: Path,
    model_payload: dict[str, Any],
) -> Config:
    config = Config()
    config.update(
        {
            "llm": {
                "provider": str(model_payload.get("provider", "")).strip(),
                "model": str(model_payload.get("model", "")).strip(),
                "base_url": str(model_payload.get("base_url", "")).strip(),
                "api_key": str(model_payload.get("api_key", "")).strip(),
                "max_tokens": int(model_payload.get("max_tokens", 0) or 0),
                "timeout_seconds": 90,
                "parallel_chunk_workers": 6,
                "retry_attempts": 2,
                "retry_backoff_seconds": 0.75,
            },
            "paths": {
                "characters": str((run_dir / "artifacts" / "characters").resolve()),
                "relations": str((run_dir / "artifacts" / "relations").resolve()),
                "sessions": str((run_dir / "dialogue").resolve()),
                "corrections": str((run_dir / "corrections").resolve()),
                "logs": str((run_dir / "logs").resolve()),
                "rules": str((project_root / "rules").resolve()),
            },
        }
    )
    return config


def build_novel_source_entry(
    source_path: Path,
    *,
    source_name: str,
    kind: str,
    raw_bytes: bytes | None = None,
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    content_bytes = raw_bytes if raw_bytes is not None else source_path.read_bytes()
    return {
        "source_path": str(source_path.resolve()),
        "source_name": str(source_name or source_path.name).strip() or source_path.name,
        "kind": kind,
        "timestamp": utc_now(),
        "byte_size": len(content_bytes),
        "char_count": estimate_text_length(content_bytes),
    }


def estimate_text_length(raw_bytes: bytes) -> int:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return len(raw_bytes.decode(encoding))
        except UnicodeDecodeError:
            continue
    return len(raw_bytes.decode("utf-8", errors="replace"))


def is_model_configured_payload(payload: dict[str, Any]) -> bool:
    provider = str(payload.get("provider", "")).strip()
    model = str(payload.get("model", "")).strip()
    api_key = str(payload.get("api_key", "")).strip()
    if not provider or not model:
        return False
    if provider == "ollama":
        return True
    return bool(api_key)
