from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.web.api.compat import model_to_dict
from src.web.api.deps import get_run_service
from src.web.api.schemas import SaveSelfCardRequest
from src.web.workflow import WebRunService

router = APIRouter()


@router.get("/api/web/self-cards")
def list_self_cards(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    return {"items": run_service.list_self_cards()}


@router.get("/api/web/self-cards/{card_id}")
def get_self_card(card_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.get_self_card(card_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc


@router.post("/api/web/self-cards")
def create_self_card(
    payload: SaveSelfCardRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.save_self_card(fields=model_to_dict(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/web/self-cards/{card_id}")
def update_self_card(
    card_id: str,
    payload: SaveSelfCardRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.save_self_card(card_id=card_id, fields=model_to_dict(payload))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/web/self-cards/{card_id}")
def delete_self_card(card_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, str]:
    try:
        return run_service.delete_self_card(card_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc


@router.post("/api/web/self-cards/generate")
def generate_self_card(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.generate_self_card()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
