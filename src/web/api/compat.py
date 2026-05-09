from __future__ import annotations

from typing import Any


def model_to_dict(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return dict(payload.model_dump())
    if hasattr(payload, "dict"):
        return dict(payload.dict())
    raise TypeError("Payload object does not support model serialization.")
