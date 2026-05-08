from __future__ import annotations

from typing import Any, Callable


def build_model_settings_response(
    payload: dict[str, Any],
    *,
    configured: bool,
) -> dict[str, Any]:
    provider = str(payload.get("provider", "")).strip()
    model = str(payload.get("model", "")).strip()
    base_url = str(payload.get("base_url", "")).strip()
    api_key = str(payload.get("api_key", "")).strip()
    max_tokens = int(payload.get("max_tokens", 0) or 0)
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "max_tokens": max_tokens,
        "api_key_configured": bool(api_key),
        "configured": configured,
    }


def normalize_model_settings(
    *,
    existing: dict[str, Any],
    provider: str,
    model: str,
    base_url: str = "",
    api_key: str = "",
    max_tokens: int = 0,
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    normalized_api_key = str(api_key or "").strip() or str(existing.get("api_key", "")).strip()
    normalized = {
        "provider": str(provider or "").strip(),
        "model": str(model or "").strip(),
        "base_url": str(base_url or "").strip(),
        "api_key": normalized_api_key,
        "max_tokens": max(0, int(max_tokens or 0)),
        "updated_at": utc_now(),
    }
    validate_model_settings(normalized)
    return normalized


def validate_model_settings(payload: dict[str, Any]) -> None:
    if not str(payload.get("provider", "")).strip():
        raise ValueError("Model provider is required.")
    if not str(payload.get("model", "")).strip():
        raise ValueError("Model name is required.")
    if str(payload.get("provider", "")).strip() != "ollama" and not str(payload.get("api_key", "")).strip():
        raise ValueError("API key is required for the selected provider.")
