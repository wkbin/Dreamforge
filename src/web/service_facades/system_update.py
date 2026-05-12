from __future__ import annotations

import json
import shutil
import subprocess
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class UpdateServiceMixin:
    UPDATE_CHECK_TTL_SECONDS = 300
    DEFAULT_REPO_SLUG = "wkbin/zaomeng"
    DEFAULT_REPO_REF = "main"

    def get_app_update_status(self, *, force_check: bool = False) -> dict[str, Any]:
        with self._app_update_lock:
            thread = self._app_update_thread
            if thread and not thread.is_alive():
                self._app_update_thread = None
            if force_check or self._should_refresh_update_status_locked():
                self._refresh_update_status_locked()
            return dict(self._app_update_state)

    def start_app_update(self) -> dict[str, Any]:
        with self._app_update_lock:
            thread = self._app_update_thread
            if thread and thread.is_alive():
                return dict(self._app_update_state)

            self._refresh_update_status_locked(force=True)
            state = dict(self._app_update_state)
            if not state.get("supported", False):
                raise ValueError("当前启动方式暂不支持从 Web UI 直接更新。")
            if not state.get("update_available", False):
                return state

            launcher_path = str(state.get("launcher_path", "")).strip()
            repo_ref = str(state.get("repo_ref", "")).strip() or self.DEFAULT_REPO_REF
            if not launcher_path:
                raise ValueError("没有找到可执行更新的 zaomeng 启动命令。")

            self._app_update_state.update(
                {
                    "status": "updating",
                    "message": "正在下载并安装更新...",
                    "error": "",
                    "started_at": _utc_now(),
                    "completed_at": "",
                    "reload_required": False,
                }
            )
            worker = threading.Thread(
                target=self._run_app_update_task,
                args=(launcher_path, repo_ref),
                name="zaomeng-app-update",
                daemon=True,
            )
            self._app_update_thread = worker
            worker.start()
            return dict(self._app_update_state)

    def _run_app_update_task(self, launcher_path: str, repo_ref: str) -> None:
        command = [launcher_path, "update"]
        if repo_ref:
            command.append(repo_ref)
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            stdout = str(result.stdout or "").strip()
            stderr = str(result.stderr or "").strip()
            with self._app_update_lock:
                if result.returncode != 0:
                    self._app_update_state.update(
                        {
                            "status": "error",
                            "message": "这次自动更新没有成功。",
                            "error": stderr or stdout or f"update exited with code {result.returncode}",
                            "completed_at": _utc_now(),
                            "reload_required": False,
                        }
                    )
                    return
                self._refresh_update_status_locked(force=True)
                self._app_update_state.update(
                    {
                        "status": "completed",
                        "message": "更新已经完成，正在为你准备刷新页面。",
                        "error": "",
                        "completed_at": _utc_now(),
                        "reload_required": True,
                        "last_update_stdout": stdout,
                    }
                )
        except Exception as exc:
            with self._app_update_lock:
                self._app_update_state.update(
                    {
                        "status": "error",
                        "message": "这次自动更新没有成功。",
                        "error": str(exc),
                        "completed_at": _utc_now(),
                        "reload_required": False,
                    }
                )

    def _should_refresh_update_status_locked(self) -> bool:
        status = str(self._app_update_state.get("status", "")).strip()
        if status == "updating":
            return False
        checked_at = str(self._app_update_state.get("checked_at", "")).strip()
        if not checked_at:
            return True
        try:
            checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        return datetime.now(UTC) - checked >= timedelta(seconds=self.UPDATE_CHECK_TTL_SECONDS)

    def _refresh_update_status_locked(self, *, force: bool = False) -> None:
        if not force and not self._should_refresh_update_status_locked():
            return
        launcher = self._discover_launcher_metadata()
        current_version = self._read_local_app_version()
        state: dict[str, Any] = {
            "supported": bool(launcher),
            "status": "idle",
            "message": "",
            "error": "",
            "current_version": current_version,
            "remote_version": "",
            "update_available": False,
            "checked_at": _utc_now(),
            "started_at": str(self._app_update_state.get("started_at", "")).strip(),
            "completed_at": str(self._app_update_state.get("completed_at", "")).strip(),
            "reload_required": False,
            "launcher_path": str((launcher or {}).get("launcher_path", "")).strip(),
            "repo_slug": str((launcher or {}).get("repo_slug", self.DEFAULT_REPO_SLUG)).strip() or self.DEFAULT_REPO_SLUG,
            "repo_ref": str((launcher or {}).get("repo_ref", self.DEFAULT_REPO_REF)).strip() or self.DEFAULT_REPO_REF,
            "last_update_stdout": str(self._app_update_state.get("last_update_stdout", "")).strip(),
        }
        if not launcher:
            state["status"] = "unsupported"
            state["message"] = "当前启动方式暂不支持从 Web UI 直接更新。"
            self._app_update_state = state
            return
        try:
            remote_version = self._fetch_remote_app_version(state["repo_slug"], state["repo_ref"])
        except Exception as exc:
            state["status"] = "error"
            state["message"] = "暂时没连上更新源，稍后可以再试一次。"
            state["error"] = str(exc)
            self._app_update_state = state
            return
        state["remote_version"] = remote_version
        state["update_available"] = bool(current_version and remote_version and current_version != remote_version)
        if state["update_available"]:
            state["message"] = f"发现新版本 {remote_version}，当前是 {current_version}。"
        else:
            state["message"] = "当前已经是最新版本。"
        self._app_update_state = state

    def _read_local_app_version(self) -> str:
        version_path = self.project_root / "src" / "web" / "static" / "version.txt"
        if not version_path.exists():
            return ""
        return version_path.read_text(encoding="utf-8").strip()

    def _discover_launcher_metadata(self) -> dict[str, str] | None:
        install_root = self.project_root.resolve(strict=False)
        candidates: list[Path] = []
        env_launcher = str(getattr(self, "_launcher_path_hint", "") or "").strip()
        if env_launcher:
            candidates.append(Path(env_launcher))
        which_launcher = shutil.which("zaomeng")
        if which_launcher:
            candidates.append(Path(which_launcher))
        candidates.append(Path.home() / ".local" / "bin" / "zaomeng")

        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if not key or key in seen or not candidate.exists():
                continue
            seen.add(key)
            try:
                text = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            install_root_text = self._extract_launcher_value(text, "INSTALL_ROOT")
            if not install_root_text:
                continue
            candidate_root = Path(install_root_text).resolve(strict=False)
            if candidate_root != install_root:
                continue
            return {
                "launcher_path": str(candidate),
                "repo_slug": self._extract_launcher_value(text, "REPO_SLUG") or self.DEFAULT_REPO_SLUG,
                "repo_ref": self._extract_launcher_value(text, "REPO_REF") or self.DEFAULT_REPO_REF,
            }
        return None

    @staticmethod
    def _extract_launcher_value(text: str, key: str) -> str:
        prefix = f'{key}="'
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line.startswith(prefix):
                continue
            return line[len(prefix) :].split('"', 1)[0].strip()
        return ""

    @staticmethod
    def _fetch_remote_app_version(repo_slug: str, repo_ref: str) -> str:
        url = f"https://raw.githubusercontent.com/{repo_slug}/{repo_ref}/src/web/static/version.txt"
        try:
            with urlopen(url, timeout=5) as response:
                return response.read().decode("utf-8").strip()
        except URLError as exc:
            raise ValueError(f"无法获取远端版本信息：{exc}") from exc
