from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.web.api.deps import get_run_service
from src.web.api.schemas import SaveModelSettingsRequest
from src.web.workflow import WebRunService

router = APIRouter()


@router.get("/api/web/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/web/settings/model")
def get_model_settings(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    return run_service.get_model_settings()


@router.put("/api/web/settings/model")
def save_model_settings(
    payload: SaveModelSettingsRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.save_model_settings(
            provider=payload.provider,
            model=payload.model,
            base_url=payload.base_url,
            api_key=payload.api_key,
            max_tokens=payload.max_tokens,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
