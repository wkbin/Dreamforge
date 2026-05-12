from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.web.api.compat import model_to_dict
from src.web.api.deps import get_run_service
from src.web.api.schemas import RecommendSceneCardRequest, SaveSceneCardRequest
from src.web.workflow import WebRunService

router = APIRouter()


@router.get("/api/web/scene-cards")
def list_scene_cards(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    return {"items": run_service.list_scene_cards()}


@router.get("/api/web/scene-cards/{card_id}")
def get_scene_card(card_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.get_scene_card(card_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc


@router.post("/api/web/scene-cards")
def create_scene_card(
    payload: SaveSceneCardRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.save_scene_card(fields=model_to_dict(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/web/scene-cards/{card_id}")
def update_scene_card(
    card_id: str,
    payload: SaveSceneCardRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.save_scene_card(card_id=card_id, fields=model_to_dict(payload))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/web/scene-cards/{card_id}")
def delete_scene_card(card_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, str]:
    try:
        return run_service.delete_scene_card(card_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found.") from exc


@router.post("/api/web/scene-cards/generate")
def generate_scene_card(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.generate_scene_card()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/scene-cards/recommend")
def recommend_scene_cards(
    payload: RecommendSceneCardRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    return run_service.recommend_scene_cards(
        mode=payload.mode,
        participants=payload.participants,
    )
