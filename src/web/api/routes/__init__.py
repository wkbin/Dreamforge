from .dialogue import router as dialogue_router
from .runs import router as runs_router
from .settings import router as settings_router

ROUTERS = (
    settings_router,
    runs_router,
    dialogue_router,
)

__all__ = ["ROUTERS", "dialogue_router", "runs_router", "settings_router"]
