from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.web.api import (
    ROUTERS,
)
from src.web.workflow import WebRunService


def create_app(service: WebRunService | None = None) -> FastAPI:
    app = FastAPI(title="zaomeng webui", version="0.1.0")
    app.state.run_service = service or WebRunService()
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/web", StaticFiles(directory=static_dir, html=True), name="web")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    for router in ROUTERS:
        app.include_router(router)

    return app


app = create_app()
