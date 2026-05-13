from __future__ import annotations

import os
import threading
from pathlib import Path
from src.core.runtime_factory import build_runtime_parts
from src.web.chat import DialogueService
from src.web.review import (
    PERSONA_REVIEW_FIELDS,
    PROFILE_LIST_FIELDS,
    PROFILE_MAP_FIELDS,
)
from src.web.service_facades import (
    AutomaticPipelineMixin,
    ArtifactServiceMixin,
    CoreServiceMixin,
    DialogueServiceMixin,
    OpeningPresetServiceMixin,
    PipelineHelpersMixin,
    ReviewHelpersMixin,
    RunPreparationMixin,
    RuntimeSupportMixin,
    RunServiceMixin,
    SceneCardServiceMixin,
    SelfCardServiceMixin,
    UpdateServiceMixin,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RunStoppedError(Exception):
    """Raised when a running distill task is asked to stop."""


class WebRunService(
    AutomaticPipelineMixin,
    UpdateServiceMixin,
    RuntimeSupportMixin,
    CoreServiceMixin,
    RunPreparationMixin,
    RunServiceMixin,
    ArtifactServiceMixin,
    OpeningPresetServiceMixin,
    SceneCardServiceMixin,
    SelfCardServiceMixin,
    DialogueServiceMixin,
    ReviewHelpersMixin,
    PipelineHelpersMixin,
):
    DISTILL_CHUNK_TRIGGER_CHARS = 18_000
    DISTILL_CHUNK_TRIGGER_SENTENCES = 180
    DISTILL_CHUNK_MAX_CHARS = 9_000
    DISTILL_CHUNK_MAX_SENTENCES = 70
    RELATION_CHUNK_TRIGGER_CHARS = 9_000
    RELATION_CHUNK_TRIGGER_SENTENCES = 110
    RELATION_CHUNK_MAX_CHARS = 4_800
    RELATION_CHUNK_MAX_SENTENCES = 36
    PROFILE_REWRITE_FIELDS = (
        "worldview",
        "belief_anchor",
        "moral_bottom_line",
        "restraint_threshold",
        "stress_response",
        "speech_style",
        "cadence",
    )
    PROFILE_COMPLETION_FIELDS = (
        "gender",
        "age_stage",
        "appearance_feature",
        "habit_action",
        "soul_goal",
        "hidden_desire",
        "core_traits",
        "temperament_type",
        "preference_like",
        "dislike_hate",
        "values",
        "worldview",
        "belief_anchor",
        "moral_bottom_line",
        "restraint_threshold",
        "inner_conflict",
        "self_cognition",
        "private_self",
        "thinking_style",
        "cognitive_limits",
        "decision_rules",
        "reward_logic",
        "action_style",
        "fear_triggers",
        "stress_response",
        "emotion_model",
        "anger_style",
        "joy_style",
        "grievance_style",
        "speech_style",
        "typical_lines",
        "cadence",
        "signature_phrases",
        "sentence_openers",
        "connective_tokens",
        "sentence_endings",
        "forbidden_fillers",
    )
    PROFILE_COMPLETION_GROUPS = (
        (
            "Embodiment",
            (
                "gender",
                "age_stage",
                "appearance_feature",
                "habit_action",
                "preference_like",
                "dislike_hate",
            ),
        ),
        (
            "Inner Core",
            (
                "soul_goal",
                "hidden_desire",
                "core_traits",
                "temperament_type",
                "values",
                "worldview",
                "belief_anchor",
                "moral_bottom_line",
                "restraint_threshold",
            ),
        ),
        (
            "Decision Logic",
            (
                "inner_conflict",
                "self_cognition",
                "private_self",
                "thinking_style",
                "cognitive_limits",
                "decision_rules",
                "reward_logic",
                "action_style",
            ),
        ),
        (
            "Emotion And Stress",
            (
                "fear_triggers",
                "stress_response",
                "emotion_model",
                "anger_style",
                "joy_style",
                "grievance_style",
            ),
        ),
        (
            "Voice",
            (
                "speech_style",
                "typical_lines",
                "cadence",
                "signature_phrases",
                "sentence_openers",
                "connective_tokens",
                "sentence_endings",
                "forbidden_fillers",
            ),
        ),
    )
    PROFILE_LIST_FIELDS = PROFILE_LIST_FIELDS
    PROFILE_MAP_FIELDS = PROFILE_MAP_FIELDS
    RELATION_REWRITE_FIELDS = (
        "conflict_point",
        "typical_interaction",
        "relation_change",
        "hidden_attitude",
    )
    PERSONA_REVIEW_FIELDS = PERSONA_REVIEW_FIELDS
    DISTILL_SINGLE_MAX_TOKENS = 1800
    DISTILL_CHUNK_MAX_TOKENS = 1200
    DISTILL_MERGE_MAX_TOKENS = 1800
    RELATION_SINGLE_MAX_TOKENS = 1000
    RELATION_CHUNK_MAX_TOKENS = 800
    RELATION_MERGE_MAX_TOKENS = 1000
    PROFILE_REPAIR_MAX_TOKENS = 900
    PROFILE_COMPLETION_MAX_TOKENS = 1100
    PROFILE_COMPLETION_GROUP_LIMIT = 4
    RELATION_REPAIR_MAX_TOKENS = 1000
    STOPPED_ERROR_TYPE = RunStoppedError

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self.project_root = _project_root()
        env_storage_root = str(os.getenv("ZAOMENG_WEB_STORAGE_ROOT", "") or os.getenv("ZAOMENG_STORAGE_DIR", "")).strip()
        if storage_root:
            resolved_storage_root = Path(storage_root)
        elif env_storage_root:
            resolved_storage_root = Path(env_storage_root)
        else:
            resolved_storage_root = self.project_root / ".zaomeng-web"
        self.storage_root = resolved_storage_root
        self.runs_root = self.storage_root / "runs"
        self.scene_cards_root = self.storage_root / "scene-cards"
        self.self_cards_root = self.storage_root / "self-cards"
        self.opening_presets_root = self.storage_root / "opening-presets"
        self.settings_path = self.storage_root / "model_settings.json"
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.scene_cards_root.mkdir(parents=True, exist_ok=True)
        self.self_cards_root.mkdir(parents=True, exist_ok=True)
        self.opening_presets_root.mkdir(parents=True, exist_ok=True)
        self.dialogue = DialogueService(
            self.runs_root,
            memory_store_resolver=self._dialogue_memory_store_for_run,
        )
        self._active_run_threads: dict[str, threading.Thread] = {}
        self._run_manifest_locks_guard = threading.Lock()
        self._run_manifest_locks: dict[str, threading.RLock] = {}
        self._app_update_lock = threading.Lock()
        self._app_update_thread: threading.Thread | None = None
        self._app_update_state: dict[str, object] = {
            "supported": False,
            "status": "idle",
            "message": "",
            "error": "",
            "current_version": "",
            "remote_version": "",
            "update_available": False,
            "checked_at": "",
            "started_at": "",
            "completed_at": "",
            "reload_required": False,
            "launcher_path": "",
            "repo_slug": "",
            "repo_ref": "",
            "last_update_stdout": "",
        }
        self._launcher_path_hint = ""

    @staticmethod
    def _build_runtime_parts(config):
        return build_runtime_parts(config)
