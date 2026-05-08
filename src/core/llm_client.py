#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM client with local fallback.

Responsibilities:
- token estimation
- cost/budget tracking
- provider-aware chat completion
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request

try:
    import tiktoken
except ImportError:
    tiktoken = None

from .config import Config
from .exceptions import BudgetExceededError, LLMRequestError, MissingAPIKeyError
from src.utils.file_utils import load_markdown_data, save_markdown_data


logger = logging.getLogger(__name__)


class LLMClient:
    """Provider-aware chat client with automatic host/env detection."""

    HOST_BRIDGE_ENV_URL = "ZAOMENG_HOST_BRIDGE_URL"
    HOST_BRIDGE_ENV_MODEL = "ZAOMENG_HOST_BRIDGE_MODEL"
    HOST_BRIDGE_ENV_TOKEN = "ZAOMENG_HOST_BRIDGE_TOKEN"
    DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
    DEFAULT_HOST_BRIDGE_PATH = "/chat/completions"
    DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
    DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
    DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"
    DEFAULT_HOST_BRIDGE_MODEL = "host-default"
    AUTO_PROVIDER = "auto"
    LOCAL_PROVIDER = "local-rule-engine"
    DEFAULT_RETRY_STATUS_CODES = (408, 429, 500, 502, 503, 504)

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.cost_config = self.config.get_cost_config()
        self.engine_config = self.config.get("engine", {})
        self.llm_config = self.config.get_llm_config()

        self.session_cost = 0.0
        self.daily_cost = 0.0
        self.last_reset_date = datetime.now().date()
        self.request_count = 0
        self.total_tokens = 0
        self._usage_lock = threading.Lock()

        self._load_cost_stats()

        try:
            self.encoder = tiktoken.get_encoding("cl100k_base") if tiktoken else None
        except Exception as exc:  # pragma: no cover - depends on local tiktoken/network state
            logger.warning("Failed to initialize tiktoken encoder, falling back to heuristic token counting: %s", exc)
            self.encoder = None

    def _load_cost_stats(self):
        stats_file = Path(self.config.project_root) / "data" / "cost_stats.md"
        if stats_file.exists():
            try:
                data = load_markdown_data(stats_file, default={}) or {}
                self.daily_cost = float(data.get("daily_cost", 0.0))
                last = data.get("last_reset_date")
                if last:
                    self.last_reset_date = datetime.fromisoformat(last).date()
            except (OSError, TypeError, ValueError) as exc:
                logger.warning("Failed to load cost stats from %s: %s", stats_file, exc)
        self._check_reset_daily()

    def _save_cost_stats(self):
        stats_file = Path(self.config.project_root) / "data" / "cost_stats.md"
        payload = {
            "daily_cost": self.daily_cost,
            "last_reset_date": self.last_reset_date.isoformat(),
            "total_requests": self.request_count,
            "total_tokens": self.total_tokens,
        }
        save_markdown_data(
            stats_file,
            payload,
            title="COST_STATS",
            summary=[
                f"- daily_cost: {self.daily_cost}",
                f"- total_requests: {self.request_count}",
                f"- total_tokens: {self.total_tokens}",
            ],
        )

    def _check_reset_daily(self):
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_cost = 0.0
            self.last_reset_date = today
            self._save_cost_stats()

    def _check_budget(self):
        daily_budget = float(self.cost_config.get("daily_budget_usd", 10.0))
        if self.daily_cost >= daily_budget:
            raise BudgetExceededError(f"日预算已用完: ${self.daily_cost:.2f} >= ${daily_budget:.2f}")
        threshold = float(self.cost_config.get("warning_threshold", 0.8))
        if self.daily_cost >= daily_budget * threshold:
            remaining = daily_budget - self.daily_cost
            logger.warning("警告: 日预算已使用 %.1f%%", self.daily_cost / daily_budget * 100)
            logger.warning("剩余预算: $%.2f", remaining)

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self.encoder:
            return len(self.encoder.encode(text))
        return max(1, len(text) // 2)

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        unit = float(self.engine_config.get("pseudo_cost_per_1k_tokens_usd", 0.001))
        return ((prompt_tokens + completion_tokens) / 1000.0) * unit

    def estimate_cost(self, text: str, expected_completion_ratio: float = 0.5) -> float:
        prompt_tokens = self.count_tokens(text)
        completion_tokens = int(prompt_tokens * expected_completion_ratio)
        return self._calculate_cost(prompt_tokens, completion_tokens)

    def record_usage(self, prompt_tokens: int, completion_tokens: int = 0, elapsed_time: float = 0.0):
        with self._usage_lock:
            self._check_budget()
            total_tokens = prompt_tokens + completion_tokens
            cost = self._calculate_cost(prompt_tokens, completion_tokens)
            self.session_cost += cost
            self.daily_cost += cost
            self.request_count += 1
            self.total_tokens += total_tokens
            self._save_cost_stats()
        if self.cost_config.get("enable_cost_warning", True):
            logger.info(
                f"[Tokens: {prompt_tokens}+{completion_tokens}={total_tokens}] "
                f"[Cost: ${cost:.4f}] [Time: {elapsed_time:.2f}s]"
            )
            logger.info("[Session: $%.4f] [Daily: $%.4f]", self.session_cost, self.daily_cost)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "elapsed_time": elapsed_time,
        }

    def provider_name(self) -> str:
        configured = str(self.llm_config.get("provider", self.AUTO_PROVIDER)).strip().lower()
        if configured and configured not in {self.AUTO_PROVIDER, self.LOCAL_PROVIDER}:
            return configured
        return self._infer_provider_from_environment()

    def is_generation_enabled(self) -> bool:
        return self.provider_name() != self.LOCAL_PROVIDER

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        del stream  # streaming is not implemented in this client.

        provider = self.provider_name()
        start = time.time()
        prompt = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
        prompt_tokens = self.count_tokens(prompt)

        if provider == self.LOCAL_PROVIDER:
            content = "本地模式未启用云模型。请使用规则引擎发言。"
            completion_tokens = self.count_tokens(content)
            usage = self.record_usage(prompt_tokens, completion_tokens, time.time() - start)
            usage["content"] = content
            usage["model"] = self.LOCAL_PROVIDER
            usage["provider"] = provider
            return usage

        result = self._dispatch_chat_completion(
            provider=provider,
            messages=messages,
            model=self._resolve_model_name(provider, model),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        prompt_usage = int(result.get("prompt_tokens", prompt_tokens))
        completion_usage = int(result.get("completion_tokens", self.count_tokens(result.get("content", ""))))
        usage = self.record_usage(prompt_usage, completion_usage, time.time() - start)
        usage["content"] = result.get("content", "")
        usage["model"] = result.get("model", model or self.llm_config.get("model", ""))
        usage["provider"] = provider
        usage["raw"] = result.get("raw", {})
        return usage

    def _infer_provider_from_environment(self) -> str:
        if self._host_bridge_url():
            return "host-bridge"
        if str(os.getenv("OPENAI_API_KEY", "")).strip():
            base_url = str(os.getenv("OPENAI_BASE_URL", "")).strip()
            return "openai-compatible" if base_url else "openai"
        if str(os.getenv("ANTHROPIC_API_KEY", "")).strip():
            return "anthropic"
        if str(os.getenv("OLLAMA_MODEL", "")).strip():
            return "ollama"
        return self.LOCAL_PROVIDER

    def _resolve_model_name(self, provider: str, requested_model: Optional[str] = None) -> str:
        configured = str(requested_model or self.llm_config.get("model", "")).strip()
        if configured and configured != self.LOCAL_PROVIDER:
            return configured
        env_overrides = {
            "host-bridge": (self.HOST_BRIDGE_ENV_MODEL,),
            "openai": ("OPENAI_MODEL",),
            "openai-compatible": ("OPENAI_MODEL",),
            "anthropic": ("ANTHROPIC_MODEL",),
            "ollama": ("OLLAMA_MODEL",),
        }
        for env_name in env_overrides.get(provider, ()):
            value = str(os.getenv(env_name, "")).strip()
            if value:
                return value
        defaults = {
            "host-bridge": self.DEFAULT_HOST_BRIDGE_MODEL,
            "openai": self.DEFAULT_OPENAI_MODEL,
            "openai-compatible": self.DEFAULT_OPENAI_MODEL,
            "anthropic": self.DEFAULT_ANTHROPIC_MODEL,
            "ollama": self.DEFAULT_OLLAMA_MODEL,
        }
        return defaults.get(provider, configured or self.LOCAL_PROVIDER)

    def _dispatch_chat_completion(
        self,
        *,
        provider: str,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        if provider in {"openai", "openai-compatible"}:
            return self._chat_openai_like(
                provider=provider,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if provider == "anthropic":
            return self._chat_anthropic(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if provider == "host-bridge":
            return self._chat_host_bridge(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if provider == "ollama":
            return self._chat_ollama(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        raise ValueError(f"Unsupported llm.provider: {provider}")

    def _chat_openai_like(
        self,
        *,
        provider: str,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        api_key = self._resolve_api_key(provider)
        base_url = self._resolve_base_url(provider)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self._resolve_temperature(temperature),
        }
        resolved_max_tokens = self._resolve_max_tokens(max_tokens)
        if resolved_max_tokens:
            payload["max_tokens"] = resolved_max_tokens

        data = self._post_json(
            url=self._endpoint(base_url, "/chat/completions"),
            payload=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
            },
        )
        choices = data.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        usage = data.get("usage", {})
        return {
            "content": self._extract_text_content(message),
            "model": data.get("model", model),
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "raw": data,
        }

    def _chat_anthropic(
        self,
        *,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        api_key = self._resolve_api_key("anthropic")
        base_url = self._resolve_base_url("anthropic")
        system_parts: List[str] = []
        chat_messages: List[Dict[str, str]] = []
        for item in messages:
            role = str(item.get("role", "user")).strip()
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
            else:
                chat_messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})
        payload: Dict[str, Any] = {
            "model": model,
            "messages": chat_messages,
            "temperature": self._resolve_temperature(temperature),
            "max_tokens": self._resolve_max_tokens(max_tokens, default=512),
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        data = self._post_json(
            url=self._endpoint(base_url, "/messages"),
            payload=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        content_blocks = data.get("content", [])
        content = ""
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                content += str(block.get("text", ""))
        usage = data.get("usage", {})
        return {
            "content": content.strip(),
            "model": data.get("model", model),
            "prompt_tokens": int(usage.get("input_tokens", 0)),
            "completion_tokens": int(usage.get("output_tokens", 0)),
            "raw": data,
        }

    def _chat_ollama(
        self,
        *,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        base_url = self._resolve_base_url("ollama")
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._resolve_temperature(temperature),
            },
        }
        resolved_max_tokens = self._resolve_max_tokens(max_tokens)
        if resolved_max_tokens:
            payload["options"]["num_predict"] = resolved_max_tokens

        data = self._post_json(
            url=self._endpoint(base_url, "/api/chat"),
            payload=payload,
        )
        message = data.get("message", {}) if isinstance(data.get("message", {}), dict) else {}
        prompt_tokens = int(data.get("prompt_eval_count", 0))
        completion_tokens = int(data.get("eval_count", 0))
        return {
            "content": self._extract_text_content(message),
            "model": data.get("model", model),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "raw": data,
        }

    @staticmethod
    def _extract_text_content(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        parts.append(text)
                elif isinstance(item, dict):
                    text = str(item.get("text", "") or item.get("content", "")).strip()
                    if text:
                        parts.append(text)
            return "\n".join(parts).strip()
        if isinstance(value, dict):
            for key in ("content", "text", "output_text"):
                text = value.get(key)
                if isinstance(text, str) and text.strip():
                    return text.strip()
                if isinstance(text, list):
                    nested = LLMClient._extract_text_content(text)
                    if nested:
                        return nested
            for key in ("reasoning_content", "reasoning"):
                text = value.get(key)
                if isinstance(text, str) and text.strip():
                    return text.strip()
            return ""
        return str(value or "").strip()

    def _chat_host_bridge(
        self,
        *,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        url = self._resolve_host_bridge_url()
        payload: Dict[str, Any] = {
            "messages": messages,
            "model": model,
            "temperature": self._resolve_temperature(temperature),
            "max_tokens": self._resolve_max_tokens(max_tokens, default=512),
            "provider": "host-bridge",
            "metadata": {
                "source": "zaomeng",
                "configured_provider": str(self.llm_config.get("provider", self.LOCAL_PROVIDER)).strip().lower(),
            },
        }
        headers: Dict[str, str] = {}
        token = self._resolve_host_bridge_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["X-Zaomeng-Bridge-Token"] = token
        data = self._post_json(url=url, payload=payload, headers=headers or None)
        return self._normalize_host_bridge_response(data, fallback_model=model)

    def _post_json(self, *, url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        request_headers = {
            "Content-Type": "application/json",
        }
        if headers:
            request_headers.update(headers)

        timeout = float(self.llm_config.get("timeout_seconds", 120) or 120)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url=url, data=body, headers=request_headers, method="POST")
        attempts = self._retry_attempts()
        retry_status_codes = self._retry_status_codes()
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                with request.urlopen(req, timeout=timeout) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    body_text = resp.read().decode(charset)
                    return json.loads(body_text)
            except error.HTTPError as exc:
                body_text = exc.read().decode("utf-8", errors="replace")
                last_error = exc
                if attempt < attempts and exc.code in retry_status_codes:
                    self._sleep_before_retry(attempt, f"HTTP {exc.code} {exc.reason}")
                    continue
                raise LLMRequestError(f"LLM 请求失败: {exc.code} {exc.reason} | {body_text}") from exc
            except error.URLError as exc:
                last_error = exc
                if attempt < attempts:
                    self._sleep_before_retry(attempt, f"connection error: {exc.reason}")
                    continue
                raise LLMRequestError(f"LLM 连接失败: {exc.reason}") from exc
            except OSError as exc:
                last_error = exc
                if attempt < attempts:
                    self._sleep_before_retry(attempt, f"socket error: {exc}")
                    continue
                raise LLMRequestError(f"LLM 连接失败: {exc}") from exc
            except json.JSONDecodeError as exc:
                raise LLMRequestError("LLM 返回了无法解析的 JSON 响应") from exc

        raise LLMRequestError(f"LLM 请求失败: {last_error}") from last_error

    def _retry_attempts(self) -> int:
        return max(1, int(self.llm_config.get("retry_attempts", 3) or 1))

    def _retry_backoff_seconds(self) -> float:
        return max(0.0, float(self.llm_config.get("retry_backoff_seconds", 1.0) or 0.0))

    def _retry_backoff_multiplier(self) -> float:
        return max(1.0, float(self.llm_config.get("retry_backoff_multiplier", 2.0) or 1.0))

    def _retry_status_codes(self) -> set[int]:
        configured = self.llm_config.get("retry_status_codes", self.DEFAULT_RETRY_STATUS_CODES)
        if not isinstance(configured, (list, tuple, set)):
            configured = self.DEFAULT_RETRY_STATUS_CODES
        return {int(code) for code in configured}

    def _sleep_before_retry(self, attempt: int, reason: str) -> None:
        delay = self._retry_backoff_seconds() * (self._retry_backoff_multiplier() ** (attempt - 1))
        if delay <= 0:
            return
        logger.warning(
            "LLM request retry %s/%s after %s (sleep %.2fs)",
            attempt,
            self._retry_attempts() - 1,
            reason,
            delay,
        )
        time.sleep(delay)

    def _resolve_api_key(self, provider: str) -> str:
        configured = str(self.llm_config.get("api_key", "")).strip()
        if configured:
            return configured

        explicit_env = str(self.llm_config.get("api_key_env", "")).strip()
        if explicit_env and os.getenv(explicit_env):
            return str(os.getenv(explicit_env, "")).strip()

        fallback_envs = {
            "openai": ("OPENAI_API_KEY",),
            "openai-compatible": ("OPENAI_API_KEY",),
            "anthropic": ("ANTHROPIC_API_KEY",),
        }
        for env_name in fallback_envs.get(provider, ()):
            value = str(os.getenv(env_name, "")).strip()
            if value:
                return value

        raise MissingAPIKeyError(f"{provider} provider 缺少 API key，请在 config.yaml 或环境变量中配置。")

    def _resolve_base_url(self, provider: str) -> str:
        configured = str(self.llm_config.get("base_url", "")).strip()
        if configured:
            return configured.rstrip("/")

        defaults = {
            "openai": self.DEFAULT_OPENAI_BASE_URL,
            "openai-compatible": self.DEFAULT_OPENAI_BASE_URL,
            "anthropic": self.DEFAULT_ANTHROPIC_BASE_URL,
            "ollama": self.DEFAULT_OLLAMA_BASE_URL,
        }
        return defaults.get(provider, self.DEFAULT_OPENAI_BASE_URL)

    def _host_bridge_url(self) -> str:
        configured = str(self.llm_config.get("host_bridge_url", "")).strip()
        if configured:
            return configured
        configured_base = str(self.llm_config.get("base_url", "")).strip()
        if str(self.llm_config.get("provider", "")).strip().lower() == "host-bridge" and configured_base:
            return configured_base
        return str(os.getenv(self.HOST_BRIDGE_ENV_URL, "")).strip()

    def _resolve_host_bridge_url(self) -> str:
        configured = self._host_bridge_url()
        if not configured:
            raise LLMRequestError(
                "host-bridge provider 已启用，但未提供 bridge URL。请配置 llm.host_bridge_url 或环境变量 "
                f"{self.HOST_BRIDGE_ENV_URL}。"
            )
        if "://" not in configured:
            configured = f"http://{configured.lstrip('/')}"
        if configured.endswith(("/chat/completions", "/api/chat", "/v1/chat/completions")):
            return configured
        return configured.rstrip("/") + self.DEFAULT_HOST_BRIDGE_PATH

    def _resolve_host_bridge_token(self) -> str:
        configured = str(self.llm_config.get("host_bridge_token", "")).strip()
        if configured:
            return configured
        explicit_env = str(self.llm_config.get("host_bridge_token_env", "")).strip()
        if explicit_env and os.getenv(explicit_env):
            return str(os.getenv(explicit_env, "")).strip()
        return str(os.getenv(self.HOST_BRIDGE_ENV_TOKEN, "")).strip()

    def _resolve_temperature(self, temperature: Optional[float]) -> float:
        if temperature is not None:
            return float(temperature)
        return float(self.llm_config.get("temperature", 0.2) or 0.2)

    def _resolve_max_tokens(self, max_tokens: Optional[int], default: int = 0) -> int:
        if max_tokens is not None:
            return int(max_tokens)
        configured = int(self.llm_config.get("max_tokens", default) or default)
        return configured

    def _normalize_host_bridge_response(self, data: Dict[str, Any], fallback_model: str) -> Dict[str, Any]:
        content = ""
        if isinstance(data.get("content"), str):
            content = str(data.get("content", "")).strip()
        elif isinstance(data.get("message"), dict):
            content = str(data.get("message", {}).get("content", "")).strip()
        else:
            choices = data.get("choices", [])
            first = choices[0] if choices else {}
            if isinstance(first, dict):
                message = first.get("message", {})
                if isinstance(message, dict):
                    content = str(message.get("content", "")).strip()

        usage = data.get("usage", {}) if isinstance(data.get("usage", {}), dict) else {}
        return {
            "content": content,
            "model": str(data.get("model", fallback_model)).strip() or fallback_model,
            "prompt_tokens": int(data.get("prompt_tokens", usage.get("prompt_tokens", 0)) or 0),
            "completion_tokens": int(data.get("completion_tokens", usage.get("completion_tokens", 0)) or 0),
            "raw": data,
        }

    @staticmethod
    def _endpoint(base_url: str, suffix: str) -> str:
        if base_url.endswith(suffix):
            return base_url
        return f"{base_url.rstrip('/')}{suffix}"

    def get_cost_summary(self) -> Dict[str, Any]:
        daily_budget = float(self.cost_config.get("daily_budget_usd", 10.0))
        remaining_budget = max(0.0, daily_budget - self.daily_cost)
        return {
            "session_cost": self.session_cost,
            "daily_cost": self.daily_cost,
            "daily_budget": daily_budget,
            "remaining_budget": remaining_budget,
            "budget_usage_percent": (self.daily_cost / daily_budget * 100) if daily_budget > 0 else 0,
            "request_count": self.request_count,
            "total_tokens": self.total_tokens,
            "provider": self.provider_name(),
        }

    def reset_session_cost(self):
        self.session_cost = 0.0
        logger.info("会话成本统计已重置")
