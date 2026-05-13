from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from src.web.api.compat import model_to_dict
from src.web.api.deps import get_run_service
from src.web.api.schemas import (
    CreateRunRequest,
    ImportRunPackageRequest,
    IngestCharacterRequest,
    IngestRelationRequest,
    RestartRunRequest,
    SavePersonaReviewRequest,
    SuggestRedistillSegmentsRequest,
    SuggestPersonaFieldRequest,
    UpdateRelationDetailRequest,
)
from src.web.workflow import WebRunService

router = APIRouter()


@router.get("/api/web/builtin-novels")
def list_builtin_novels(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    return {"items": run_service.list_builtin_novels()}


@router.post("/api/web/builtin-novels/{package_id}/clone")
def clone_builtin_novel(package_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.clone_builtin_novel(package_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Built-in novel not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/web/runs")
def list_runs(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    return {"items": run_service.list_runs()}


@router.get("/api/web/sessions")
def list_recent_sessions(run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    return {"items": run_service.list_recent_sessions()}


@router.post("/api/web/runs")
def create_run_route(
    payload: CreateRunRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.create_run(
            novel_name=payload.novel_name,
            novel_content_base64=payload.novel_content_base64,
            characters=payload.characters,
            max_sentences=payload.max_sentences,
            max_chars=payload.max_chars,
            auto_run=payload.auto_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/import")
def import_run_package_route(
    payload: ImportRunPackageRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.import_run_package(
            filename=payload.filename,
            content_base64=payload.content_base64,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Package not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/web/runs/{run_id}")
def get_run(run_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.get_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc


@router.get("/api/web/runs/{run_id}/export")
def export_run_package_route(
    run_id: str,
    builtin: bool = False,
    run_service: WebRunService = Depends(get_run_service),
) -> FileResponse:
    try:
        exported = run_service.export_run_package(run_id, builtin=builtin)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(
        exported["path"],
        media_type="application/zip",
        filename=str(exported.get("filename", "")).strip() or None,
    )


@router.post("/api/web/runs/{run_id}/publish-builtin")
def publish_run_as_builtin_route(
    run_id: str,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.publish_run_as_builtin(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/web/runs/{run_id}")
def delete_run(run_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.delete_run_group(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/stop")
def stop_run(run_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.stop_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/redistill")
def redistill_run(
    run_id: str,
    payload: RestartRunRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.restart_run_distill(
            run_id,
            characters=payload.characters,
            novel_name=payload.novel_name,
            novel_content_base64=payload.novel_content_base64,
            max_sentences=payload.max_sentences,
            max_chars=payload.max_chars,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/redistill/recommend")
def suggest_redistill_segments(
    run_id: str,
    payload: SuggestRedistillSegmentsRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.suggest_redistill_segments(
            run_id,
            character=payload.character,
            max_segments=payload.max_segments,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run or source not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/refresh")
def refresh_run(run_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.refresh_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc


@router.get("/api/web/runs/{run_id}/personas/{character}")
def get_persona_review(
    run_id: str,
    character: str,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.get_persona_review(run_id, character)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Character not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/web/runs/{run_id}/personas/{character}")
def save_persona_review(
    run_id: str,
    character: str,
    payload: SavePersonaReviewRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.save_persona_review(run_id, character, model_to_dict(payload))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Character not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/personas/{character}/suggest-field")
def suggest_persona_field(
    run_id: str,
    character: str,
    payload: SuggestPersonaFieldRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.suggest_persona_field(run_id, character, payload.field)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Character not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/web/runs/{run_id}/relations")
def list_relation_details(run_id: str, run_service: WebRunService = Depends(get_run_service)) -> dict[str, Any]:
    try:
        return run_service.list_relation_details(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Relation graph not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/api/web/runs/{run_id}/relations/{pair_key}")
def update_relation_details(
    run_id: str,
    pair_key: str,
    payload: UpdateRelationDetailRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.update_relation_detail(run_id, pair_key, model_to_dict(payload))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Relation pair not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/ingest/character")
def ingest_character(
    run_id: str,
    payload: IngestCharacterRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.ingest_character_result(
            run_id,
            character=payload.character,
            content_base64=payload.content_base64,
            filename=payload.filename,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/runs/{run_id}/ingest/relation")
def ingest_relation(
    run_id: str,
    payload: IngestRelationRequest,
    run_service: WebRunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return run_service.ingest_relation_result(
            run_id,
            content_base64=payload.content_base64,
            filename=payload.filename,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/web/runs/{run_id}/files/{relative_path:path}")
def get_run_file(
    run_id: str,
    relative_path: str,
    run_service: WebRunService = Depends(get_run_service),
) -> FileResponse:
    try:
        file_path = run_service.resolve_run_file(run_id, relative_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(file_path)
