from .dialogue import router as dialogue_router
from .runs import router as runs_router
from .self_cards import router as self_cards_router
from .settings import router as settings_router

ROUTERS = (
    settings_router,
    self_cards_router,
    runs_router,
    dialogue_router,
)

__all__ = ["ROUTERS", "dialogue_router", "runs_router", "self_cards_router", "settings_router"]
