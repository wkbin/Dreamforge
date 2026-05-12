from .dialogue import router as dialogue_router
from .opening_presets import router as opening_presets_router
from .runs import router as runs_router
from .scene_cards import router as scene_cards_router
from .self_cards import router as self_cards_router
from .settings import router as settings_router

ROUTERS = (
    settings_router,
    opening_presets_router,
    scene_cards_router,
    self_cards_router,
    runs_router,
    dialogue_router,
)

__all__ = [
    "ROUTERS",
    "dialogue_router",
    "opening_presets_router",
    "runs_router",
    "scene_cards_router",
    "self_cards_router",
    "settings_router",
]
