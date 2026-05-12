from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.web.api.compat import model_to_dict
from src.web.api.deps import get_run_service
from src.web.api.schemas import SaveOpeningPresetRequest
from src.web.workflow import WebRunService

router = APIRouter()


@router.get("/api/web/opening-presets")
def list_opening_presets(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    return {"items": run_service.list_opening_presets()}


@router.get("/api/web/opening-presets/{card_id}")
def get_opening_preset(card_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.get_opening_preset(card_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc


@router.post("/api/web/opening-presets")
def create_opening_preset(
    payload: SaveOpeningPresetRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.save_opening_preset(fields=model_to_dict(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/web/opening-presets/{card_id}")
def update_opening_preset(
    card_id: str,
    payload: SaveOpeningPresetRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.save_opening_preset(card_id=card_id, fields=model_to_dict(payload))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/web/opening-presets/{card_id}")
def delete_opening_preset(card_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, str]:
    try:
        return run_service.delete_opening_preset(card_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc
