from __future__ import annotations

import base64
import concurrent.futures
import json
import logging
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.skill_support.prompt_payloads import build_distill_prompt_payload, build_relation_prompt_payload
from src.core.config import Config
from src.core.exceptions import LLMRequestError
from src.core.runtime_factory import build_runtime_parts
from src.utils.file_utils import safe_filename
from src.utils.text_parser import split_sentences
from src.web.dialogue import DialogueService
from src.web.host_ingest import (
    decode_text_content,
    export_relations_source,
    load_relations_source,
    load_persona_bundle,
    load_profile_source,
    materialize_profile_source,
    render_profile_md,
    write_persona_profile,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


logger = logging.getLogger(__name__)


class RunStoppedError(Exception):
    """Raised when a running distill task is asked to stop."""


class WebRunService:
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
        "faction_position",
        "story_role",
        "stance_stability",
        "identity_anchor",
        "world_rule_fit",
        "background_imprint",
        "life_experience",
        "trauma_scar",
        "taboo_topics",
        "forbidden_behaviors",
        "world_belong",
        "rule_view",
        "plot_restriction",
        "soul_goal",
        "hidden_desire",
        "core_traits",
        "temperament_type",
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
        "social_mode",
        "carry_style",
        "others_impression",
        "key_bonds",
        "appearance_feature",
        "habit_action",
        "preference_like",
        "dislike_hate",
        "interest_claim",
        "resource_dependence",
        "trade_principle",
        "disguise_switch",
        "ooc_redline",
        "speech_style",
        "typical_lines",
        "cadence",
        "signature_phrases",
        "sentence_openers",
        "connective_tokens",
        "sentence_endings",
        "forbidden_fillers",
        "strengths",
        "weaknesses",
        "arc_start",
        "arc_mid",
        "arc_end",
        "arc_type",
        "arc_blocker",
        "arc_summary",
    )
    PROFILE_COMPLETION_GROUPS = (
        (
            "基础与根源",
            (
                "faction_position",
                "story_role",
                "stance_stability",
                "identity_anchor",
                "world_rule_fit",
                "background_imprint",
                "life_experience",
                "trauma_scar",
                "taboo_topics",
                "forbidden_behaviors",
                "world_belong",
                "rule_view",
                "plot_restriction",
            ),
        ),
        (
            "精神内核",
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
            "冲突与决策",
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
            "情绪与社交",
            (
                "fear_triggers",
                "stress_response",
                "emotion_model",
                "anger_style",
                "joy_style",
                "grievance_style",
                "social_mode",
                "carry_style",
                "others_impression",
                "key_bonds",
            ),
        ),
        (
            "外显与资源",
            (
                "appearance_feature",
                "habit_action",
                "preference_like",
                "dislike_hate",
                "interest_claim",
                "resource_dependence",
                "trade_principle",
                "disguise_switch",
                "ooc_redline",
                "strengths",
                "weaknesses",
            ),
        ),
        (
            "语言与弧光",
            (
                "speech_style",
                "typical_lines",
                "cadence",
                "signature_phrases",
                "sentence_openers",
                "connective_tokens",
                "sentence_endings",
                "forbidden_fillers",
                "arc_start",
                "arc_mid",
                "arc_end",
                "arc_type",
                "arc_blocker",
                "arc_summary",
            ),
        ),
    )
    PROFILE_LIST_FIELDS = {
        "role_tags",
        "life_experience",
        "taboo_topics",
        "forbidden_behaviors",
        "core_traits",
        "fear_triggers",
        "key_bonds",
        "preference_like",
        "dislike_hate",
        "decision_rules",
        "typical_lines",
        "strengths",
        "weaknesses",
        "signature_phrases",
        "sentence_openers",
        "connective_tokens",
        "sentence_endings",
        "forbidden_fillers",
        "cognitive_limits",
    }
    PROFILE_MAP_FIELDS = {"values", "arc_start", "arc_mid", "arc_end"}
    RELATION_REWRITE_FIELDS = (
        "conflict_point",
        "typical_interaction",
        "relation_change",
        "hidden_attitude",
    )
    PERSONA_REVIEW_FIELDS = (
        "core_identity",
        "story_role",
        "soul_goal",
        "speech_style",
        "social_mode",
        "worldview",
        "belief_anchor",
        "moral_bottom_line",
        "restraint_threshold",
        "stress_response",
        "others_impression",
    )
    DISTILL_SINGLE_MAX_TOKENS = 1200
    DISTILL_CHUNK_MAX_TOKENS = 900
    DISTILL_MERGE_MAX_TOKENS = 1200
    RELATION_SINGLE_MAX_TOKENS = 1000
    RELATION_CHUNK_MAX_TOKENS = 800
    RELATION_MERGE_MAX_TOKENS = 1000
    PROFILE_REPAIR_MAX_TOKENS = 900
    PROFILE_COMPLETION_MAX_TOKENS = 700
    PROFILE_COMPLETION_GROUP_LIMIT = 3
    RELATION_REPAIR_MAX_TOKENS = 1000

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self.project_root = _project_root()
        self.storage_root = Path(storage_root) if storage_root else self.project_root / ".zaomeng-web"
        self.runs_root = self.storage_root / "runs"
        self.settings_path = self.storage_root / "model_settings.json"
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.dialogue = DialogueService(self.runs_root)
        self._active_run_threads: dict[str, threading.Thread] = {}

    def get_model_settings(self) -> dict[str, Any]:
        payload = self._load_model_settings_payload()
        provider = str(payload.get("provider", "")).strip()
        model = str(payload.get("model", "")).strip()
        base_url = str(payload.get("base_url", "")).strip()
        api_key = str(payload.get("api_key", "")).strip()
        max_tokens = int(payload.get("max_tokens", 0) or 0)
        return {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "max_tokens": max_tokens,
            "api_key_configured": bool(api_key),
            "configured": self._is_model_configured_payload(payload),
        }

    def save_model_settings(
        self,
        *,
        provider: str,
        model: str,
        base_url: str = "",
        api_key: str = "",
        max_tokens: int = 0,
    ) -> dict[str, Any]:
        existing = self._load_model_settings_payload()
        normalized_api_key = str(api_key or "").strip() or str(existing.get("api_key", "")).strip()
        normalized = {
            "provider": str(provider or "").strip(),
            "model": str(model or "").strip(),
            "base_url": str(base_url or "").strip(),
            "api_key": normalized_api_key,
            "max_tokens": max(0, int(max_tokens or 0)),
            "updated_at": _utc_now(),
        }
        if not normalized["provider"]:
            raise ValueError("Model provider is required.")
        if not normalized["model"]:
            raise ValueError("Model name is required.")
        if normalized["provider"] != "ollama" and not normalized["api_key"]:
            raise ValueError("API key is required for the selected provider.")
        self._write_json(self.settings_path, normalized)
        return self.get_model_settings()

    def model_is_configured(self) -> bool:
        return self._is_model_configured_payload(self._load_model_settings_payload())

    def list_runs(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for manifest_path in sorted(self.runs_root.glob("*/run_manifest.json"), reverse=True):
            payload = self._load_manifest(manifest_path)
            if payload:
                items.append(self._serialize_manifest(payload))
        items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return items

    def list_recent_sessions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for manifest_path in sorted(self.runs_root.glob("*/run_manifest.json"), reverse=True):
            manifest = self._load_manifest(manifest_path)
            if not manifest:
                continue
            run_id = str(manifest.get("run_id", "")).strip()
            novel_id = str(manifest.get("novel_id", "")).strip()
            if not run_id:
                continue
            for session in self.dialogue.list_sessions(run_id):
                session["novel_id"] = novel_id
                items.append(session)
        items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return items

    def get_run(self, run_id: str) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        payload = self._load_manifest(manifest_path)
        if not payload:
            raise FileNotFoundError(run_id)
        return self._serialize_manifest(payload)

    def refresh_run(self, run_id: str) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)
        refreshed = self._discover_artifacts(manifest)
        refreshed["updated_at"] = _utc_now()
        self._write_json(manifest_path, refreshed)
        return self._serialize_manifest(refreshed)

    def stop_run(self, run_id: str) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)

        status = str(manifest.get("status", "")).strip()
        if status != "running":
            raise ValueError("只有正在蒸馏的书卷才能停止。")

        control = manifest.setdefault("control", {})
        if bool(control.get("stop_requested", False)):
            return self._serialize_manifest(manifest)

        now_text = _utc_now()
        control["stop_requested"] = True
        control["stop_requested_at"] = now_text
        progress = manifest.setdefault("progress", {})
        progress["message"] = "已收到停止请求，正在收束当前步骤"
        summary = manifest.setdefault("summary", {})
        summary["status_text"] = "stop_requested"
        manifest["updated_at"] = now_text
        manifest.setdefault("events", []).append(
            {
                "stage": "stop_requested",
                "status": "running",
                "message": "已收到停止请求，正在收束当前步骤",
                "character": str(progress.get("current_character", "")).strip(),
                "capability": "verify_workflow",
                "timestamp": now_text,
            }
        )
        self._write_json(manifest_path, manifest)
        return self._serialize_manifest(manifest)

    def delete_run_group(self, run_id: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        target_novel_id = str(manifest.get("novel_id", "")).strip()
        if not target_novel_id:
            raise ValueError("Run is missing novel_id.")

        targets: list[Path] = []
        deleted_run_ids: list[str] = []
        deleted_sessions = 0
        blocked_runs: list[str] = []
        for manifest_path in sorted(self.runs_root.glob("*/run_manifest.json")):
            payload = self._load_manifest(manifest_path)
            if not payload:
                continue
            if str(payload.get("novel_id", "")).strip() != target_novel_id:
                continue
            if str(payload.get("status", "")).strip() == "running":
                blocked_runs.append(str(payload.get("run_id", "")).strip() or manifest_path.parent.name)
                continue
            targets.append(manifest_path.parent)

        if blocked_runs:
            raise ValueError("这本书还在整理中，暂时不能删除。请等这一轮结束后再删。")
        if not targets:
            raise FileNotFoundError(run_id)

        for run_dir in targets:
            manifest_path = run_dir / "run_manifest.json"
            payload = self._load_manifest(manifest_path) or {}
            deleted_run_ids.append(str(payload.get("run_id", "")).strip() or run_dir.name)
            dialogue_dir = run_dir / "dialogue"
            if dialogue_dir.exists():
                deleted_sessions += len([path for path in dialogue_dir.iterdir() if path.is_dir()])
            shutil.rmtree(run_dir, ignore_errors=False)

        return {
            "status": "deleted",
            "novel_id": target_novel_id,
            "deleted_run_count": len(deleted_run_ids),
            "deleted_session_count": deleted_sessions,
            "deleted_run_ids": deleted_run_ids,
        }

    def create_run(
        self,
        *,
        novel_name: str,
        novel_content_base64: str,
        characters: list[str],
        max_sentences: int = 120,
        max_chars: int = 50_000,
        auto_run: bool = False,
    ) -> dict[str, Any]:
        if not self.model_is_configured():
            raise ValueError("Model is not configured yet.")
        locked_characters = self._normalize_characters(characters)
        if not locked_characters:
            raise ValueError("At least one character is required.")

        file_name = safe_filename(novel_name or "novel.txt")
        raw_bytes = self._decode_base64(novel_content_base64)
        if not raw_bytes:
            raise ValueError("Novel content is empty.")

        run_id = self._new_run_id()
        run_dir = self.runs_root / run_id
        input_dir = run_dir / "input"
        payload_dir = run_dir / "payloads"
        artifact_dir = run_dir / "artifacts"
        for directory in (input_dir, payload_dir, artifact_dir):
            directory.mkdir(parents=True, exist_ok=True)

        novel_path = input_dir / file_name
        novel_path.write_bytes(raw_bytes)
        novel_id = Path(file_name).stem.strip() or run_id

        manifest = {
            "kind": "zaomeng_web_run",
            "schema_version": 1,
            "run_id": run_id,
            "novel_id": novel_id,
            "novel_path": str(novel_path.resolve()),
            "novel_sources": [
                self._build_novel_source_entry(
                    novel_path,
                    source_name=file_name,
                    kind="initial",
                    raw_bytes=raw_bytes,
                )
            ],
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "status": "running",
            "success": False,
            "entrypoint": "webui",
            "timing": {
                "started_at": _utc_now(),
                "completed_at": "",
                "failed_at": "",
                "stopped_at": "",
                "elapsed_seconds": 0.0,
                "elapsed_text": "",
            },
            "model_settings": self.get_model_settings(),
            "locked_characters": locked_characters,
            "progress": {
                "stage": "characters_locked",
                "message": "已锁定待蒸馏角色",
                "current_character": "",
                "completed_characters": [],
                "total_characters": len(locked_characters),
                "completed_count": 0,
                "graph_status": "pending",
                "chunking": {},
            },
            "capabilities": {
                "distill": {"status": "preparing", "success": False, "updated_at": _utc_now()},
                "materialize": {"status": "pending", "success": False, "updated_at": _utc_now()},
                "export_graph": {"status": "preparing", "success": False, "updated_at": _utc_now()},
                "verify_workflow": {"status": "pending", "success": False, "updated_at": _utc_now()},
            },
            "artifacts": {
                "payloads": {},
                "status_files": {},
                "character_dirs": {},
                "relation_graph": {},
                "chunking": {},
            },
            "summary": {
                "characters_total": len(locked_characters),
                "characters_completed": 0,
                "graph_status": "pending",
                "status_text": "waiting_for_payloads",
                "chunking": {},
            },
            "quality": {
                "excerpt_focus": {
                    "matched_characters": [],
                    "missing_characters": [],
                    "strategy": "",
                },
                "stage_presence": [],
                "character_focus": {},
                "profile_repairs": {"count": 0, "characters": []},
                "relation_repairs": {"count": 0, "pairs": []},
            },
            "events": [
                {
                    "stage": "characters_locked",
                    "status": "running",
                    "message": "已锁定待蒸馏角色",
                    "character": "",
                    "capability": "distill",
                    "timestamp": _utc_now(),
                }
            ],
            "control": {
                "stop_requested": False,
                "stop_requested_at": "",
                "stop_acknowledged_at": "",
            },
            "webui": {
                "run_dir": str(run_dir.resolve()),
                "input_dir": str(input_dir.resolve()),
                "payload_dir": str(payload_dir.resolve()),
                "artifact_dir": str(artifact_dir.resolve()),
            },
        }

        manifest_path = self._manifest_path(run_id)
        self._write_json(manifest_path, manifest)

        characters_root = artifact_dir / "characters" / novel_id
        manifest["webui"]["workspace"] = {
            "characters_root": str(characters_root.resolve()),
            "relations_root": str((artifact_dir / "relations").resolve()),
        }

        if auto_run:
            self._write_json(manifest_path, manifest)
            self._start_background_run(
                manifest_path=manifest_path,
                novel_path=novel_path,
                locked_characters=locked_characters,
                max_sentences=max_sentences,
                max_chars=max_chars,
            )
            return self._serialize_manifest(self._load_manifest(manifest_path) or manifest)

        distill_payload = build_distill_prompt_payload(
            novel_path,
            characters=locked_characters,
            max_sentences=max_sentences,
            max_chars=max_chars,
            characters_root=characters_root,
            manifest_path=manifest_path,
            update_mode="auto",
        )
        relation_payload = build_relation_prompt_payload(
            novel_path,
            max_sentences=min(max_sentences, 80),
            max_chars=min(max_chars, 12_000),
        )

        distill_payload_path = payload_dir / "distill_payload.json"
        relation_payload_path = payload_dir / "relation_payload.json"
        self._write_json(distill_payload_path, distill_payload)
        self._write_json(relation_payload_path, relation_payload)

        manifest["progress"]["stage"] = "relation_payload_ready"
        manifest["progress"]["message"] = "蒸馏与关系提取 payload 已准备完成"
        manifest["updated_at"] = _utc_now()
        manifest["summary"]["status_text"] = "waiting_for_host_generation"
        manifest["capabilities"]["distill"] = {
            "status": "ready",
            "success": False,
            "updated_at": _utc_now(),
            "message": "distill payload ready",
        }
        manifest["capabilities"]["export_graph"] = {
            "status": "ready",
            "success": False,
            "updated_at": _utc_now(),
            "message": "relation payload ready",
        }
        manifest["artifacts"]["payloads"] = {
            "distill": str(distill_payload_path.resolve()),
            "relation": str(relation_payload_path.resolve()),
        }
        manifest["artifacts"]["chunking"] = {
            "distill": self._chunk_overview_from_payload(distill_payload),
            "relation": self._chunk_overview_from_payload(relation_payload),
        }
        manifest["progress"]["chunking"] = self._build_progress_chunking_from_artifacts(manifest["artifacts"]["chunking"])
        manifest["summary"]["chunking"] = self._build_summary_chunking(manifest["progress"]["chunking"])
        manifest["excerpt_focus"] = {
            "matched_characters": distill_payload.get("request", {}).get("excerpt_focus", {}).get("matched_characters", []),
            "missing_characters": distill_payload.get("request", {}).get("excerpt_focus", {}).get("missing_characters", []),
            "strategy": distill_payload.get("request", {}).get("excerpt_focus", {}).get("strategy", ""),
        }
        manifest["quality"] = self._build_quality_snapshot(
            matched_characters=distill_payload.get("request", {}).get("excerpt_focus", {}).get("matched_characters", []),
            missing_characters=distill_payload.get("request", {}).get("excerpt_focus", {}).get("missing_characters", []),
            strategy=distill_payload.get("request", {}).get("excerpt_focus", {}).get("strategy", ""),
            excerpt_stages=distill_payload.get("request", {}).get("excerpt_stages", {}),
            character_focus={
                name: {
                    "matched": name in distill_payload.get("request", {}).get("excerpt_focus", {}).get("matched_characters", []),
                    "missing": name in distill_payload.get("request", {}).get("excerpt_focus", {}).get("missing_characters", []),
                    "stage_presence": self._stage_presence(
                        distill_payload.get("request", {}).get("excerpt_stages", {})
                    ),
                }
                for name in locked_characters
            },
        )
        manifest["events"].append(
            {
                "stage": "distill_payload_ready",
                "status": "running",
                "message": "蒸馏 payload 已生成，等待宿主 LLM 执行",
                "character": "",
                "capability": "distill",
                "timestamp": _utc_now(),
            }
        )
        manifest["events"].append(
            {
                "stage": "relation_payload_ready",
                "status": "running",
                "message": "关系图谱 payload 已生成，等待宿主 LLM 执行",
                "character": "",
                "capability": "export_graph",
                "timestamp": _utc_now(),
            }
        )
        self._write_json(manifest_path, manifest)
        return self._serialize_manifest(manifest)

    def restart_run_distill(
        self,
        run_id: str,
        *,
        characters: list[str],
        novel_name: str = "",
        novel_content_base64: str = "",
        max_sentences: int = 120,
        max_chars: int = 50_000,
    ) -> dict[str, Any]:
        if not self.model_is_configured():
            raise ValueError("Model is not configured yet.")
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)

        locked_characters = self._normalize_characters(characters) or list(manifest.get("locked_characters", []))
        if not locked_characters:
            raise ValueError("At least one character is required.")

        existing_character_names = set()
        artifact_index = manifest.get("artifact_index", {}).get("characters", [])
        if isinstance(artifact_index, list):
            existing_character_names.update(
                str(item.get("name", "")).strip() for item in artifact_index if isinstance(item, dict)
            )
        character_dirs = manifest.get("artifacts", {}).get("character_dirs", {})
        if isinstance(character_dirs, dict):
            existing_character_names.update(str(name).strip() for name in character_dirs.keys())
        existing_requested = [name for name in locked_characters if name in existing_character_names]
        new_requested = [name for name in locked_characters if name not in existing_character_names]
        relation_characters = self._normalize_characters([*existing_character_names, *locked_characters])
        using_new_source = bool(str(novel_content_base64 or "").strip())
        redistill_summary = f"继续蒸馏：新增 {len(new_requested)} 人，增量 {len(existing_requested)} 人"

        if using_new_source:
            run_dir = self.runs_root / run_id
            updates_dir = run_dir / "input" / "updates"
            updates_dir.mkdir(parents=True, exist_ok=True)
            file_name = safe_filename(novel_name or "novel-update.txt")
            raw_bytes = self._decode_base64(novel_content_base64)
            if not raw_bytes:
                raise ValueError("Novel content is empty.")
            stamped_name = f"{_utc_now().replace(':', '').replace('-', '')}_{file_name}"
            novel_path = updates_dir / stamped_name
            novel_path.write_bytes(raw_bytes)
        else:
            novel_path = Path(str(manifest.get("novel_path", "")).strip())
            if not novel_path.exists():
                raise ValueError("Novel source file is missing for this run.")

        progress = manifest.setdefault("progress", {})
        progress.update(
            {
                "stage": "characters_locked",
                "message": redistill_summary,
                "current_character": "",
                "completed_characters": [],
                "total_characters": len(locked_characters),
                "completed_count": 0,
                "graph_status": "pending",
                "chunking": {},
            }
        )
        manifest["locked_characters"] = locked_characters
        manifest["novel_path"] = str(novel_path.resolve())
        manifest["redistill"] = {
            "requested_characters": locked_characters,
            "new_characters": new_requested,
            "existing_characters": existing_requested,
            "relation_characters": relation_characters,
            "summary": redistill_summary,
            "used_new_source": using_new_source,
            "source_name": Path(novel_path).name,
        }
        if using_new_source:
            sources = list(manifest.get("novel_sources", []))
            sources.append(
                self._build_novel_source_entry(
                    novel_path,
                    source_name=Path(novel_path).name,
                    kind="incremental_update",
                    raw_bytes=raw_bytes,
                )
            )
            manifest["novel_sources"] = sources
        manifest["status"] = "running"
        manifest["success"] = False
        manifest["updated_at"] = _utc_now()
        manifest["timing"] = {
            "started_at": _utc_now(),
            "completed_at": "",
            "failed_at": "",
            "stopped_at": "",
            "elapsed_seconds": 0.0,
            "elapsed_text": "",
        }
        manifest["control"] = {
            "stop_requested": False,
            "stop_requested_at": "",
            "stop_acknowledged_at": "",
        }
        manifest["quality"] = {
            "excerpt_focus": {
                "matched_characters": [],
                "missing_characters": [],
                "strategy": "",
            },
            "stage_presence": [],
            "character_focus": {},
            "profile_repairs": {"count": 0, "characters": []},
            "relation_repairs": {"count": 0, "pairs": []},
        }
        manifest.setdefault("summary", {}).update(
            {
                "characters_total": len(locked_characters),
                "characters_completed": 0,
                "graph_status": "pending",
                "status_text": "waiting_for_payloads",
                "chunking": {},
            }
        )
        manifest.setdefault("artifacts", {}).setdefault("chunking", {})
        manifest.setdefault("capabilities", {})["distill"] = {
            "status": "preparing",
            "success": False,
            "updated_at": _utc_now(),
            "message": "incremental distill requested",
            "outputs": {
                "update_mode": "incremental" if existing_requested else "refresh",
                "used_new_source": using_new_source,
            },
        }
        manifest["capabilities"]["export_graph"] = {
            "status": "preparing",
            "success": False,
            "updated_at": _utc_now(),
            "message": "graph regeneration requested",
        }
        manifest["events"] = [
            {
                "stage": "redistill_requested",
                "status": "running",
                "message": redistill_summary,
                "character": "",
                "capability": "distill",
                "timestamp": _utc_now(),
            }
        ]
        if using_new_source:
            manifest["events"].append(
                {
                    "stage": "source_updated",
                    "status": "running",
                    "message": f"已换入新的书段：{Path(novel_path).name}",
                    "character": "",
                    "capability": "distill",
                    "timestamp": _utc_now(),
                }
            )
        self._write_json(manifest_path, manifest)
        self._start_background_run(
            manifest_path=manifest_path,
            novel_path=novel_path,
            locked_characters=locked_characters,
            relation_characters=relation_characters,
            max_sentences=max_sentences,
            max_chars=max_chars,
        )
        return self._serialize_manifest(self._load_manifest(manifest_path) or manifest)

    def ingest_character_result(
        self,
        run_id: str,
        *,
        character: str,
        content_base64: str,
        filename: str = "PROFILE.generated.md",
    ) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)

        run_dir = self.runs_root / run_id
        novel_id = str(manifest.get("novel_id", "")).strip() or run_id
        safe_character = safe_filename(character)
        host_output_dir = run_dir / "host_output" / novel_id / safe_character
        host_output_dir.mkdir(parents=True, exist_ok=True)
        source_path = host_output_dir / safe_filename(filename or "PROFILE.generated.md")
        source_text = decode_text_content(content_base64)
        source_path.write_text(source_text, encoding="utf-8")

        persona_dir = run_dir / "artifacts" / "characters" / novel_id / safe_character
        payload = materialize_profile_source(source_path, persona_dir)

        manifest.setdefault("capabilities", {})["materialize"] = {
            "status": "complete",
            "success": True,
            "updated_at": _utc_now(),
            "message": f"{payload['character']} materialized",
        }
        manifest.setdefault("artifacts", {}).setdefault("character_dirs", {})
        manifest["artifacts"]["character_dirs"][payload["character"]] = payload["persona_dir"]
        manifest.setdefault("events", []).append(
            {
                "stage": "character_completed",
                "status": "running",
                "message": f"{payload['character']} 人物包已生成",
                "character": payload["character"],
                "capability": "materialize",
                "timestamp": _utc_now(),
            }
        )
        refreshed = self._discover_artifacts(manifest)
        refreshed["updated_at"] = _utc_now()
        self._write_json(manifest_path, refreshed)
        return self._serialize_manifest(refreshed)

    def ingest_relation_result(
        self,
        run_id: str,
        *,
        content_base64: str,
        filename: str = "relations.md",
    ) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)

        run_dir = self.runs_root / run_id
        novel_id = str(manifest.get("novel_id", "")).strip() or run_id
        relations_dir = run_dir / "artifacts" / "relations"
        relations_dir.mkdir(parents=True, exist_ok=True)
        relation_source = relations_dir / safe_filename(filename or f"{novel_id}_relations.md")
        relation_source.write_text(decode_text_content(content_base64), encoding="utf-8")
        graph_payload = export_relations_source(relation_source, novel_id=novel_id, manifest_path=manifest_path)

        manifest.setdefault("capabilities", {})["export_graph"] = {
            "status": "complete",
            "success": True,
            "updated_at": _utc_now(),
            "message": "relation graph exported",
        }
        manifest.setdefault("events", []).append(
            {
                "stage": "graph_export_completed",
                "status": "running",
                "message": "人物关系图谱已生成",
                "character": "",
                "capability": "export_graph",
                "timestamp": _utc_now(),
            }
        )
        manifest.setdefault("artifacts", {})["relation_graph"] = dict(graph_payload)
        refreshed = self._discover_artifacts(manifest)
        refreshed["updated_at"] = _utc_now()
        self._write_json(manifest_path, refreshed)
        return self._serialize_manifest(refreshed)

    def get_persona_review(self, run_id: str, character: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        persona_dir = self._resolve_persona_dir(manifest, character)
        editable_path = persona_dir / "PROFILE.md"
        generated_path = persona_dir / "PROFILE.generated.md"
        source_path = editable_path if editable_path.exists() else generated_path
        if not source_path.exists():
            raise FileNotFoundError(character)
        profile = load_profile_source(source_path)
        return {
            "run_id": run_id,
            "character": str(profile.get("name", "")).strip() or character,
            "persona_dir": str(persona_dir.resolve()),
            "editable_profile_path": str(editable_path.resolve()) if editable_path.exists() else "",
            "generated_profile_path": str(generated_path.resolve()) if generated_path.exists() else "",
            "fields": {field: str(profile.get(field, "")).strip() for field in self.PERSONA_REVIEW_FIELDS},
        }

    def save_persona_review(self, run_id: str, character: str, fields: dict[str, str]) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        persona_dir = self._resolve_persona_dir(manifest, character)
        editable_path = persona_dir / "PROFILE.md"
        generated_path = persona_dir / "PROFILE.generated.md"
        source_path = editable_path if editable_path.exists() else generated_path
        if not source_path.exists():
            raise FileNotFoundError(character)
        profile = load_profile_source(source_path)
        for field in self.PERSONA_REVIEW_FIELDS:
            if field not in fields:
                continue
            profile[field] = str(fields.get(field, "") or "").strip()
        editable_path = write_persona_profile(persona_dir, profile)
        refreshed = self._discover_artifacts(manifest)
        refreshed["updated_at"] = _utc_now()
        refreshed.setdefault("events", []).append(
            {
                "stage": "persona_review_saved",
                "status": "running",
                "message": f"{character} 的人物校对已保存",
                "character": character,
                "capability": "materialize",
                "timestamp": _utc_now(),
            }
        )
        self._write_json(self._manifest_path(run_id), refreshed)
        payload = self.get_persona_review(run_id, character)
        payload["editable_profile_path"] = str(editable_path.resolve())
        return payload

    def list_relation_details(self, run_id: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        relations_file = self._resolve_relations_file(manifest)
        payload = load_relations_source(relations_file)
        relations = dict(payload.get("relations", {}) or {})
        items: list[dict[str, Any]] = []
        for pair_key, relation in sorted(relations.items()):
            if not isinstance(relation, dict):
                continue
            left, right = self._split_relation_pair(pair_key)
            items.append(
                {
                    "pair_key": pair_key,
                    "characters": [left, right],
                    "trust": int(relation.get("trust", 0) or 0),
                    "affection": int(relation.get("affection", 0) or 0),
                    "hostility": int(relation.get("hostility", 0) or 0),
                    "relationship_type": self._relation_type_label(relation),
                    "relation_change": str(relation.get("relation_change", "")).strip(),
                    "conflict_point": str(relation.get("conflict_point", "")).strip(),
                    "typical_interaction": str(relation.get("typical_interaction", "")).strip(),
                    "evidence_lines": self._coerce_relation_evidence(relation),
                }
            )
        return {
            "run_id": run_id,
            "novel_id": str(manifest.get("novel_id", "")).strip(),
            "relations_file": str(relations_file.resolve()),
            "relation_count": len(items),
            "items": items,
        }

    def resolve_run_file(self, run_id: str, relative_path: str) -> Path:
        run_dir = self.runs_root / run_id
        if not run_dir.exists():
            raise FileNotFoundError(run_id)
        candidate = (run_dir / relative_path).resolve()
        if run_dir.resolve() not in candidate.parents and candidate != run_dir.resolve():
            raise ValueError("Path escapes run directory.")
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(relative_path)
        return candidate

    def list_dialogue_sessions(self, run_id: str) -> list[dict[str, Any]]:
        self._ensure_run_exists(run_id)
        return self.dialogue.list_sessions(run_id)

    def create_dialogue_session(
        self,
        run_id: str,
        *,
        mode: str,
        participants: list[str],
        controlled_character: str = "",
        self_profile: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        session = self.dialogue.create_session(
            manifest,
            mode=mode,
            participants=participants,
            controlled_character=controlled_character,
            self_profile=self_profile,
        )
        opening_message = self._build_dialogue_opening_message(session)
        self.dialogue.prepare_turn(
            manifest,
            session_id=str(session.get("session_id", "")).strip(),
            message=opening_message,
            speaker_override="场景提示",
            transcript_message="",
        )
        pending_payload = self._load_pending_turn_payload(run_id, str(session.get("session_id", "")).strip())
        try:
            responses = self._generate_dialogue_responses(run_id, pending_payload)
        except LLMRequestError as exc:
            raise ValueError(self._friendly_dialogue_llm_error(exc)) from exc
        return self.dialogue.ingest_turn_responses(
            run_id,
            session_id=str(session.get("session_id", "")).strip(),
            responses=responses,
        )

    def get_dialogue_session(self, run_id: str, session_id: str) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        return self.dialogue.get_session(run_id, session_id)

    def delete_dialogue_session(self, run_id: str, session_id: str) -> None:
        self._ensure_run_exists(run_id)
        self.dialogue.delete_session(run_id, session_id)

    def prepare_dialogue_turn(self, run_id: str, *, session_id: str, message: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        return self.dialogue.prepare_turn(manifest, session_id=session_id, message=message)

    def reply_dialogue_turn(self, run_id: str, *, session_id: str, message: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        self.dialogue.prepare_turn(manifest, session_id=session_id, message=message)
        pending_payload = self._load_pending_turn_payload(run_id, session_id)
        try:
            responses = self._generate_dialogue_responses(run_id, pending_payload)
        except LLMRequestError as exc:
            raise ValueError(self._friendly_dialogue_llm_error(exc)) from exc
        return self.dialogue.ingest_turn_responses(run_id, session_id=session_id, responses=responses)

    def ingest_dialogue_turn(
        self,
        run_id: str,
        *,
        session_id: str,
        responses: list[dict[str, str]],
    ) -> dict[str, Any]:
        self._ensure_run_exists(run_id)
        return self.dialogue.ingest_turn_responses(run_id, session_id=session_id, responses=responses)

    def _serialize_manifest(self, payload: dict[str, Any]) -> dict[str, Any]:
        manifest = dict(payload)
        run_id = str(manifest.get("run_id", "")).strip()
        if run_id:
            manifest["file_urls"] = self._build_file_urls(run_id, manifest)
        return manifest

    def _discover_artifacts(self, manifest: dict[str, Any]) -> dict[str, Any]:
        updated = json.loads(json.dumps(manifest, ensure_ascii=False))
        webui = updated.get("webui", {})
        workspace = webui.get("workspace", {})
        run_dir = Path(str(webui.get("run_dir", ""))).resolve() if webui.get("run_dir") else None
        artifact_dir = Path(str(webui.get("artifact_dir", ""))).resolve() if webui.get("artifact_dir") else None
        characters_root = Path(str(workspace.get("characters_root", ""))).resolve() if workspace.get("characters_root") else None
        relations_root = Path(str(workspace.get("relations_root", ""))).resolve() if workspace.get("relations_root") else None

        character_index = self._discover_character_cards(characters_root)
        if character_index:
            updated.setdefault("artifacts", {}).setdefault("character_dirs", {})
            updated["artifacts"]["character_dirs"] = {
                item["name"]: item["persona_dir"] for item in character_index
            }
            updated.setdefault("artifact_index", {})["characters"] = character_index
            completed_names = [item["name"] for item in character_index]
            updated.setdefault("progress", {})["completed_characters"] = completed_names
            updated["progress"]["completed_count"] = len(completed_names)
            if updated.get("locked_characters") and len(completed_names) >= len(updated["locked_characters"]):
                if updated["progress"].get("graph_status") == "complete":
                    updated["summary"]["status_text"] = "waiting_for_verification"
                else:
                    updated["summary"]["status_text"] = "graph_pending"
                updated["progress"]["current_character"] = ""
            updated["summary"]["characters_completed"] = len(completed_names)

        relation_graph = self._discover_relation_graph(relations_root, artifact_dir, run_dir)
        if relation_graph:
            updated.setdefault("artifacts", {})["relation_graph"] = relation_graph
            updated.setdefault("artifact_index", {})["relation_graph"] = relation_graph
            updated.setdefault("progress", {})["graph_status"] = "complete"
            if updated["summary"].get("status_text") in {"waiting_for_payloads", "waiting_for_host_generation", "graph_pending"}:
                updated["summary"]["status_text"] = "graph_ready"
            updated["summary"]["graph_status"] = "complete"

        updated.setdefault("progress", {}).setdefault("chunking", self._build_progress_chunking_from_artifacts(updated.get("artifacts", {}).get("chunking", {})))
        updated.setdefault("summary", {})["chunking"] = self._build_summary_chunking(updated.get("progress", {}).get("chunking", {}))

        return updated

    @staticmethod
    def _stage_presence(excerpt_stages: dict[str, Any] | None) -> list[str]:
        stages = dict(excerpt_stages or {})
        labels: list[str] = []
        mapping = {"start": "前段", "mid": "中段", "end": "后段"}
        for key, label in mapping.items():
            if str(stages.get(key, "")).strip():
                labels.append(label)
        return labels

    def _build_quality_snapshot(
        self,
        *,
        matched_characters: list[str],
        missing_characters: list[str],
        strategy: str,
        excerpt_stages: dict[str, Any] | None,
        character_focus: dict[str, Any] | None = None,
        profile_repairs: dict[str, Any] | None = None,
        relation_repairs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "excerpt_focus": {
                "matched_characters": self._normalize_characters(matched_characters),
                "missing_characters": self._normalize_characters(missing_characters),
                "strategy": str(strategy or "").strip(),
            },
            "stage_presence": self._stage_presence(excerpt_stages),
            "character_focus": dict(character_focus or {}),
            "profile_repairs": {
                "count": int((profile_repairs or {}).get("count", 0) or 0),
                "characters": self._normalize_characters((profile_repairs or {}).get("characters", [])),
            },
            "relation_repairs": {
                "count": int((relation_repairs or {}).get("count", 0) or 0),
                "pairs": [str(item).strip() for item in list((relation_repairs or {}).get("pairs", [])) if str(item).strip()],
            },
        }

    @staticmethod
    def _chunk_overview_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
        request = dict(payload.get("request", {}) or {})
        meta = dict(payload.get("meta", {}) or {})
        return {
            "chunk_mode": str(request.get("chunk_mode", "single")).strip() or "single",
            "chunk_count": int(meta.get("chunk_count", 0) or 0),
            "merge_required": bool(meta.get("merge_required", False)),
        }

    @staticmethod
    def _build_progress_chunking_from_artifacts(chunking: dict[str, Any] | None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for capability, item in dict(chunking or {}).items():
            if not isinstance(item, dict):
                continue
            result[capability] = {
                "capability": capability,
                "mode": str(item.get("chunk_mode", "single")).strip() or "single",
                "chunk_count": int(item.get("chunk_count", 0) or 0),
                "current_chunk": 0,
                "current_label": "",
                "status": "pending",
                "merge_required": bool(item.get("merge_required", False)),
                "merge_status": "pending",
            }
        return result

    @staticmethod
    def _build_summary_chunking(chunking: dict[str, Any] | None) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        for capability, item in dict(chunking or {}).items():
            if not isinstance(item, dict):
                continue
            summary[capability] = {
                "mode": str(item.get("mode", "")).strip(),
                "chunk_count": int(item.get("chunk_count", 0) or 0),
                "current_chunk": int(item.get("current_chunk", 0) or 0),
                "status": str(item.get("status", "pending")).strip() or "pending",
                "merge_required": bool(item.get("merge_required", False)),
                "merge_status": str(item.get("merge_status", "pending")).strip() or "pending",
            }
        return summary

    def _update_manifest_chunk_progress(
        self,
        manifest: dict[str, Any],
        *,
        capability: str,
        mode: str = "",
        chunk_count: int | None = None,
        current_chunk: int | None = None,
        current_label: str = "",
        status: str = "",
        merge_required: bool | None = None,
        merge_status: str = "",
        extras: dict[str, Any] | None = None,
    ) -> None:
        artifacts = manifest.setdefault("artifacts", {})
        artifact_chunking = artifacts.setdefault("chunking", {})
        artifact_current = dict(artifact_chunking.get(capability, {}))
        if mode:
            artifact_current["chunk_mode"] = mode
        if chunk_count is not None:
            artifact_current["chunk_count"] = int(chunk_count or 0)
        if merge_required is not None:
            artifact_current["merge_required"] = bool(merge_required)
        if extras:
            artifact_current.update(dict(extras))
        artifact_chunking[capability] = artifact_current

        progress = manifest.setdefault("progress", {})
        progress_chunking = progress.setdefault("chunking", {})
        progress_current = dict(progress_chunking.get(capability, {}))
        progress_current["capability"] = capability
        if mode:
            progress_current["mode"] = mode
        if chunk_count is not None:
            progress_current["chunk_count"] = int(chunk_count or 0)
        if current_chunk is not None:
            progress_current["current_chunk"] = int(current_chunk or 0)
        if current_label or current_label == "":
            progress_current["current_label"] = str(current_label or "")
        if status:
            progress_current["status"] = status
        if merge_required is not None:
            progress_current["merge_required"] = bool(merge_required)
        if merge_status:
            progress_current["merge_status"] = merge_status
        progress_chunking[capability] = progress_current
        manifest.setdefault("summary", {})["chunking"] = self._build_summary_chunking(progress_chunking)

    @staticmethod
    def _format_elapsed_text(seconds: float) -> str:
        total = max(0, int(round(seconds)))
        minutes, remain = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        parts: list[str] = []
        if hours:
            parts.append(f"{hours}小时")
        if minutes:
            parts.append(f"{minutes}分钟")
        if remain or not parts:
            parts.append(f"{remain}秒")
        return "".join(parts)

    def _finalize_manifest_timing(self, manifest: dict[str, Any], *, outcome: str) -> None:
        timing = manifest.setdefault("timing", {})
        started_at = str(timing.get("started_at", "")).strip()
        now_text = _utc_now()
        finished_key = {
            "completed": "completed_at",
            "failed": "failed_at",
            "stopped": "stopped_at",
        }.get(str(outcome or "").strip(), "failed_at")
        timing[finished_key] = now_text
        if started_at:
            try:
                from datetime import datetime

                started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                finished = datetime.fromisoformat(now_text.replace("Z", "+00:00"))
                elapsed_seconds = max(0.0, (finished - started).total_seconds())
            except Exception:
                elapsed_seconds = 0.0
        else:
            elapsed_seconds = 0.0
        timing["elapsed_seconds"] = round(elapsed_seconds, 3)
        timing["elapsed_text"] = self._format_elapsed_text(elapsed_seconds)

    def _is_stop_requested(self, manifest_path: Path) -> bool:
        manifest = self._load_manifest(manifest_path) or {}
        return bool((manifest.get("control", {}) or {}).get("stop_requested", False))

    def _assert_run_not_stopped(
        self,
        manifest_path: Path,
        *,
        message: str = "这次蒸馏已停止。",
        current_character: str = "",
    ) -> None:
        if not self._is_stop_requested(manifest_path):
            return
        manifest = self._load_manifest(manifest_path) or {}
        control = manifest.setdefault("control", {})
        if not str(control.get("stop_acknowledged_at", "")).strip():
            control["stop_acknowledged_at"] = _utc_now()
            manifest["updated_at"] = _utc_now()
            self._write_json(manifest_path, manifest)
        if current_character:
            raise RunStoppedError(f"已停止蒸馏，停在 {current_character}。")
        raise RunStoppedError(message)

    def _build_file_urls(self, run_id: str, manifest: dict[str, Any]) -> dict[str, str]:
        urls: dict[str, str] = {}
        manifest_path = self._manifest_path(run_id)
        urls["manifest"] = self._file_url(run_id, manifest_path.relative_to(self.runs_root / run_id))
        payloads = manifest.get("artifacts", {}).get("payloads", {})
        if isinstance(payloads, dict):
            for key, value in payloads.items():
                path = Path(str(value))
                if path.exists():
                    urls[f"payload_{key}"] = self._file_url(run_id, path.relative_to(self.runs_root / run_id))
        character_items = manifest.get("artifact_index", {}).get("characters", [])
        if isinstance(character_items, list):
            for item in character_items:
                profile = Path(str(item.get("profile_file", "")))
                if profile.exists():
                    urls[f"character_{item.get('name', '')}"] = self._file_url(run_id, profile.relative_to(self.runs_root / run_id))
        relation_graph = manifest.get("artifact_index", {}).get("relation_graph", {})
        if isinstance(relation_graph, dict):
            for key in ("html_path", "svg_path", "mermaid_path", "relations_file"):
                value = str(relation_graph.get(key, "")).strip()
                if not value:
                    continue
                path = Path(value)
                if path.exists():
                    urls[f"graph_{key.replace('_path', '')}"] = self._file_url(run_id, path.relative_to(self.runs_root / run_id))
        return urls

    def _file_url(self, run_id: str, relative_path: Path) -> str:
        return f"/api/web/runs/{run_id}/files/{relative_path.as_posix()}"

    def _manifest_path(self, run_id: str) -> Path:
        return self.runs_root / run_id / "run_manifest.json"

    def _require_manifest(self, run_id: str) -> dict[str, Any]:
        payload = self._load_manifest(self._manifest_path(run_id))
        if not payload:
            raise FileNotFoundError(run_id)
        return payload

    def _ensure_run_exists(self, run_id: str) -> None:
        if not self._manifest_path(run_id).exists():
            raise FileNotFoundError(run_id)

    def _load_manifest(self, manifest_path: Path) -> dict[str, Any] | None:
        if not manifest_path.exists():
            return None
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload, changed = self._reconcile_loaded_manifest(manifest_path, payload)
        if changed:
            self._write_json(manifest_path, payload)
        return payload

    def _reconcile_loaded_manifest(self, manifest_path: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        manifest = dict(payload or {})
        run_id = str(manifest.get("run_id", "")).strip() or manifest_path.parent.name
        status = str(manifest.get("status", "")).strip()
        control = dict(manifest.get("control", {}) or {})
        thread = self._active_run_threads.get(run_id)
        thread_alive = bool(thread and thread.is_alive())
        if status == "running" and bool(control.get("stop_requested", False)) and not thread_alive:
            now_text = _utc_now()
            manifest["status"] = "stopped"
            manifest["success"] = False
            manifest["updated_at"] = now_text
            progress = manifest.setdefault("progress", {})
            progress["stage"] = "stopped"
            current_character = str(progress.get("current_character", "")).strip()
            progress["message"] = f"已停止蒸馏，停在 {current_character}。" if current_character else "这次蒸馏已停止。"
            summary = manifest.setdefault("summary", {})
            summary["status_text"] = "stopped"
            control["stop_acknowledged_at"] = str(control.get("stop_acknowledged_at", "")).strip() or now_text
            manifest["control"] = control
            self._finalize_manifest_timing(manifest, outcome="stopped")
            if manifest.get("timing", {}).get("elapsed_text"):
                summary["elapsed_text"] = manifest["timing"]["elapsed_text"]
            manifest.setdefault("capabilities", {})["verify_workflow"] = {
                "status": "stopped",
                "success": False,
                "updated_at": now_text,
                "message": "automatic workflow stopped after restart reconciliation",
            }
            events = manifest.setdefault("events", [])
            if not any(str(item.get("stage", "")).strip() == "stopped" for item in events if isinstance(item, dict)):
                events.append(
                    {
                        "stage": "stopped",
                        "status": "stopped",
                        "message": progress["message"],
                        "character": current_character,
                        "capability": "verify_workflow",
                        "timestamp": now_text,
                    }
                )
            return manifest, True
        return manifest, False

    def _load_model_settings_payload(self) -> dict[str, Any]:
        return self._load_json_file(self.settings_path) or {}

    def _load_pending_turn_payload(self, run_id: str, session_id: str) -> dict[str, Any]:
        session_path = self.runs_root / run_id / "dialogue" / session_id / "session.json"
        session_payload = self._load_json_file(session_path) or {}
        pending_path_text = str(session_payload.get("pending_turn", {}).get("payload_path", "")).strip()
        if not pending_path_text:
            raise ValueError("Pending turn payload was not created.")
        pending_path = Path(pending_path_text)
        pending_payload = self._load_json_file(pending_path)
        if not pending_payload:
            raise ValueError("Pending turn payload is empty.")
        return pending_payload

    def _generate_dialogue_responses(self, run_id: str, payload: dict[str, Any]) -> list[dict[str, str]]:
        run_dir = self.runs_root / run_id
        config = self._build_runtime_config_for_run(run_dir=run_dir)
        parts = build_runtime_parts(config)
        if not hasattr(parts.llm, "chat_completion"):
            raise ValueError("Configured model does not support chat generation.")

        allowed_speakers = [str(item.get("name", "")).strip() for item in payload.get("responder_hints", [])]
        allowed_speakers.extend(["旁白", "场景提示"])
        attempts = (
            self._build_dialogue_llm_messages(payload, retry_on_empty=False),
            self._build_dialogue_llm_messages(payload, retry_on_empty=True),
        )
        last_error: Exception | None = None
        for index, llm_messages in enumerate(attempts):
            llm_result = parts.llm.chat_completion(
                llm_messages,
                temperature=float(config.get("llm.temperature", 0.35) or 0.35),
                max_tokens=int(config.get("llm.max_tokens", 900) or 900),
            )
            content = str(llm_result.get("content", "")).strip()
            if not content:
                last_error = ValueError("Model returned an empty reply.")
                if index + 1 < len(attempts):
                    continue
                break
            try:
                return self._parse_dialogue_responses(content=content, allowed_speakers=allowed_speakers)
            except ValueError as exc:
                last_error = exc
                if index + 1 < len(attempts):
                    continue
                raise
        raise ValueError("模型没有返回可用的角色回复。") from last_error

    @staticmethod
    def _build_dialogue_opening_message(session: dict[str, Any]) -> str:
        mode = str(session.get("mode", "observe")).strip() or "observe"
        participants = [str(item).strip() for item in session.get("participants", []) if str(item).strip()]
        cast = "、".join(participants) or "当前角色"
        if mode == "act":
            controlled = str(session.get("controlled_character", "")).strip() or "该角色"
            return (
                f"请先为 {controlled} 与 {cast} 生成一个自然开场。"
                "先给 1 条简短的场景提示或旁白，再让其他角色先接出第一轮对话，不要等待用户补充。"
            )
        if mode == "insert":
            self_profile = dict(session.get("self_insert", {}) or {})
            display_name = str(self_profile.get("display_name", "")).strip() or "我"
            scene_identity = str(self_profile.get("scene_identity", "")).strip()
            identity_suffix = f"，身份是{scene_identity}" if scene_identity else ""
            return (
                f"请先为 {display_name}{identity_suffix} 与 {cast} 生成一个自然开场。"
                "先给 1 条简短的场景提示或旁白，再让角色们先开口，对这个进入场景的人作出第一轮反应。"
            )
        return (
            f"请先为 {cast} 生成一个自然开场。"
            "先给 1 条简短的场景提示或旁白，再让角色们开始第一轮对话，让场景自己动起来。"
        )

    @staticmethod
    def _friendly_dialogue_llm_error(exc: Exception) -> str:
        message = str(exc or "").strip()
        lowered = message.lower()
        if any(token in lowered for token in ("invalidsubscription", "codingplan", "subscription has expired", "does not have a valid")):
            return "当前模型账号没有可用的对话生成订阅权限，请更换可用模型，或检查并续订当前账号权限。"
        return message or "当前模型调用失败，请检查模型配置后重试。"

    @staticmethod
    def _build_dialogue_llm_messages(payload: dict[str, Any], *, retry_on_empty: bool = False) -> list[dict[str, str]]:
        input_block = dict(payload.get("input", {}) or {})
        session_mode = str(payload.get("mode", "")).strip() or "observe"
        participants = [str(item).strip() for item in input_block.get("participants", []) if str(item).strip()]
        persona_contexts = payload.get("persona_contexts", [])
        relation_excerpt = str(payload.get("relation_context", {}).get("relations_excerpt", "")).strip()
        history = payload.get("history", [])
        instructions = dict(payload.get("instructions", {}) or {})
        host_action = dict(payload.get("host_action", {}) or {})
        response_limit = int(host_action.get("response_limit_hint", 2) or 2)

        system_parts = [
            str(payload.get("host_prompt_brief", "")).strip(),
            str(instructions.get("generation_goal", "")).strip(),
            str(instructions.get("mode_rule", "")).strip(),
            str(instructions.get("speaker_rule", "")).strip(),
            str(instructions.get("response_style", "")).strip(),
            str(host_action.get("output_rule", "")).strip(),
            "只返回 JSON 数组，每项必须包含 speaker 和 message。",
        ]
        if retry_on_empty:
            system_parts.append('这次至少返回 1 条可用回复；如果角色暂时不宜直接接话，可先返回 speaker 为“旁白”或“场景提示”的一条提示。')
        system_prompt = "\n".join(part for part in system_parts if part)

        user_payload = {
            "mode": session_mode,
            "speaker": str(input_block.get("speaker", "")).strip(),
            "message": str(input_block.get("message", "")).strip(),
            "participants": participants,
            "response_limit": response_limit,
            "persona_contexts": persona_contexts,
            "history": history,
            "relation_excerpt": relation_excerpt,
            "expected_output": host_action.get("expected_output", [{"speaker": "角色名", "message": "回复内容"}]),
            "retry_on_empty": retry_on_empty,
        }
        user_prompt = json.dumps(user_payload, ensure_ascii=False, indent=2)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    @staticmethod
    def _parse_dialogue_responses(content: str, allowed_speakers: list[str]) -> list[dict[str, str]]:

        text = str(content or "").strip()
        if not text:
            raise ValueError("Model returned an empty reply.")
        if text.startswith("```"):
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3].strip()
        parsed: Any
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end == -1 or end <= start:
                raise ValueError("Model reply is not valid JSON.") from None
            parsed = json.loads(text[start : end + 1])

        if isinstance(parsed, dict):
            parsed = parsed.get("responses", [])
        if not isinstance(parsed, list):
            raise ValueError("Model reply is not a response list.")

        allowed = {name for name in allowed_speakers if name}
        clean_responses: list[dict[str, str]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            speaker = str(item.get("speaker", "")).strip()
            message = str(item.get("message", "")).strip()
            if not speaker or not message:
                continue
            if allowed and speaker not in allowed:
                continue
            clean_responses.append({"speaker": speaker, "message": message})
        if not clean_responses:
            raise ValueError("Model reply did not contain usable character responses.")
        return clean_responses

    @staticmethod
    def _load_json_file(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _run_automatic_pipeline(
        self,
        *,
        manifest_path: Path,
        novel_path: Path,
        locked_characters: list[str],
        relation_characters: list[str] | None = None,
        max_sentences: int,
        max_chars: int,
        run_id: str = "",
    ) -> dict[str, Any]:
        manifest = self._load_manifest(manifest_path) or {}
        run_dir = manifest_path.parent
        novel_id = str(manifest.get("novel_id", "")).strip() or run_dir.name
        config = self._build_runtime_config_for_run(run_dir=run_dir)
        parts = build_runtime_parts(config)
        graph_cast = self._normalize_characters(relation_characters or locked_characters)

        def on_distill(stage: str, payload: dict[str, Any]) -> None:
            current = self._load_manifest(manifest_path) or manifest
            progress = current.setdefault("progress", {})
            if stage == "text_loaded":
                progress["stage"] = "text_loaded"
                progress["message"] = "已载入小说文本"
            elif stage == "characters_ready":
                progress["stage"] = "characters_ready"
                total = int(payload.get("total", 0) or 0)
                progress["message"] = f"已锁定 {total} 个待蒸馏角色" if total else "已锁定待蒸馏角色"
            elif stage == "drafting_character":
                progress["stage"] = "distilling"
                progress["current_character"] = payload.get("character", "")
                progress["message"] = f"正在蒸馏 {payload.get('character', '')}"
            elif stage == "materializing_character":
                progress["stage"] = "distilling"
                progress["current_character"] = payload.get("character", "")
                progress["message"] = f"正在落盘 {payload.get('character', '')}"
            elif stage == "chunking_character":
                progress["stage"] = "distilling"
                progress["current_character"] = payload.get("character", "")
                index = int(payload.get("chunk_index", 0) or 0)
                total = int(payload.get("chunk_total", 0) or 0)
                workers = int(payload.get("parallel_workers", 1) or 1)
                worker_suffix = f"，并行 {workers} 线程" if workers > 1 else ""
                progress["message"] = f"正在分批蒸馏 {payload.get('character', '')}（{index}/{total}）{worker_suffix}"
                self._update_manifest_chunk_progress(
                    current,
                    capability="distill",
                    mode="chunked",
                    chunk_count=total,
                    current_chunk=index,
                    current_label=str(payload.get("chunk_label", "")).strip(),
                    status="running",
                    merge_required=True,
                    merge_status="pending",
                    extras={"current_character": str(payload.get("character", "")).strip()},
                )
            elif stage == "merging_character":
                progress["stage"] = "distilling"
                progress["current_character"] = payload.get("character", "")
                progress["message"] = f"正在汇总 {payload.get('character', '')} 的分批草稿"
                self._update_manifest_chunk_progress(
                    current,
                    capability="distill",
                    mode="chunked",
                    chunk_count=int(payload.get("chunk_total", 0) or 0) or None,
                    current_chunk=int(payload.get("chunk_total", 0) or 0) or None,
                    current_label=str(payload.get("character", "")).strip(),
                    status="complete",
                    merge_required=True,
                    merge_status="running",
                    extras={"current_character": str(payload.get("character", "")).strip()},
                )
            elif stage == "character_done":
                completed = list(progress.get("completed_characters", []))
                character = str(payload.get("character", "")).strip()
                if character and character not in completed:
                    completed.append(character)
                progress["completed_characters"] = completed
                progress["completed_count"] = len(completed)
                progress["current_character"] = ""
                progress["message"] = f"{character} 蒸馏完成"
            current.setdefault("events", []).append(
                {
                    "stage": stage,
                    "status": "running",
                    "message": progress.get("message", ""),
                    "character": payload.get("character", ""),
                    "capability": "distill",
                    "timestamp": _utc_now(),
                }
            )
            current["updated_at"] = _utc_now()
            self._write_json(manifest_path, current)

        def on_relation(stage: str, payload: dict[str, Any]) -> None:
            current = self._load_manifest(manifest_path) or manifest
            progress = current.setdefault("progress", {})
            if stage == "rendering_graph":
                progress["stage"] = "rendering_graph"
                progress["graph_status"] = "running"
                progress["message"] = "正在生成人物关系图谱"
            elif stage == "chunking_graph":
                progress["stage"] = "rendering_graph"
                progress["graph_status"] = "running"
                index = int(payload.get("chunk_index", 0) or 0)
                total = int(payload.get("chunk_total", 0) or 0)
                workers = int(payload.get("parallel_workers", 1) or 1)
                worker_suffix = f"，并行 {workers} 线程" if workers > 1 else ""
                progress["message"] = f"正在分批抽取人物关系（{index}/{total}）{worker_suffix}"
                self._update_manifest_chunk_progress(
                    current,
                    capability="relation",
                    mode="chunked",
                    chunk_count=total,
                    current_chunk=index,
                    current_label=str(payload.get("chunk_label", "")).strip(),
                    status="running",
                    merge_required=True,
                    merge_status="pending",
                )
            elif stage == "merging_graph":
                progress["stage"] = "rendering_graph"
                progress["graph_status"] = "running"
                progress["message"] = "正在汇总分批关系草稿"
                self._update_manifest_chunk_progress(
                    current,
                    capability="relation",
                    mode="chunked",
                    chunk_count=int(payload.get("chunk_total", 0) or 0) or None,
                    current_chunk=int(payload.get("chunk_total", 0) or 0) or None,
                    current_label="关系汇总",
                    status="complete",
                    merge_required=True,
                    merge_status="running",
                )
            elif stage == "graph_done":
                progress["stage"] = "graph_done"
                progress["graph_status"] = "complete"
                progress["message"] = "人物关系图谱已生成"
            current.setdefault("events", []).append(
                {
                    "stage": stage,
                    "status": "running",
                    "message": progress.get("message", ""),
                    "character": "",
                    "capability": "export_graph",
                    "timestamp": _utc_now(),
                }
            )
            current["updated_at"] = _utc_now()
            self._write_json(manifest_path, current)

        try:
            if not hasattr(parts.llm, "chat_completion"):
                raise ValueError("Configured model does not support distill generation.")

            characters_root = parts.path_provider.characters_root(novel_id)
            payload_dir = run_dir / "payloads"
            host_output_root = run_dir / "host_output" / novel_id
            host_output_root.mkdir(parents=True, exist_ok=True)
            payload_dir.mkdir(parents=True, exist_ok=True)

            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止。")
            on_distill("text_loaded", {"source_path": str(novel_path.resolve())})
            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止。")
            on_distill("characters_ready", {"total": len(locked_characters), "characters": locked_characters})

            distill_payload_paths: dict[str, str] = {}
            character_dirs: dict[str, str] = {}
            distill_chunk_by_character: dict[str, Any] = {}
            quality_focus: dict[str, Any] = {}
            quality_matched: set[str] = set()
            quality_missing: set[str] = set()
            quality_stage_presence: set[str] = set()
            profile_repair_characters: list[str] = []
            for character in locked_characters:
                self._assert_run_not_stopped(manifest_path, current_character=character)
                on_distill("drafting_character", {"character": character})
                character_payload = build_distill_prompt_payload(
                    novel_path,
                    characters=[character],
                    max_sentences=max_sentences,
                    max_chars=max_chars,
                    characters_root=characters_root,
                    manifest_path=manifest_path,
                    update_mode="auto",
                )
                payload_path = payload_dir / f"distill_{safe_filename(character)}.json"
                self._write_json(payload_path, character_payload)
                distill_payload_paths[character] = str(payload_path.resolve())
                excerpt_focus = dict(character_payload.get("request", {}).get("excerpt_focus", {}) or {})
                stage_presence = self._stage_presence(character_payload.get("request", {}).get("excerpt_stages", {}))
                matched = character in excerpt_focus.get("matched_characters", [])
                missing = character in excerpt_focus.get("missing_characters", [])
                if matched:
                    quality_matched.add(character)
                if missing:
                    quality_missing.add(character)
                quality_stage_presence.update(stage_presence)
                self._assert_run_not_stopped(manifest_path, current_character=character)
                content, chunk_meta = self._generate_character_profile_markdown(
                    parts=parts,
                    config=config,
                    manifest_path=manifest_path,
                    payload=character_payload,
                    character=character,
                    peer_characters=locked_characters,
                    progress_hook=on_distill,
                )
                quality_focus[character] = {
                    "matched": matched,
                    "missing": missing,
                    "stage_presence": stage_presence,
                    "chunk_count": int(chunk_meta.get("chunk_count", 1) or 1),
                    "chunked": bool(chunk_meta.get("chunked", False)),
                }
                distill_chunk_by_character[character] = {
                    "chunk_count": int(chunk_meta.get("chunk_count", 1) or 1),
                    "chunked": bool(chunk_meta.get("chunked", False)),
                }
                if not content.strip():
                    raise ValueError(f"{character} 的人物档案生成为空。")
                host_output_dir = host_output_root / safe_filename(character)
                host_output_dir.mkdir(parents=True, exist_ok=True)
                source_path = host_output_dir / "PROFILE.generated.md"
                source_path.write_text(content.strip() + "\n", encoding="utf-8")
                self._assert_run_not_stopped(manifest_path, current_character=character)
                repaired_text = self._maybe_repair_generated_profile(
                    parts=parts,
                    config=config,
                    payload=character_payload,
                    character=character,
                    peer_characters=locked_characters,
                    source_path=source_path,
                )
                if repaired_text is not None:
                    source_path.write_text(repaired_text.strip() + "\n", encoding="utf-8")
                    if character not in profile_repair_characters:
                        profile_repair_characters.append(character)
                self._finalize_generated_profile_source(
                    source_path,
                    payload=character_payload,
                    chunk_count=int(chunk_meta.get("chunk_count", 1) or 1),
                )

                self._assert_run_not_stopped(manifest_path, current_character=character)
                on_distill("materializing_character", {"character": character})
                materialized = materialize_profile_source(
                    source_path,
                    run_dir / "artifacts" / "characters" / novel_id / safe_filename(character),
                )
                character_dirs[materialized["character"]] = materialized["persona_dir"]
                current = self._load_manifest(manifest_path) or manifest
                current.setdefault("artifacts", {}).setdefault("character_dirs", {}).update(character_dirs)
                current.setdefault("artifacts", {}).setdefault("payloads", {})["distill_characters"] = distill_payload_paths
                distill_total_chunks = sum(int(item.get("chunk_count", 1) or 1) for item in distill_chunk_by_character.values())
                distill_any_chunked = any(bool(item.get("chunked", False)) for item in distill_chunk_by_character.values())
                self._update_manifest_chunk_progress(
                    current,
                    capability="distill",
                    mode="chunked" if distill_any_chunked else "single",
                    chunk_count=distill_total_chunks,
                    current_chunk=distill_total_chunks if distill_any_chunked else 0,
                    current_label="人物蒸馏完成" if distill_any_chunked else "",
                    status="complete",
                    merge_required=distill_any_chunked,
                    merge_status="complete" if distill_any_chunked else "pending",
                    extras={"by_character": distill_chunk_by_character},
                )
                current.setdefault("capabilities", {})["materialize"] = {
                    "status": "running",
                    "success": False,
                    "updated_at": _utc_now(),
                    "message": f"{character} persona bundle materialized",
                }
                current["quality"] = self._build_quality_snapshot(
                    matched_characters=list(quality_matched),
                    missing_characters=list(quality_missing),
                    strategy="character_windows",
                    excerpt_stages={
                        "start": "yes" if "前段" in quality_stage_presence else "",
                        "mid": "yes" if "中段" in quality_stage_presence else "",
                        "end": "yes" if "后段" in quality_stage_presence else "",
                    },
                    character_focus=quality_focus,
                    profile_repairs={"count": len(profile_repair_characters), "characters": profile_repair_characters},
                    relation_repairs=(current.get("quality", {}) or {}).get("relation_repairs", {}),
                )
                current["updated_at"] = _utc_now()
                self._write_json(manifest_path, current)
                on_distill("character_done", {"character": materialized["character"]})

            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止。")
            relation_payload = build_relation_prompt_payload(
                novel_path,
                max_sentences=min(max_sentences, 80),
                max_chars=min(max_chars, 12_000),
                characters=graph_cast,
            )
            relation_payload_path = payload_dir / "relation_payload.auto.json"
            self._write_json(relation_payload_path, relation_payload)
            current = self._load_manifest(manifest_path) or manifest
            current.setdefault("artifacts", {}).setdefault("payloads", {})["relation"] = str(relation_payload_path.resolve())
            self._update_manifest_chunk_progress(
                current,
                capability="relation",
                mode=str(relation_payload.get("request", {}).get("chunk_mode", "single")).strip() or "single",
                chunk_count=int(relation_payload.get("meta", {}).get("chunk_count", 0) or 0),
                current_chunk=0,
                current_label="",
                status="pending",
                merge_required=bool(relation_payload.get("meta", {}).get("merge_required", False)),
                merge_status="pending",
            )
            current["quality"] = self._build_quality_snapshot(
                matched_characters=list(quality_matched),
                missing_characters=list(quality_missing),
                strategy=str(relation_payload.get("request", {}).get("excerpt_focus", {}).get("strategy", "character_windows")),
                excerpt_stages=relation_payload.get("request", {}).get("excerpt_stages", {}),
                character_focus=quality_focus,
                profile_repairs={"count": len(profile_repair_characters), "characters": profile_repair_characters},
                relation_repairs=(current.get("quality", {}) or {}).get("relation_repairs", {}),
            )
            current["updated_at"] = _utc_now()
            self._write_json(manifest_path, current)

            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
            on_relation("rendering_graph", {})
            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
            relation_markdown, relation_chunk_meta = self._generate_relation_markdown(
                parts=parts,
                config=config,
                manifest_path=manifest_path,
                payload=relation_payload,
                characters=graph_cast,
                progress_hook=on_relation,
            )
            if not relation_markdown.strip():
                raise ValueError("人物关系图谱结果为空。")
            relations_file = parts.path_provider.relations_file(novel_id)
            relations_file.parent.mkdir(parents=True, exist_ok=True)
            relations_file.write_text(relation_markdown.strip() + "\n", encoding="utf-8")
            repaired_relations = self._maybe_repair_generated_relations(
                parts=parts,
                config=config,
                payload=relation_payload,
                characters=graph_cast,
                relations_file=relations_file,
                relation_markdown=relation_markdown,
            )
            relation_repair_pairs: list[str] = []
            if repaired_relations is not None:
                relations_file.write_text(repaired_relations.strip() + "\n", encoding="utf-8")
                try:
                    repaired_payload = load_relations_source(relations_file)
                    relation_repair_pairs = [
                        str(key).strip()
                        for key in dict(repaired_payload.get("relations", {}) or {}).keys()
                        if str(key).strip()
                    ]
                except Exception:
                    relation_repair_pairs = []
            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续落盘。")
            graph_payload = export_relations_source(relations_file, novel_id=novel_id, manifest_path=manifest_path)
            current = self._load_manifest(manifest_path) or manifest
            current.setdefault("artifacts", {})["relation_graph"] = dict(graph_payload)
            self._update_manifest_chunk_progress(
                current,
                capability="relation",
                mode="chunked" if bool(relation_chunk_meta.get("chunked", False)) else "single",
                chunk_count=int(relation_chunk_meta.get("chunk_count", 1) or 1),
                current_chunk=int(relation_chunk_meta.get("chunk_count", 1) or 1)
                if bool(relation_chunk_meta.get("chunked", False))
                else 0,
                current_label="关系图谱完成" if bool(relation_chunk_meta.get("chunked", False)) else "",
                status="complete",
                merge_required=bool(relation_chunk_meta.get("chunked", False)),
                merge_status="complete" if bool(relation_chunk_meta.get("chunked", False)) else "pending",
            )
            current["quality"] = self._build_quality_snapshot(
                matched_characters=list(quality_matched),
                missing_characters=list(quality_missing),
                strategy=str(relation_payload.get("request", {}).get("excerpt_focus", {}).get("strategy", "character_windows")),
                excerpt_stages=relation_payload.get("request", {}).get("excerpt_stages", {}),
                character_focus=quality_focus,
                profile_repairs={"count": len(profile_repair_characters), "characters": profile_repair_characters},
                relation_repairs={
                    "count": 1 if repaired_relations is not None else 0,
                    "pairs": relation_repair_pairs,
                    "chunked": bool(relation_chunk_meta.get("chunked", False)),
                    "chunk_count": int(relation_chunk_meta.get("chunk_count", 1) or 1),
                },
            )
            current["updated_at"] = _utc_now()
            self._write_json(manifest_path, current)
            on_relation("graph_done", {})

            refreshed = self._discover_artifacts(self._load_manifest(manifest_path) or manifest)
            refreshed["status"] = "ready"
            refreshed["success"] = True
            refreshed["updated_at"] = _utc_now()
            self._finalize_manifest_timing(refreshed, outcome="completed")
            refreshed.setdefault("summary", {})["status_text"] = "workflow_complete"
            if refreshed.get("timing", {}).get("elapsed_text"):
                refreshed["summary"]["elapsed_text"] = refreshed["timing"]["elapsed_text"]
            refreshed.setdefault("capabilities", {})["distill"] = {
                "status": "complete",
                "success": True,
                "updated_at": _utc_now(),
                "message": "canonical profiles generated",
            }
            refreshed["capabilities"]["materialize"] = {
                "status": "complete",
                "success": True,
                "updated_at": _utc_now(),
                "message": "persona bundle written",
            }
            refreshed["capabilities"]["export_graph"] = {
                "status": "complete",
                "success": True,
                "updated_at": _utc_now(),
                "message": "relation graph exported",
            }
            refreshed["capabilities"]["verify_workflow"] = {
                "status": "complete",
                "success": True,
                "updated_at": _utc_now(),
                "message": "automatic workflow finished",
            }
            refreshed.setdefault("events", []).append(
                {
                    "stage": "workflow_complete",
                    "status": "complete",
                    "message": f"本次整理耗时 {refreshed['timing']['elapsed_text']}" if refreshed.get("timing", {}).get("elapsed_text") else "本次整理已完成",
                    "character": "",
                    "capability": "verify_workflow",
                    "timestamp": _utc_now(),
                }
            )
            self._write_json(manifest_path, refreshed)
            return self._serialize_manifest(refreshed)
        except RunStoppedError as exc:
            stopped = self._load_manifest(manifest_path) or manifest
            stopped["status"] = "stopped"
            stopped["success"] = False
            stopped["updated_at"] = _utc_now()
            self._finalize_manifest_timing(stopped, outcome="stopped")
            stopped.setdefault("summary", {})["status_text"] = "stopped"
            if stopped.get("timing", {}).get("elapsed_text"):
                stopped["summary"]["elapsed_text"] = stopped["timing"]["elapsed_text"]
            progress = stopped.setdefault("progress", {})
            progress["stage"] = "stopped"
            progress["message"] = str(exc)
            control = stopped.setdefault("control", {})
            if not str(control.get("stop_acknowledged_at", "")).strip():
                control["stop_acknowledged_at"] = _utc_now()
            stopped.setdefault("capabilities", {})["verify_workflow"] = {
                "status": "stopped",
                "success": False,
                "updated_at": _utc_now(),
                "message": "automatic workflow stopped by user",
            }
            stopped.setdefault("events", []).append(
                {
                    "stage": "stopped",
                    "status": "stopped",
                    "message": str(exc),
                    "character": str(progress.get("current_character", "")).strip(),
                    "capability": "verify_workflow",
                    "timestamp": _utc_now(),
                }
            )
            if stopped.get("timing", {}).get("elapsed_text"):
                stopped.setdefault("events", []).append(
                    {
                        "stage": "stopped_timing",
                        "status": "stopped",
                        "message": f"本次整理已停止，已耗时 {stopped['timing']['elapsed_text']}",
                        "character": "",
                        "capability": "verify_workflow",
                        "timestamp": _utc_now(),
                    }
                )
            self._write_json(manifest_path, stopped)
            return self._serialize_manifest(stopped)
        except Exception as exc:
            failed = self._load_manifest(manifest_path) or manifest
            failed["status"] = "failed"
            failed["success"] = False
            failed["updated_at"] = _utc_now()
            self._finalize_manifest_timing(failed, outcome="failed")
            failed.setdefault("summary", {})["status_text"] = "failed"
            if failed.get("timing", {}).get("elapsed_text"):
                failed["summary"]["elapsed_text"] = failed["timing"]["elapsed_text"]
            failed.setdefault("progress", {})["message"] = str(exc)
            failed.setdefault("events", []).append(
                {
                    "stage": "failed",
                    "status": "failed",
                    "message": str(exc),
                    "character": "",
                    "capability": "verify_workflow",
                    "timestamp": _utc_now(),
                }
            )
            if failed.get("timing", {}).get("elapsed_text"):
                failed.setdefault("events", []).append(
                    {
                        "stage": "failed_timing",
                        "status": "failed",
                        "message": f"本次整理已中断，已耗时 {failed['timing']['elapsed_text']}",
                        "character": "",
                        "capability": "verify_workflow",
                        "timestamp": _utc_now(),
                    }
                )
            self._write_json(manifest_path, failed)
            raise

    @staticmethod
    def _sanitize_markdown_output(content: str) -> str:
        text = str(content or "").strip()
        if not text:
            return ""
        fenced = re.search(r"```(?:markdown|md)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return text

    def _finalize_generated_profile_source(
        self,
        source_path: Path,
        *,
        payload: dict[str, Any],
        chunk_count: int,
    ) -> None:
        try:
            profile = load_profile_source(source_path)
        except Exception:
            return
        evidence = self._profile_evidence_from_payload(payload, chunk_count=chunk_count)
        profile["description_count"] = int(evidence["description_count"])
        profile["dialogue_count"] = int(evidence["dialogue_count"])
        profile["thought_count"] = int(evidence["thought_count"])
        profile["chunk_count"] = int(evidence["chunk_count"])
        profile["evidence"] = {
            "description_count": int(evidence["description_count"]),
            "dialogue_count": int(evidence["dialogue_count"]),
            "thought_count": int(evidence["thought_count"]),
            "chunk_count": int(evidence["chunk_count"]),
        }
        if not str(profile.get("evidence_source", "")).strip():
            profile["evidence_source"] = str(evidence["evidence_source"]).strip()
        rendered = render_profile_md(profile).strip()
        if rendered:
            source_path.write_text(rendered + "\n", encoding="utf-8")

    def _profile_evidence_from_payload(self, payload: dict[str, Any], *, chunk_count: int) -> dict[str, Any]:
        request = dict(payload.get("request", {}) or {})
        excerpt = str(request.get("excerpt", "")).strip()
        sentences = [item.strip() for item in split_sentences(excerpt) if item.strip()]
        if not sentences and excerpt:
            sentences = [item.strip() for item in excerpt.splitlines() if item.strip()]

        description_count = 0
        dialogue_count = 0
        thought_count = 0
        for sentence in sentences:
            if self._looks_like_thought_or_evaluation_sentence(sentence):
                thought_count += 1
            elif self._looks_like_dialogue_sentence(sentence):
                dialogue_count += 1
            else:
                description_count += 1

        excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
        stage_refs: list[str] = []
        for stage_key in ("start", "mid", "end"):
            if str(excerpt_stages.get(stage_key, "")).strip():
                stage_refs.append(f"excerpt:{stage_key}")
        strategy = str((request.get("excerpt_focus", {}) or {}).get("strategy", "")).strip()
        if strategy:
            stage_refs.append(f"strategy:{strategy}")

        return {
            "description_count": description_count,
            "dialogue_count": dialogue_count,
            "thought_count": thought_count,
            "chunk_count": max(1, int(chunk_count or 1)),
            "evidence_source": "；".join(stage_refs),
        }

    @staticmethod
    def _looks_like_dialogue_sentence(text: str) -> bool:
        sample = str(text or "").strip()
        if not sample:
            return False
        if any(token in sample for token in ('"', "“", "”", "「", "」")):
            return True
        return bool(re.search(r"(说道|笑道|问道|答道|道：|道:|喊道|喝道|骂道|低声道|轻声道)", sample))

    @staticmethod
    def _looks_like_thought_or_evaluation_sentence(text: str) -> bool:
        sample = str(text or "").strip()
        if not sample:
            return False
        return bool(
            re.search(
                r"(心想|心道|心里|想着|只觉|觉得|不禁|暗想|思忖|寻思|素来|向来|一向|生性|性子|为人|看似|其实|原是|本就)",
                sample,
            )
        )

    def _llm_cap(self, config: Config, key: str, fallback: int) -> int:
        configured = int(config.get(key, 0) or 0)
        if configured > 0:
            return min(configured, fallback)
        return fallback

    def _generate_character_profile_markdown(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        payload: dict[str, Any],
        character: str,
        peer_characters: list[str],
        progress_hook: Any | None = None,
    ) -> tuple[str, dict[str, Any]]:
        self._assert_run_not_stopped(manifest_path, current_character=character)
        if self._should_use_chunked_distill(payload):
            return self._generate_character_profile_markdown_chunked(
                parts=parts,
                config=config,
                manifest_path=manifest_path,
                payload=payload,
                character=character,
                peer_characters=peer_characters,
                progress_hook=progress_hook,
            )
        try:
            self._assert_run_not_stopped(manifest_path, current_character=character)
            llm_result = parts.llm.chat_completion(
                self._build_distill_llm_messages(
                    payload,
                    character=character,
                    peer_characters=peer_characters,
                ),
                temperature=float(config.get("llm.temperature", 0.2) or 0.2),
                max_tokens=self._llm_cap(config, "llm.max_tokens", self.DISTILL_SINGLE_MAX_TOKENS),
            )
            content = self._sanitize_markdown_output(str(llm_result.get("content", "")))
            return content, {"chunked": False, "chunk_count": 1}
        except LLMRequestError as exc:
            logger.warning("Single-pass distill failed for %s, retrying with chunked distill: %s", character, exc)
            return self._generate_character_profile_markdown_chunked(
                parts=parts,
                config=config,
                manifest_path=manifest_path,
                payload=payload,
                character=character,
                peer_characters=peer_characters,
                progress_hook=progress_hook,
                fallback_reason=str(exc),
            )

    def _generate_character_profile_markdown_chunked(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        payload: dict[str, Any],
        character: str,
        peer_characters: list[str],
        progress_hook: Any | None = None,
        fallback_reason: str = "",
    ) -> tuple[str, dict[str, Any]]:
        chunk_entries = self._build_distill_chunk_payloads(payload)
        if len(chunk_entries) <= 1:
            self._assert_run_not_stopped(manifest_path, current_character=character)
            llm_result = parts.llm.chat_completion(
                self._build_distill_llm_messages(
                    payload,
                    character=character,
                    peer_characters=peer_characters,
                ),
                temperature=float(config.get("llm.temperature", 0.2) or 0.2),
                max_tokens=self._llm_cap(config, "llm.max_tokens", self.DISTILL_SINGLE_MAX_TOKENS),
            )
            content = self._sanitize_markdown_output(str(llm_result.get("content", "")))
            return content, {"chunked": False, "chunk_count": 1}

        workers = self._chunk_parallel_workers(config=config, chunk_total=len(chunk_entries))
        drafts = self._run_distill_chunk_drafts(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            chunk_entries=chunk_entries,
            character=character,
            peer_characters=peer_characters,
            progress_hook=progress_hook,
            workers=workers,
        )

        if not drafts:
            raise ValueError(f"{character} 的分批蒸馏结果为空。")
        if len(drafts) == 1:
            return drafts[0]["content"], {
                "chunked": True,
                "chunk_count": len(chunk_entries),
                "fallback_reason": fallback_reason,
                "parallel_workers": workers,
            }

        if callable(progress_hook):
            progress_hook("merging_character", {"character": character, "chunk_total": len(drafts), "parallel_workers": workers})
        self._assert_run_not_stopped(manifest_path, current_character=character)
        merge_result = parts.llm.chat_completion(
            self._build_distill_merge_messages(
                payload,
                character=character,
                peer_characters=peer_characters,
                chunk_drafts=drafts,
                fallback_reason=fallback_reason,
            ),
            temperature=float(config.get("llm.temperature", 0.2) or 0.2),
            max_tokens=self._llm_cap(config, "llm.max_tokens", self.DISTILL_MERGE_MAX_TOKENS),
        )
        merged_content = self._sanitize_markdown_output(str(merge_result.get("content", "")))
        return merged_content, {
            "chunked": True,
            "chunk_count": len(chunk_entries),
            "fallback_reason": fallback_reason,
            "parallel_workers": workers,
        }

    def _generate_relation_markdown(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        payload: dict[str, Any],
        characters: list[str],
        progress_hook: Any | None = None,
    ) -> tuple[str, dict[str, Any]]:
        self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
        if self._should_use_chunked_relation(payload):
            return self._generate_relation_markdown_chunked(
                parts=parts,
                config=config,
                manifest_path=manifest_path,
                payload=payload,
                characters=characters,
                progress_hook=progress_hook,
            )
        try:
            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
            relation_result = parts.llm.chat_completion(
                self._build_relation_llm_messages(payload, characters=characters),
                temperature=float(config.get("llm.temperature", 0.2) or 0.2),
                max_tokens=self._llm_cap(config, "llm.max_tokens", self.RELATION_SINGLE_MAX_TOKENS),
            )
            relation_markdown = self._sanitize_markdown_output(str(relation_result.get("content", "")))
            return relation_markdown, {"chunked": False, "chunk_count": 1}
        except LLMRequestError as exc:
            logger.warning("Single-pass relation graph failed, retrying with chunked relation distill: %s", exc)
            return self._generate_relation_markdown_chunked(
                parts=parts,
                config=config,
                manifest_path=manifest_path,
                payload=payload,
                characters=characters,
                progress_hook=progress_hook,
                fallback_reason=str(exc),
            )

    def _generate_relation_markdown_chunked(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        payload: dict[str, Any],
        characters: list[str],
        progress_hook: Any | None = None,
        fallback_reason: str = "",
    ) -> tuple[str, dict[str, Any]]:
        chunk_entries = self._build_relation_chunk_payloads(payload)
        if len(chunk_entries) <= 1:
            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
            relation_result = parts.llm.chat_completion(
                self._build_relation_llm_messages(payload, characters=characters),
                temperature=float(config.get("llm.temperature", 0.2) or 0.2),
                max_tokens=self._llm_cap(config, "llm.max_tokens", self.RELATION_SINGLE_MAX_TOKENS),
            )
            relation_markdown = self._sanitize_markdown_output(str(relation_result.get("content", "")))
            return relation_markdown, {"chunked": False, "chunk_count": 1}

        workers = self._chunk_parallel_workers(config=config, chunk_total=len(chunk_entries))
        drafts = self._run_relation_chunk_drafts(
            parts=parts,
            config=config,
            manifest_path=manifest_path,
            chunk_entries=chunk_entries,
            characters=characters,
            progress_hook=progress_hook,
            workers=workers,
        )

        if not drafts:
            raise ValueError("分批关系图谱结果为空。")
        if len(drafts) == 1:
            return drafts[0]["content"], {
                "chunked": True,
                "chunk_count": len(chunk_entries),
                "fallback_reason": fallback_reason,
                "parallel_workers": workers,
            }

        if callable(progress_hook):
            progress_hook("merging_graph", {"chunk_total": len(drafts), "parallel_workers": workers})
        self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
        merge_result = parts.llm.chat_completion(
            self._build_relation_merge_messages(
                payload,
                characters=characters,
                chunk_drafts=drafts,
                fallback_reason=fallback_reason,
            ),
            temperature=float(config.get("llm.temperature", 0.2) or 0.2),
            max_tokens=self._llm_cap(config, "llm.max_tokens", self.RELATION_MERGE_MAX_TOKENS),
        )
        merged_markdown = self._sanitize_markdown_output(str(merge_result.get("content", "")))
        return merged_markdown, {
            "chunked": True,
            "chunk_count": len(chunk_entries),
            "fallback_reason": fallback_reason,
            "parallel_workers": workers,
        }

    @staticmethod
    def _render_payload_section(title: str, value: Any) -> str:
        if isinstance(value, str):
            body = value.strip()
        else:
            body = json.dumps(value, ensure_ascii=False, indent=2)
        return f"## {title}\n{body}".strip()

    def _build_distill_llm_messages(
        self,
        payload: dict[str, Any],
        *,
        character: str,
        peer_characters: list[str] | None = None,
        chunk_label: str = "",
        chunk_index: int = 0,
        chunk_total: int = 0,
        chunk_mode: str = "",
    ) -> list[dict[str, str]]:
        references = dict(payload.get("references", {}) or {})
        request = dict(payload.get("request", {}) or {})
        meta = dict(payload.get("meta", {}) or {})
        system_prompt = str(payload.get("prompt", "")).strip()
        peers = [name for name in self._normalize_characters(peer_characters or []) if name != character]
        excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
        focused_request = dict(request)
        focused_request.pop("excerpt_stages", None)
        user_parts = [
            f"目标角色：{character}",
            f"同批角色：{'、'.join(peers) if peers else '无'}",
            "请严格根据以下 skill payload 输出该角色唯一一份完整的 PROFILE.generated.md Markdown。",
            "不要解释，不要输出代码块，不要补充额外前后缀。",
            "如果证据不足，相关字段直接写“证据不足”。",
            self._build_distill_priority_guidance(character),
            self._build_excerpt_stage_guidance(excerpt_stages),
            self._build_dialogue_style_guidance(request, character),
            self._build_chunk_distill_guidance(
                chunk_label=chunk_label,
                chunk_index=chunk_index,
                chunk_total=chunk_total,
                chunk_mode=chunk_mode,
            ),
            self._render_payload_section("OUTPUT_SCHEMA", references.get("output_schema", "")),
            self._render_payload_section("STYLE_DIFFER", references.get("style_differ", "")),
            self._render_payload_section("LOGIC_CONSTRAINT", references.get("logic_constraint", "")),
            self._render_payload_section("VALIDATION_POLICY", references.get("validation_policy", "")),
            self._render_payload_section("REQUEST", focused_request),
            self._render_payload_section("META", meta),
        ]
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(part for part in user_parts if part).strip()},
        ]

    def _build_distill_merge_messages(
        self,
        payload: dict[str, Any],
        *,
        character: str,
        peer_characters: list[str] | None,
        chunk_drafts: list[dict[str, str]],
        fallback_reason: str = "",
    ) -> list[dict[str, str]]:
        references = dict(payload.get("references", {}) or {})
        request = dict(payload.get("request", {}) or {})
        meta = dict(payload.get("meta", {}) or {})
        excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
        focused_request = dict(request)
        focused_request.pop("excerpt", None)
        focused_request.pop("excerpt_stages", None)
        peers = [name for name in self._normalize_characters(peer_characters or []) if name != character]
        drafts_text = "\n\n".join(
            f"### {item['label']}\n{item['content']}".strip()
            for item in chunk_drafts
            if str(item.get("content", "")).strip()
        ).strip()
        system_prompt = str(payload.get("prompt", "")).strip()
        user_parts = [
            f"目标角色：{character}",
            f"同批角色：{'、'.join(peers) if peers else '无'}",
            "以下是基于多个证据块得到的局部 PROFILE 草稿，请整合成唯一一份最终 PROFILE.generated.md。",
            "去重、纠偏、补足稳定特征；不要保留桥段碎句、剧情转述或互相打架的字段。",
            "说话风格优先保留重复出现的口头禅、语气词、起句、句尾和代表句味道。",
            "不要解释，不要输出代码块，不要补充额外前后缀。",
            f"补充分批原因参考：{fallback_reason}" if fallback_reason else "",
            self._build_distill_priority_guidance(character),
            self._build_excerpt_stage_guidance(excerpt_stages),
            self._build_dialogue_style_guidance(request, character),
            self._render_payload_section("OUTPUT_SCHEMA", references.get("output_schema", "")),
            self._render_payload_section("STYLE_DIFFER", references.get("style_differ", "")),
            self._render_payload_section("LOGIC_CONSTRAINT", references.get("logic_constraint", "")),
            self._render_payload_section("VALIDATION_POLICY", references.get("validation_policy", "")),
            self._render_payload_section("REQUEST", focused_request),
            self._render_payload_section("CHUNK_DRAFTS", drafts_text or "证据不足"),
            self._render_payload_section("META", meta),
        ]
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(part for part in user_parts if part).strip()},
        ]

    def _build_distill_chunk_payloads(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        request = dict(payload.get("request", {}) or {})
        excerpt = str(request.get("excerpt", "")).strip()
        excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
        chunk_entries: list[dict[str, Any]] = []
        for stage_key, stage_label in (("start", "前段"), ("mid", "中段"), ("end", "后段")):
            stage_text = str(excerpt_stages.get(stage_key, "")).strip()
            if not stage_text:
                continue
            stage_chunks = self._chunk_excerpt_text(stage_text)
            for index, chunk_text in enumerate(stage_chunks, start=1):
                chunk_request = dict(request)
                chunk_request["excerpt"] = chunk_text
                chunk_request["excerpt_stages"] = {"start": "", "mid": "", "end": ""}
                chunk_request["excerpt_stages"][stage_key] = chunk_text
                chunk_request["excerpt_focus"] = {
                    **dict(request.get("excerpt_focus", {}) or {}),
                    "strategy": "chunked_character_windows",
                }
                chunk_meta = dict(payload.get("meta", {}) or {})
                chunk_meta["chunk_stage"] = stage_key
                chunk_meta["chunk_index"] = index
                chunk_meta["chunk_total"] = len(stage_chunks)
                chunk_entries.append(
                    {
                        "label": f"{stage_label}-{index}" if len(stage_chunks) > 1 else stage_label,
                        "payload": {
                            **payload,
                            "request": chunk_request,
                            "meta": chunk_meta,
                        },
                    }
                )
        if chunk_entries:
            return chunk_entries
        excerpt_chunks = self._chunk_excerpt_text(excerpt)
        return [
            {
                "label": f"证据块-{index}",
                "payload": {
                    **payload,
                    "request": {
                        **request,
                        "excerpt": chunk_text,
                        "excerpt_stages": {"start": "", "mid": "", "end": ""},
                    },
                    "meta": {
                        **dict(payload.get("meta", {}) or {}),
                        "chunk_index": index,
                        "chunk_total": len(excerpt_chunks),
                    },
                },
            }
            for index, chunk_text in enumerate(excerpt_chunks, start=1)
        ]

    def _chunk_parallel_workers(self, *, config: Config, chunk_total: int) -> int:
        if chunk_total <= 1:
            return 1
        provider = str(config.get("llm.provider", "") or "").strip().lower()
        configured = int(config.get("llm.parallel_chunk_workers", 6) or 6)
        configured = max(1, configured)
        if provider == "ollama":
            return 1
        return min(configured, 6, chunk_total)

    def _run_distill_chunk_drafts(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        chunk_entries: list[dict[str, Any]],
        character: str,
        peer_characters: list[str],
        progress_hook: Any | None,
        workers: int,
    ) -> list[dict[str, str]]:
        def run_one(index: int, chunk_entry: dict[str, Any]) -> dict[str, str]:
            self._assert_run_not_stopped(manifest_path, current_character=character)
            if callable(progress_hook):
                progress_hook(
                    "chunking_character",
                    {
                        "character": character,
                        "chunk_index": index,
                        "chunk_total": len(chunk_entries),
                        "chunk_label": chunk_entry["label"],
                        "parallel_workers": workers,
                    },
                )
            self._assert_run_not_stopped(manifest_path, current_character=character)
            llm_result = parts.llm.chat_completion(
                self._build_distill_llm_messages(
                    chunk_entry["payload"],
                    character=character,
                    peer_characters=peer_characters,
                    chunk_label=str(chunk_entry["label"]),
                    chunk_index=index,
                    chunk_total=len(chunk_entries),
                    chunk_mode="partial",
                ),
                temperature=float(config.get("llm.temperature", 0.18) or 0.18),
                max_tokens=self._llm_cap(config, "llm.max_tokens", self.DISTILL_CHUNK_MAX_TOKENS),
            )
            content = self._sanitize_markdown_output(str(llm_result.get("content", ""))).strip()
            return {"label": str(chunk_entry["label"]), "content": content, "index": index}

        if workers <= 1:
            drafts: list[dict[str, str]] = []
            for index, chunk_entry in enumerate(chunk_entries, start=1):
                self._assert_run_not_stopped(manifest_path, current_character=character)
                result = run_one(index, chunk_entry)
                if result["content"]:
                    drafts.append(result)
            return sorted(drafts, key=lambda item: int(item["index"]))

        try:
            futures: dict[concurrent.futures.Future[dict[str, str]], int] = {}
            drafts = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="zaomeng-distill") as executor:
                for index, chunk_entry in enumerate(chunk_entries, start=1):
                    futures[executor.submit(run_one, index, chunk_entry)] = index
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result["content"]:
                        drafts.append(result)
            return sorted(drafts, key=lambda item: int(item["index"]))
        except Exception as exc:
            if isinstance(exc, RunStoppedError):
                raise
            logger.warning("Parallel distill chunk execution failed for %s, falling back to sequential mode: %s", character, exc)
            drafts = []
            for index, chunk_entry in enumerate(chunk_entries, start=1):
                self._assert_run_not_stopped(manifest_path, current_character=character)
                result = run_one(index, chunk_entry)
                if result["content"]:
                    drafts.append(result)
            return sorted(drafts, key=lambda item: int(item["index"]))

    def _run_relation_chunk_drafts(
        self,
        *,
        parts: Any,
        config: Config,
        manifest_path: Path,
        chunk_entries: list[dict[str, Any]],
        characters: list[str],
        progress_hook: Any | None,
        workers: int,
    ) -> list[dict[str, str]]:
        def run_one(index: int, chunk_entry: dict[str, Any]) -> dict[str, str]:
            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
            if callable(progress_hook):
                progress_hook(
                    "chunking_graph",
                    {
                        "chunk_index": index,
                        "chunk_total": len(chunk_entries),
                        "chunk_label": chunk_entry["label"],
                        "parallel_workers": workers,
                    },
                )
            self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
            relation_result = parts.llm.chat_completion(
                self._build_relation_llm_messages(
                    chunk_entry["payload"],
                    characters=characters,
                    chunk_label=str(chunk_entry["label"]),
                    chunk_index=index,
                    chunk_total=len(chunk_entries),
                    chunk_mode="partial",
                ),
                temperature=float(config.get("llm.temperature", 0.18) or 0.18),
                max_tokens=self._llm_cap(config, "llm.max_tokens", self.RELATION_CHUNK_MAX_TOKENS),
            )
            content = self._sanitize_markdown_output(str(relation_result.get("content", ""))).strip()
            return {"label": str(chunk_entry["label"]), "content": content, "index": index}

        if workers <= 1:
            drafts: list[dict[str, str]] = []
            for index, chunk_entry in enumerate(chunk_entries, start=1):
                self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
                result = run_one(index, chunk_entry)
                if result["content"]:
                    drafts.append(result)
            return sorted(drafts, key=lambda item: int(item["index"]))

        try:
            futures: dict[concurrent.futures.Future[dict[str, str]], int] = {}
            drafts = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="zaomeng-relation") as executor:
                for index, chunk_entry in enumerate(chunk_entries, start=1):
                    futures[executor.submit(run_one, index, chunk_entry)] = index
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result["content"]:
                        drafts.append(result)
            return sorted(drafts, key=lambda item: int(item["index"]))
        except Exception as exc:
            if isinstance(exc, RunStoppedError):
                raise
            logger.warning("Parallel relation chunk execution failed, falling back to sequential mode: %s", exc)
            drafts = []
            for index, chunk_entry in enumerate(chunk_entries, start=1):
                self._assert_run_not_stopped(manifest_path, message="这次蒸馏已停止，关系图未继续生成。")
                result = run_one(index, chunk_entry)
                if result["content"]:
                    drafts.append(result)
            return sorted(drafts, key=lambda item: int(item["index"]))

    def _should_use_chunked_distill(self, payload: dict[str, Any]) -> bool:
        request = dict(payload.get("request", {}) or {})
        excerpt = str(request.get("excerpt", "")).strip()
        if not excerpt:
            return False
        sentence_count = len(split_sentences(excerpt))
        return len(excerpt) > self.DISTILL_CHUNK_TRIGGER_CHARS or sentence_count > self.DISTILL_CHUNK_TRIGGER_SENTENCES

    def _chunk_excerpt_text(self, text: str) -> list[str]:
        clean = str(text or "").strip()
        if not clean:
            return []
        sentences = [item.strip() for item in split_sentences(clean) if item.strip()]
        if not sentences:
            sentences = [item.strip() for item in clean.splitlines() if item.strip()] or [clean]
        chunks: list[str] = []
        current: list[str] = []
        current_chars = 0
        for sentence in sentences:
            units = [sentence[i : i + self.DISTILL_CHUNK_MAX_CHARS] for i in range(0, len(sentence), self.DISTILL_CHUNK_MAX_CHARS)] or [sentence]
            for unit in units:
                unit = unit.strip()
                if not unit:
                    continue
                projected = current_chars + len(unit) + (1 if current else 0)
                if current and (len(current) >= self.DISTILL_CHUNK_MAX_SENTENCES or projected > self.DISTILL_CHUNK_MAX_CHARS):
                    chunks.append("\n".join(current).strip())
                    current = []
                    current_chars = 0
                current.append(unit)
                current_chars += len(unit) + (1 if len(current) > 1 else 0)
        if current:
            chunks.append("\n".join(current).strip())
        return [item for item in chunks if item]

    @staticmethod
    def _build_chunk_distill_guidance(
        *,
        chunk_label: str = "",
        chunk_index: int = 0,
        chunk_total: int = 0,
        chunk_mode: str = "",
    ) -> str:
        if not chunk_total:
            return ""
        lines = [
            "## CHUNK_MODE",
            f"- 当前是证据块 {chunk_index}/{chunk_total}：{chunk_label or '未命名证据块'}",
            "- 这是分批蒸馏中的局部草稿，请尽量完整，但允许写“证据不足”。",
            "- 不要因为当前块缺少信息，就虚构角色稳定特征。",
        ]
        if chunk_mode == "partial":
            lines.append("- 输出仍然必须是 PROFILE.generated.md 格式，但这是局部草案，后续还会汇总。")
        return "\n".join(lines).strip()

    def _maybe_repair_generated_relations(
        self,
        *,
        parts: Any,
        config: Config,
        payload: dict[str, Any],
        characters: list[str],
        relations_file: Path,
        relation_markdown: str,
    ) -> str | None:
        try:
            relation_payload = load_relations_source(relations_file)
        except Exception:
            return None
        issues = self._collect_relation_repair_issues(relation_payload)
        if not issues:
            return None
        repair_result = parts.llm.chat_completion(
            self._build_relation_repair_messages(
                payload,
                characters=characters,
                relation_markdown=relation_markdown,
                issues=issues,
            ),
            temperature=float(config.get("llm.temperature", 0.15) or 0.15),
            max_tokens=self._llm_cap(config, "llm.max_tokens", self.RELATION_REPAIR_MAX_TOKENS),
        )
        repaired = self._sanitize_markdown_output(str(repair_result.get("content", "")))
        return repaired or None

    def _collect_relation_repair_issues(self, relation_payload: dict[str, Any]) -> list[str]:
        relations = dict(relation_payload.get("relations", {}) or {})
        issues: list[str] = []
        for pair_key, item in sorted(relations.items()):
            if not isinstance(item, dict):
                continue
            for field in self.RELATION_REWRITE_FIELDS:
                value = str(item.get(field, "")).strip()
                if not value:
                    if field == "hidden_attitude":
                        continue
                    if field == "relation_change":
                        issues.append(f"{pair_key}.{field}: 为空")
                    continue
                if self._looks_like_unstable_relation_scalar(value):
                    issues.append(f"{pair_key}.{field}: 像剧情摘要或叙述片段 -> {value}")
                elif field == "relation_change" and len(value) > 12:
                    issues.append(f"{pair_key}.{field}: 过长，不像关系趋势标签 -> {value}")
        return issues

    @staticmethod
    def _looks_like_unstable_relation_scalar(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        if any(token in text for token in ('"', "“", "”", "‘", "’", "「", "」")):
            return True
        if text.endswith(("：", ":", "，", ",", "；", ";", "、")):
            return True
        if len(text) > 42:
            return True
        return bool(
            re.search(
                r"(只见|忽见|回头|转过|只听|听见|听得|说道|笑道|问道|喝道|骂道|叹道|叫道|大家想着|心里还自|拍着手|走了出来|看了.*一眼|转过大厅|墙角边|旧诗有云)",
                text,
            )
        )

    def _build_relation_repair_messages(
        self,
        payload: dict[str, Any],
        *,
        characters: list[str],
        relation_markdown: str,
        issues: list[str],
    ) -> list[dict[str, str]]:
        base_messages = self._build_relation_llm_messages(payload, characters=characters)
        repair_instruction = "\n".join(
            [
                "## REPAIR_TASK",
                "你刚刚生成的关系图谱里，有少数关系字段更像剧情摘要、叙述碎句，或不像关系趋势结论。",
                "请只修正这些问题字段，让它们回到关系结论表达。",
                "typical_interaction 应写互动模式，不写具体桥段流水账。",
                "conflict_point 应写冲突焦点，不写整段剧情。",
                "relation_change 应写简短趋势，如升温、恶化、稳定、反复波动、固化。",
                "hidden_attitude 只在有表里落差时填写；没有证据可以留空。",
                "输出仍然必须是完整的 RELATION_GRAPH Markdown，不要解释。",
                "",
                "### ISSUES",
                *[f"- {item}" for item in issues],
                "",
                "### CURRENT_DRAFT",
                relation_markdown.strip(),
            ]
        ).strip()
        return [
            base_messages[0],
            {"role": "user", "content": f"{base_messages[1]['content']}\n\n{repair_instruction}"},
        ]

    def _maybe_repair_generated_profile(
        self,
        *,
        parts: Any,
        config: Config,
        payload: dict[str, Any],
        character: str,
        peer_characters: list[str],
        source_path: Path,
    ) -> str | None:
        try:
            profile = load_profile_source(source_path)
        except Exception:
            return None
        dialogue_evidence = self._extract_dialogue_evidence(payload, character=character)
        issues = self._collect_profile_repair_issues(profile, dialogue_evidence=dialogue_evidence)
        completion_issues = self._collect_profile_completion_issues(profile)
        updated = False
        if issues or completion_issues:
            repair_result = parts.llm.chat_completion(
                self._build_distill_repair_messages(
                    payload,
                    character=character,
                    peer_characters=peer_characters,
                    profile=profile,
                    issues=issues,
                    completion_issues=completion_issues,
                    dialogue_evidence=dialogue_evidence,
                ),
                temperature=float(config.get("llm.temperature", 0.15) or 0.15),
                max_tokens=self._llm_cap(config, "llm.max_tokens", self.PROFILE_REPAIR_MAX_TOKENS),
            )
            repaired = self._sanitize_markdown_output(str(repair_result.get("content", "")))
            if repaired:
                source_path.write_text(repaired.strip() + "\n", encoding="utf-8")
                try:
                    profile = load_profile_source(source_path)
                    updated = True
                except Exception:
                    return repaired or None

        group_gaps = self._collect_profile_completion_groups(profile)
        if not updated and not group_gaps:
            return None
        if group_gaps:
            for group_name, fields in group_gaps[: self.PROFILE_COMPLETION_GROUP_LIMIT]:
                completion_result = parts.llm.chat_completion(
                    self._build_distill_completion_messages(
                        payload,
                        character=character,
                        peer_characters=peer_characters,
                        profile=profile,
                        group_name=group_name,
                        fields=fields,
                        dialogue_evidence=dialogue_evidence,
                    ),
                    temperature=float(config.get("llm.temperature", 0.1) or 0.1),
                    max_tokens=self._llm_cap(config, "llm.max_tokens", self.PROFILE_COMPLETION_MAX_TOKENS),
                )
                patch_text = self._sanitize_markdown_output(str(completion_result.get("content", ""))).strip()
                if not patch_text:
                    continue
                self._merge_profile_patch(profile, patch_text)
                updated = True

        self._apply_profile_missing_fallbacks(profile)
        rendered = render_profile_md(profile).strip()
        return (rendered + "\n") if updated and rendered else (rendered if rendered else None)

    def _collect_profile_repair_issues(
        self,
        profile: dict[str, Any],
        *,
        dialogue_evidence: list[str] | None = None,
    ) -> list[str]:
        issues: list[str] = []
        for field in self.PROFILE_REWRITE_FIELDS:
            value = str(profile.get(field, "")).strip()
            if not value:
                issues.append(f"{field}: 为空")
                continue
            if value == "证据不足":
                continue
            if self._looks_like_unstable_profile_scalar(value):
                issues.append(f"{field}: 像剧情碎句或叙述片段 -> {value}")
                continue
            if len(value) <= 4:
                issues.append(f"{field}: 过短，像未完成结论 -> {value}")
        if dialogue_evidence:
            speech_style = str(profile.get("speech_style", "")).strip()
            cadence = str(profile.get("cadence", "")).strip() or str(
                (profile.get("speech_habits", {}) or {}).get("cadence", "")
            ).strip()
            signature_phrases = self._profile_list_value(profile, "signature_phrases")
            typical_lines = self._profile_list_value(profile, "typical_lines")
            sentence_openers = self._profile_list_value(profile, "sentence_openers")
            sentence_endings = self._profile_list_value(profile, "sentence_endings")

            if not speech_style or self._looks_generic_style_scalar(speech_style):
                issues.append(f"speech_style: 太泛，缺少对白味道 -> {speech_style or '空'}")
            if not cadence:
                issues.append("cadence: 为空")
            if len(signature_phrases) == 0 and len(typical_lines) < 2:
                issues.append("signature_phrases / typical_lines: 太少，口头禅与代表句不够")
            if len(sentence_openers) == 0 and len(sentence_endings) == 0:
                issues.append("sentence_openers / sentence_endings: 缺少稳定的起句或收尾习惯")
        return issues

    def _collect_profile_completion_issues(self, profile: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        for field in self.PROFILE_COMPLETION_FIELDS:
            if self._profile_field_is_effectively_empty(profile, field):
                issues.append(f"{field}: 为空，请结合正文补齐；若仍无证据则写“证据不足”")
        return issues

    def _collect_profile_completion_groups(self, profile: dict[str, Any]) -> list[tuple[str, tuple[str, ...]]]:
        groups: list[tuple[str, tuple[str, ...]]] = []
        for group_name, fields in self.PROFILE_COMPLETION_GROUPS:
            missing = tuple(field for field in fields if self._profile_field_is_effectively_empty(profile, field))
            if missing:
                groups.append((group_name, missing))
        return groups

    def _profile_field_is_effectively_empty(self, profile: dict[str, Any], field: str) -> bool:
        if field == "cadence":
            value = str((profile.get("speech_habits", {}) or {}).get("cadence", "")).strip() or str(profile.get("cadence", "")).strip()
            return not value
        if field in {"signature_phrases", "sentence_openers", "connective_tokens", "sentence_endings", "forbidden_fillers"}:
            return len(self._profile_list_value(profile, field)) == 0
        if field in {"anger_style", "joy_style", "grievance_style"}:
            value = str((profile.get("emotion_profile", {}) or {}).get(field, "")).strip() or str(profile.get(field, "")).strip()
            return not value
        if field in {"arc_start", "arc_mid", "arc_end"}:
            arc_key = field.replace("arc_", "")
            value = (profile.get("arc", {}) or {}).get(arc_key, {})
            return not bool(value)
        value = profile.get(field, "")
        if isinstance(value, list):
            return len([str(item).strip() for item in value if str(item).strip()]) == 0
        if isinstance(value, dict):
            return not bool(value)
        return not str(value or "").strip()

    def _merge_profile_patch(self, profile: dict[str, Any], patch_text: str) -> None:
        for raw_line in str(patch_text or "").splitlines():
            line = raw_line.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            field, raw_value = line[2:].split(":", 1)
            key = str(field or "").strip()
            value_text = str(raw_value or "").strip()
            if not key:
                continue
            if key in self.PROFILE_MAP_FIELDS:
                parsed_map = self._parse_profile_metric_map(value_text)
                if key == "values":
                    if parsed_map:
                        profile["values"] = parsed_map
                else:
                    profile.setdefault("arc", {})
                    profile["arc"][key.replace("arc_", "")] = parsed_map
                continue
            if key in self.PROFILE_LIST_FIELDS:
                items = self._split_profile_list_value(value_text)
                profile[key] = items or (["证据不足"] if value_text == "证据不足" else [])
                if key in {"signature_phrases", "sentence_openers", "connective_tokens", "sentence_endings", "forbidden_fillers"}:
                    profile.setdefault("speech_habits", {})
                    profile["speech_habits"][key] = list(profile[key])
                continue
            profile[key] = value_text
            if key == "cadence":
                profile.setdefault("speech_habits", {})
                profile["speech_habits"]["cadence"] = value_text
            elif key in {"anger_style", "joy_style", "grievance_style"}:
                profile.setdefault("emotion_profile", {})
                profile["emotion_profile"][key] = value_text

    def _apply_profile_missing_fallbacks(self, profile: dict[str, Any]) -> None:
        for field in self.PROFILE_COMPLETION_FIELDS:
            if not self._profile_field_is_effectively_empty(profile, field):
                continue
            if field in self.PROFILE_MAP_FIELDS:
                continue
            if field in self.PROFILE_LIST_FIELDS:
                profile[field] = ["证据不足"]
                if field in {"signature_phrases", "sentence_openers", "connective_tokens", "sentence_endings", "forbidden_fillers"}:
                    profile.setdefault("speech_habits", {})
                    profile["speech_habits"][field] = ["证据不足"]
                continue
            profile[field] = "证据不足"
            if field == "cadence":
                profile.setdefault("speech_habits", {})
                profile["speech_habits"]["cadence"] = "证据不足"
            elif field in {"anger_style", "joy_style", "grievance_style"}:
                profile.setdefault("emotion_profile", {})
                profile["emotion_profile"][field] = "证据不足"

    @staticmethod
    def _split_profile_list_value(value: str) -> list[str]:
        text = str(value or "").strip()
        if not text:
            return []
        return [item.strip() for item in re.split(r"\s*[；;]\s*", text) if item.strip()]

    @staticmethod
    def _parse_profile_metric_map(value: str) -> dict[str, Any]:
        text = str(value or "").strip()
        if not text:
            return {}
        parsed: dict[str, Any] = {}
        for part in re.split(r"\s*[；;]\s*", text):
            if "=" not in part:
                continue
            key, raw = part.split("=", 1)
            key_text = key.strip()
            raw_text = raw.strip()
            if not key_text:
                continue
            try:
                parsed[key_text] = int(raw_text)
            except ValueError:
                parsed[key_text] = raw_text
        return parsed

    @staticmethod
    def _profile_list_value(profile: dict[str, Any], key: str) -> list[str]:
        direct = profile.get(key, [])
        if isinstance(direct, list):
            return [str(item).strip() for item in direct if str(item).strip()]
        speech_habits = profile.get("speech_habits", {})
        if isinstance(speech_habits, dict):
            nested = speech_habits.get(key, [])
            if isinstance(nested, list):
                return [str(item).strip() for item in nested if str(item).strip()]
        return []

    @staticmethod
    def _looks_generic_style_scalar(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        generic_tokens = (
            "冷静",
            "克制",
            "温和",
            "直接",
            "理性",
            "简短",
            "平静",
            "含蓄",
            "尖锐",
            "轻声",
        )
        return len(text) <= 8 and any(token in text for token in generic_tokens)

    def _extract_dialogue_evidence(self, payload: dict[str, Any], *, character: str) -> list[str]:
        request = dict(payload.get("request", {}) or {})
        lines: list[str] = []
        for block in [request.get("excerpt", ""), *(dict(request.get("excerpt_stages", {}) or {}).values())]:
            for raw_line in str(block or "").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if character in line or any(token in line for token in ("“", "”", "\"", "道", "说道", "笑道", "问道")):
                    if line not in lines:
                        lines.append(line)
                if len(lines) >= 8:
                    return lines
        return lines

    @staticmethod
    def _looks_like_unstable_profile_scalar(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        if any(token in text for token in ('"', "“", "”", "‘", "’", "「", "」")):
            return True
        if text.endswith(("：", ":", "，", ",", "；", ";", "、")):
            return True
        if len(text) > 46:
            return True
        return bool(
            re.search(
                r"(只见|忽见|回头|转过|只听|听见|听得|说道|笑道|问道|喝道|骂道|叹道|叫道|大家想着|心里还自|拍着手|走了出来|看了.*一眼|旧诗有云|薛蟠)",
                text,
            )
        )

    def _build_distill_repair_messages(
        self,
        payload: dict[str, Any],
        *,
        character: str,
        peer_characters: list[str],
        profile: dict[str, Any],
        issues: list[str],
        completion_issues: list[str] | None = None,
        dialogue_evidence: list[str] | None = None,
    ) -> list[dict[str, str]]:
        base_messages = self._build_distill_llm_messages(payload, character=character, peer_characters=peer_characters)
        draft_markdown = render_profile_md(profile)
        completion_items = list(completion_issues or [])
        repair_instruction = "\n".join(
            [
                "## REPAIR_TASK",
                "你刚刚生成的人物档案里，有少数高风险字段像剧情碎句、叙述片段或未收束结论。",
                "同时，有一批关键字段仍然留空，需要你基于正文证据补齐。",
                "请优先修正这些高风险字段，并补齐列出的空字段，让它们变成稳定、可演绎、能落进人格档案的概括表达。",
                "请保留原档案里其他已经合理的字段，不要整份改写成另一种人格。",
                "补空字段时，不要偷懒留空；只有在正文确实没有稳定证据时，才写“证据不足”。",
                "如果问题落在说话风格，请优先从对白里收束语气、口头禅、起句、收尾和句子节奏，不要只回到抽象标签。",
                "输出仍然必须是完整的 PROFILE.generated.md Markdown，不要解释。",
                "",
                "### HIGH_RISK_FIELDS",
                *([f"- {item}" for item in issues] or ["- 无"]),
                "",
                "### EMPTY_FIELDS_TO_FILL",
                *([f"- {item}" for item in completion_items] or ["- 无"]),
                "",
                "### DIALOGUE_EVIDENCE",
                *([f"- {item}" for item in list(dialogue_evidence or [])] or ["- 证据不足"]),
                "",
                "### CURRENT_DRAFT",
                draft_markdown,
            ]
        ).strip()
        return [
            base_messages[0],
            {"role": "user", "content": f"{base_messages[1]['content']}\n\n{repair_instruction}"},
        ]

    def _build_distill_completion_messages(
        self,
        payload: dict[str, Any],
        *,
        character: str,
        peer_characters: list[str],
        profile: dict[str, Any],
        group_name: str,
        fields: tuple[str, ...],
        dialogue_evidence: list[str] | None = None,
    ) -> list[dict[str, str]]:
        base_messages = self._build_distill_llm_messages(payload, character=character, peer_characters=peer_characters)
        draft_markdown = render_profile_md(profile)
        instruction = "\n".join(
            [
                "## COMPLETION_TASK",
                f"请只补齐这一组字段：{group_name}",
                "你必须只输出下面这些字段的 Markdown 行，每个字段一行，格式严格为 `- field: value`。",
                "不要输出标题，不要输出代码块，不要解释，不要附加其他字段。",
                "列表字段用中文分号 `；` 分隔；`values` / `arc_*` 用 `键=值；键=值`。",
                "如果正文没有稳定证据，不要留空，直接写“证据不足”。",
                "",
                "### TARGET_FIELDS",
                *[f"- {field}" for field in fields],
                "",
                "### DIALOGUE_EVIDENCE",
                *([f"- {item}" for item in list(dialogue_evidence or [])] or ["- 证据不足"]),
                "",
                "### CURRENT_DRAFT",
                draft_markdown,
            ]
        ).strip()
        return [
            base_messages[0],
            {"role": "user", "content": f"{base_messages[1]['content']}\n\n{instruction}"},
        ]

    def _build_relation_llm_messages(
        self,
        payload: dict[str, Any],
        *,
        characters: list[str],
        chunk_label: str = "",
        chunk_index: int = 0,
        chunk_total: int = 0,
        chunk_mode: str = "",
    ) -> list[dict[str, str]]:
        references = dict(payload.get("references", {}) or {})
        request = dict(payload.get("request", {}) or {})
        meta = dict(payload.get("meta", {}) or {})
        relation_request = dict(request)
        relation_request["characters"] = self._normalize_characters(characters)
        system_prompt = str(payload.get("prompt", "")).strip()
        user_parts = [
            "请严格输出一份完整的关系图谱 Markdown。",
            "不要解释，不要输出代码块，不要补充额外前后缀。",
            "只保留当前书段内有明确证据支撑的人物关系。",
            self._build_relation_chunk_guidance(
                chunk_label=chunk_label,
                chunk_index=chunk_index,
                chunk_total=chunk_total,
                chunk_mode=chunk_mode,
            ),
            self._render_payload_section("OUTPUT_SCHEMA", references.get("output_schema", "")),
            self._render_payload_section("LOGIC_CONSTRAINT", references.get("logic_constraint", "")),
            self._render_payload_section("VALIDATION_POLICY", references.get("validation_policy", "")),
            self._render_payload_section("REQUEST", relation_request),
            self._render_payload_section("META", meta),
        ]
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(part for part in user_parts if part).strip()},
        ]

    def _build_relation_merge_messages(
        self,
        payload: dict[str, Any],
        *,
        characters: list[str],
        chunk_drafts: list[dict[str, str]],
        fallback_reason: str = "",
    ) -> list[dict[str, str]]:
        references = dict(payload.get("references", {}) or {})
        request = dict(payload.get("request", {}) or {})
        meta = dict(payload.get("meta", {}) or {})
        relation_request = dict(request)
        relation_request["characters"] = self._normalize_characters(characters)
        relation_request.pop("excerpt", None)
        relation_request.pop("excerpt_stages", None)
        drafts_text = "\n\n".join(
            f"### {item['label']}\n{item['content']}".strip()
            for item in chunk_drafts
            if str(item.get("content", "")).strip()
        ).strip()
        system_prompt = str(payload.get("prompt", "")).strip()
        user_parts = [
            "以下是基于多个证据块得到的局部关系图谱草稿，请整合成唯一一份最终 RELATION_GRAPH Markdown。",
            "去重、纠偏、补足稳定关系；不要保留剧情转述碎句。",
            "若某关系只在单一块中短暂出现且证据弱，可以不保留。",
            "不要解释，不要输出代码块，不要补充额外前后缀。",
            f"补充分批原因参考：{fallback_reason}" if fallback_reason else "",
            self._render_payload_section("OUTPUT_SCHEMA", references.get("output_schema", "")),
            self._render_payload_section("LOGIC_CONSTRAINT", references.get("logic_constraint", "")),
            self._render_payload_section("VALIDATION_POLICY", references.get("validation_policy", "")),
            self._render_payload_section("REQUEST", relation_request),
            self._render_payload_section("CHUNK_DRAFTS", drafts_text or "证据不足"),
            self._render_payload_section("META", meta),
        ]
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(part for part in user_parts if part).strip()},
        ]

    def _build_relation_chunk_payloads(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        request = dict(payload.get("request", {}) or {})
        excerpt = str(request.get("excerpt", "")).strip()
        excerpt_stages = dict(request.get("excerpt_stages", {}) or {})
        chunk_entries: list[dict[str, Any]] = []
        for stage_key, stage_label in (("start", "前段"), ("mid", "中段"), ("end", "后段")):
            stage_text = str(excerpt_stages.get(stage_key, "")).strip()
            if not stage_text:
                continue
            stage_chunks = self._chunk_relation_text(stage_text)
            for index, chunk_text in enumerate(stage_chunks, start=1):
                chunk_request = dict(request)
                chunk_request["excerpt"] = chunk_text
                chunk_request["excerpt_stages"] = {"start": "", "mid": "", "end": ""}
                chunk_request["excerpt_stages"][stage_key] = chunk_text
                chunk_request["excerpt_focus"] = {
                    **dict(request.get("excerpt_focus", {}) or {}),
                    "strategy": "chunked_relation_windows",
                }
                chunk_entries.append(
                    {
                        "label": f"{stage_label}-{index}" if len(stage_chunks) > 1 else stage_label,
                        "payload": {
                            **payload,
                            "request": chunk_request,
                            "meta": {
                                **dict(payload.get("meta", {}) or {}),
                                "chunk_stage": stage_key,
                                "chunk_index": index,
                                "chunk_total": len(stage_chunks),
                            },
                        },
                    }
                )
        if chunk_entries:
            return chunk_entries
        excerpt_chunks = self._chunk_relation_text(excerpt)
        return [
            {
                "label": f"关系块-{index}",
                "payload": {
                    **payload,
                    "request": {
                        **request,
                        "excerpt": chunk_text,
                        "excerpt_stages": {"start": "", "mid": "", "end": ""},
                    },
                    "meta": {
                        **dict(payload.get("meta", {}) or {}),
                        "chunk_index": index,
                        "chunk_total": len(excerpt_chunks),
                    },
                },
            }
            for index, chunk_text in enumerate(excerpt_chunks, start=1)
        ]

    def _should_use_chunked_relation(self, payload: dict[str, Any]) -> bool:
        request = dict(payload.get("request", {}) or {})
        excerpt = str(request.get("excerpt", "")).strip()
        if not excerpt:
            return False
        sentence_count = len(split_sentences(excerpt))
        return len(excerpt) > self.RELATION_CHUNK_TRIGGER_CHARS or sentence_count > self.RELATION_CHUNK_TRIGGER_SENTENCES

    def _chunk_relation_text(self, text: str) -> list[str]:
        clean = str(text or "").strip()
        if not clean:
            return []
        sentences = [item.strip() for item in split_sentences(clean) if item.strip()]
        if not sentences:
            sentences = [item.strip() for item in clean.splitlines() if item.strip()] or [clean]
        chunks: list[str] = []
        current: list[str] = []
        current_chars = 0
        for sentence in sentences:
            units = [sentence[i : i + self.RELATION_CHUNK_MAX_CHARS] for i in range(0, len(sentence), self.RELATION_CHUNK_MAX_CHARS)] or [sentence]
            for unit in units:
                unit = unit.strip()
                if not unit:
                    continue
                projected = current_chars + len(unit) + (1 if current else 0)
                if current and (len(current) >= self.RELATION_CHUNK_MAX_SENTENCES or projected > self.RELATION_CHUNK_MAX_CHARS):
                    chunks.append("\n".join(current).strip())
                    current = []
                    current_chars = 0
                current.append(unit)
                current_chars += len(unit) + (1 if len(current) > 1 else 0)
        if current:
            chunks.append("\n".join(current).strip())
        return [item for item in chunks if item]

    @staticmethod
    def _build_relation_chunk_guidance(
        *,
        chunk_label: str = "",
        chunk_index: int = 0,
        chunk_total: int = 0,
        chunk_mode: str = "",
    ) -> str:
        if not chunk_total:
            return ""
        lines = [
            "## CHUNK_MODE",
            f"- 当前是关系证据块 {chunk_index}/{chunk_total}：{chunk_label or '未命名关系块'}",
            "- 这是分批关系抽取中的局部草稿，请只保留当前证据块里能站得住的关系。",
            "- 不要为了凑完整图谱而硬补没有证据的人物关系。",
        ]
        if chunk_mode == "partial":
            lines.append("- 输出仍然必须是完整 RELATION_GRAPH Markdown，但这是局部草案，后续还会汇总。")
        return "\n".join(lines).strip()

    @staticmethod
    def _build_distill_priority_guidance(character: str) -> str:
        lines = [
            "## PRIORITY_GUIDANCE",
            f"- 先判断 {character} 的核心身份、故事位置、立场锚点，再补深层人格。",
            "- 再判断该角色长期稳定的价值观、信念支点、情绪失控阈值，不要被单一桥段带偏。",
            "- 最后收束到说话风格、典型反应、关系落点与 OOC 边界。",
            "- 如果前期与后期明显变化，请在 timeline_stage / arc_* / contradiction_note 中体现，不要强行揉成一个静态人格。",
            "- 如果同批角色之间容易混淆，优先把差异写在 identity_anchor、soul_goal、belief_anchor、stress_response 上。",
            "",
            "### FIELD_GROUPS",
            "- 第一组：core_identity / story_role / identity_anchor / faction_position / world_belong",
            "- 第二组：soul_goal / worldview / belief_anchor / moral_bottom_line / restraint_threshold",
            "- 第三组：social_mode / stress_response / reward_logic / speech_style / typical_lines / key_bonds",
        ]
        return "\n".join(lines).strip()

    def _build_dialogue_style_guidance(self, request: dict[str, Any], character: str) -> str:
        evidence_lines = self._extract_dialogue_evidence({"request": request}, character=character)
        lines = [
            "## DIALOGUE_STYLE",
            "- 语言风格不要只写抽象词，如“冷静克制”“温柔含蓄”。要尽量落到句子手感上。",
            "- 优先从对白里提取：口头禅、常见起句、连接词、句尾习惯、语气词、代表句。",
            "- 如果没有稳定证据，可以写证据不足；不要硬编不属于这个角色的语气词。",
            "- typical_lines 应尽量保留角色自己的说话味道，不要改写成旁白总结句。",
            "### DIALOGUE_EVIDENCE",
            *([f"- {item}" for item in evidence_lines] or ["- 证据不足"]),
        ]
        return "\n".join(lines).strip()

    @staticmethod
    def _build_excerpt_stage_guidance(excerpt_stages: dict[str, Any]) -> str:
        start = str(excerpt_stages.get("start", "")).strip()
        mid = str(excerpt_stages.get("mid", "")).strip()
        end = str(excerpt_stages.get("end", "")).strip()
        lines = [
            "## EVIDENCE_STAGES",
            "- 请把前段证据更多用于判断初始底色、出身烙印、早期立场。",
            "- 请把中段证据更多用于判断稳定互动模式、冲突升级、关系走向。",
            "- 请把后段证据更多用于判断弧线收束、信念变化、边界是否松动。",
            f"### START\n{start or '证据不足'}",
            f"### MID\n{mid or '证据不足'}",
            f"### END\n{end or '证据不足'}",
        ]
        return "\n".join(lines).strip()

    def _start_background_run(
        self,
        *,
        manifest_path: Path,
        novel_path: Path,
        locked_characters: list[str],
        relation_characters: list[str] | None = None,
        max_sentences: int,
        max_chars: int,
    ) -> None:
        manifest = self._load_manifest(manifest_path) or {}
        manifest["updated_at"] = _utc_now()
        manifest.setdefault("progress", {})["stage"] = "queued"
        manifest["progress"]["message"] = "已开始蒸馏任务"
        manifest.setdefault("summary", {})["status_text"] = "waiting_for_payloads"
        manifest.setdefault("events", []).append(
            {
                "stage": "queued",
                "status": "running",
                "message": "已开始蒸馏任务",
                "character": "",
                "capability": "verify_workflow",
                "timestamp": _utc_now(),
            }
        )
        self._write_json(manifest_path, manifest)

        run_id = str(manifest.get("run_id", "")).strip() or manifest_path.parent.name
        thread = threading.Thread(
            target=self._run_automatic_pipeline_safely,
            kwargs={
                "manifest_path": manifest_path,
                "novel_path": novel_path,
                "run_id": run_id,
                "locked_characters": locked_characters,
                "relation_characters": relation_characters,
                "max_sentences": max_sentences,
                "max_chars": max_chars,
            },
            daemon=True,
        )
        self._active_run_threads[run_id] = thread
        thread.start()

    def _run_automatic_pipeline_safely(self, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "")).strip()
        try:
            self._run_automatic_pipeline(**kwargs)
        except Exception as exc:
            logger.warning("Background distill run failed: %s", exc)
        finally:
            if run_id:
                thread = self._active_run_threads.get(run_id)
                if thread is threading.current_thread():
                    self._active_run_threads.pop(run_id, None)

    def _build_runtime_config_for_run(self, *, run_dir: Path) -> Config:
        model_payload = self._load_model_settings_payload()
        config = Config()
        config.update(
            {
                "llm": {
                    "provider": str(model_payload.get("provider", "")).strip(),
                    "model": str(model_payload.get("model", "")).strip(),
                    "base_url": str(model_payload.get("base_url", "")).strip(),
                    "api_key": str(model_payload.get("api_key", "")).strip(),
                    "max_tokens": int(model_payload.get("max_tokens", 0) or 0),
                    "timeout_seconds": 90,
                    "parallel_chunk_workers": 6,
                    "retry_attempts": 2,
                    "retry_backoff_seconds": 0.75,
                },
                "paths": {
                    "characters": str((run_dir / "artifacts" / "characters").resolve()),
                    "relations": str((run_dir / "artifacts" / "relations").resolve()),
                    "sessions": str((run_dir / "dialogue").resolve()),
                    "corrections": str((run_dir / "corrections").resolve()),
                    "logs": str((run_dir / "logs").resolve()),
                    "rules": str((self.project_root / "rules").resolve()),
                },
            }
        )
        return config

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _normalize_characters(characters: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for item in characters:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            ordered.append(name)
            seen.add(name)
        return ordered

    @staticmethod
    def _decode_base64(value: str) -> bytes:
        try:
            return base64.b64decode(str(value or ""), validate=True)
        except Exception as exc:  # pragma: no cover - exact decoder error is not important
            raise ValueError("Novel content is not valid base64.") from exc

    @classmethod
    def _build_novel_source_entry(
        cls,
        source_path: Path,
        *,
        source_name: str,
        kind: str,
        raw_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        content_bytes = raw_bytes if raw_bytes is not None else source_path.read_bytes()
        return {
            "source_path": str(source_path.resolve()),
            "source_name": str(source_name or source_path.name).strip() or source_path.name,
            "kind": kind,
            "timestamp": _utc_now(),
            "byte_size": len(content_bytes),
            "char_count": cls._estimate_text_length(content_bytes),
        }

    @staticmethod
    def _estimate_text_length(raw_bytes: bytes) -> int:
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
            try:
                return len(raw_bytes.decode(encoding))
            except UnicodeDecodeError:
                continue
        return len(raw_bytes.decode("utf-8", errors="replace"))

    @staticmethod
    def _new_run_id() -> str:
        return f"run-{uuid4().hex[:12]}"

    @staticmethod
    def _is_model_configured_payload(payload: dict[str, Any]) -> bool:
        provider = str(payload.get("provider", "")).strip()
        model = str(payload.get("model", "")).strip()
        api_key = str(payload.get("api_key", "")).strip()
        if not provider or not model:
            return False
        if provider == "ollama":
            return True
        return bool(api_key)

    @staticmethod
    def _read_preview_fields(profile_path: Path) -> dict[str, str]:
        preview: dict[str, str] = {}
        wanted = {"name", "core_identity", "story_role", "soul_goal", "speech_style", "temperament_type"}
        for raw_line in profile_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip()
            if key in wanted and value.strip():
                preview[key] = value.strip()
        return preview

    def _discover_character_cards(self, characters_root: Path | None) -> list[dict[str, Any]]:
        if not characters_root or not characters_root.exists():
            return []
        cards: list[dict[str, Any]] = []
        for persona_dir in sorted(path for path in characters_root.iterdir() if path.is_dir()):
            profile_file = None
            for candidate_name in ("PROFILE.md", "PROFILE.generated.md"):
                candidate = persona_dir / candidate_name
                if candidate.exists():
                    profile_file = candidate
                    break
            if profile_file is None:
                continue
            preview = self._read_preview_fields(profile_file)
            cards.append(
                {
                    "name": persona_dir.name,
                    "persona_dir": str(persona_dir.resolve()),
                    "profile_file": str(profile_file.resolve()),
                    "generated_files": sorted(path.name for path in persona_dir.glob("*.generated.md")),
                    "editable_files": sorted(
                        path.name for path in persona_dir.glob("*.md") if not path.name.endswith(".generated.md")
                    ),
                    "preview": {
                        "core_identity": preview.get("core_identity", ""),
                        "story_role": preview.get("story_role", ""),
                        "soul_goal": preview.get("soul_goal", ""),
                        "speech_style": preview.get("speech_style", ""),
                        "temperament_type": preview.get("temperament_type", ""),
                    },
                }
            )
        return cards

    @staticmethod
    def _split_relation_pair(pair_key: str) -> tuple[str, str]:
        parts = [str(item).strip() for item in str(pair_key or "").split("_") if str(item).strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]
        if parts:
            return parts[0], ""
        return "", ""

    @staticmethod
    def _coerce_relation_evidence(relation: dict[str, Any]) -> list[str]:
        raw = relation.get("evidence_lines", [])
        if isinstance(raw, list):
            lines = [str(item).strip() for item in raw if str(item).strip()]
        else:
            lines = []
        if lines:
            return lines[:3]
        fallback = [
            str(relation.get("typical_interaction", "")).strip(),
            str(relation.get("conflict_point", "")).strip(),
        ]
        return [item for item in fallback if item][:2]

    @staticmethod
    def _relation_type_label(relation: dict[str, Any]) -> str:
        configured = str(relation.get("relationship_type", "")).strip()
        if configured:
            return configured
        trust = int(relation.get("trust", 0) or 0)
        affection = int(relation.get("affection", 0) or 0)
        hostility = int(relation.get("hostility", 0) or 0)
        if hostility >= max(trust, affection) and hostility >= 6:
            return "对立"
        if affection >= 8 and trust >= 7:
            return "深情"
        if trust >= 7:
            return "亲近"
        if hostility >= 4:
            return "拉扯"
        return "牵连"

    def _resolve_persona_dir(self, manifest: dict[str, Any], character: str) -> Path:
        name = str(character or "").strip()
        if not name:
            raise ValueError("Character is required.")
        character_dirs = dict(manifest.get("artifacts", {}).get("character_dirs", {}) or {})
        direct = str(character_dirs.get(name, "")).strip()
        if direct:
            path = Path(direct)
            if path.exists():
                return path
        for item in manifest.get("artifact_index", {}).get("characters", []) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("name", "")).strip() != name:
                continue
            persona_dir = Path(str(item.get("persona_dir", "")).strip())
            if persona_dir.exists():
                return persona_dir
        raise FileNotFoundError(name)

    def _resolve_relations_file(self, manifest: dict[str, Any]) -> Path:
        relation_graph = dict(manifest.get("artifact_index", {}).get("relation_graph", {}) or {})
        relation_path = Path(str(relation_graph.get("relations_file", "")).strip())
        if relation_path.exists():
            return relation_path
        raise FileNotFoundError("relations")

    def _discover_relation_graph(
        self,
        relations_root: Path | None,
        artifact_dir: Path | None,
        run_dir: Path | None,
    ) -> dict[str, str]:
        search_roots = [root for root in (relations_root, artifact_dir, run_dir) if root and root.exists()]
        candidates: dict[str, Path] = {}
        for root in search_roots:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                name = path.name.lower()
                if name.endswith(".html") and "relation" in name:
                    candidates.setdefault("html_path", path)
                elif name.endswith(".svg") and "relation" in name:
                    candidates.setdefault("svg_path", path)
                elif name.endswith(".mermaid.md"):
                    candidates.setdefault("mermaid_path", path)
                elif name.endswith(".status.json") and "relation" in name:
                    candidates.setdefault("relation_status_path", path)
                elif name.endswith(".md") and "relation" in name and not name.endswith(".mermaid.md"):
                    candidates.setdefault("relations_file", path)
        return {key: str(path.resolve()) for key, path in candidates.items()}
