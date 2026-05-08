from __future__ import annotations

from fastapi import Request

from src.web.workflow import WebRunService


def get_run_service(request: Request) -> WebRunService:
    return request.app.state.run_service
