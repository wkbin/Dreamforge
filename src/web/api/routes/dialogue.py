from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.web.api.compat import model_to_dict
from src.web.api.deps import get_run_service
from src.web.api.schemas import (
    BranchDialogueSessionRequest,
    CreateDialogueSessionRequest,
    IngestDialogueTurnRequest,
    PrepareDialogueTurnRequest,
    SuggestDialogueTurnRequest,
    SwitchDialogueSceneCardRequest,
)
from src.web.workflow import WebRunService

router = APIRouter()


@router.get("/api/web/runs/{run_id}/dialogue/sessions")
def list_dialogue_sessions(run_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return {"items": run_service.list_dialogue_sessions(run_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc


@router.post("/api/web/runs/{run_id}/dialogue/sessions")
def create_dialogue_session(
    run_id: str,
    payload: CreateDialogueSessionRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.create_dialogue_session(
            run_id,
            mode=payload.mode,
            participants=payload.participants,
            controlled_character=payload.controlled_character,
            scene_card_id=payload.scene_card_id,
            scene_profile=payload.scene_profile,
            self_card_id=payload.self_card_id,
            self_profile=payload.self_profile,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/web/runs/{run_id}/dialogue/sessions/{session_id}")
def get_dialogue_session(
    run_id: str,
    session_id: str,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.get_dialogue_session(run_id, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc


@router.post("/api/web/runs/{run_id}/dialogue/sessions/{session_id}/branch")
def branch_dialogue_session(
    run_id: str,
    session_id: str,
    payload: BranchDialogueSessionRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.branch_dialogue_session_from_scene(
            run_id,
            session_id=session_id,
            scene_index=payload.scene_index,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/web/runs/{run_id}/dialogue/sessions/{session_id}")
def delete_dialogue_session(
    run_id: str,
    session_id: str,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, str]:
    try:
        run_service.delete_dialogue_session(run_id, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    return {"status": "deleted"}


@router.post("/api/web/runs/{run_id}/dialogue/sessions/{session_id}/prepare")
def prepare_dialogue_turn(
    run_id: str,
    session_id: str,
    payload: PrepareDialogueTurnRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.prepare_dialogue_turn(
            run_id,
            session_id=session_id,
            message=payload.message,
            message_kind=payload.message_kind,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/dialogue/sessions/{session_id}/reply")
def reply_dialogue_turn(
    run_id: str,
    session_id: str,
    payload: PrepareDialogueTurnRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.reply_dialogue_turn(
            run_id,
            session_id=session_id,
            message=payload.message,
            message_kind=payload.message_kind,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/dialogue/sessions/{session_id}/suggest")
def suggest_dialogue_turn(
    run_id: str,
    session_id: str,
    payload: SuggestDialogueTurnRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, str]:
    try:
        return run_service.suggest_dialogue_turn(run_id, session_id=session_id, seed_text=payload.seed_text)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/web/runs/{run_id}/dialogue/sessions/{session_id}/scene-card")
def switch_dialogue_scene_card(
    run_id: str,
    session_id: str,
    payload: SwitchDialogueSceneCardRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.switch_dialogue_scene_card(
            run_id,
            session_id=session_id,
            scene_card_id=payload.scene_card_id,
            scene_profile=payload.scene_profile,
            transition_message=payload.transition_message,
            auto_continue=payload.auto_continue,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/dialogue/sessions/{session_id}/scene-card/recommend")
def recommend_dialogue_scene_card(
    run_id: str,
    session_id: str,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.recommend_dialogue_scene_card(run_id, session_id=session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/dialogue/sessions/{session_id}/ingest")
def ingest_dialogue_turn(
    run_id: str,
    session_id: str,
    payload: IngestDialogueTurnRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.ingest_dialogue_turn(
            run_id,
            session_id=session_id,
            responses=[model_to_dict(item) for item in payload.responses],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
