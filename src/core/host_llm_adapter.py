#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from src.core.exceptions import LLMRequestError


class HostProvidedLLM:
    """Adapt a host-provided LLM capability to the local CostEstimator protocol."""

    def __init__(
        self,
        host: Any,
        *,
        provider_name: str = "host-provided",
        model_name: str = "host-default",
        token_counter: Optional[Callable[[str], int]] = None,
    ):
        self.host = host
        self._provider_name = str(provider_name or "host-provided").strip() or "host-provided"
        self._model_name = str(model_name or "host-default").strip() or "host-default"
        self._token_counter = token_counter
        self.session_cost = 0.0
        self.daily_cost = 0.0
        self.request_count = 0
        self.total_tokens = 0

    @classmethod
    def from_host_context(cls, context: Any, **kwargs: Any) -> "HostProvidedLLM":
        host = getattr(context, "host", None)
        if host is None:
            raise ValueError("HostProvidedLLM.from_host_context requires context.host")
        return cls(host, **kwargs)

    def estimate_cost(self, prompt: str, expected_completion_ratio: float = 0.0) -> float:
        del prompt, expected_completion_ratio
        return 0.0

    def is_generation_enabled(self) -> bool:
        return self._host_can_generate()

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        if not self._host_can_generate():
            raise LLMRequestError("Host LLM capability is unavailable.")

        prompt = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
        prompt_tokens = self.count_tokens(prompt)
        start = time.time()
        resolved_model = str(model or self._model_name).strip() or self._model_name

        if hasattr(self.host, "chat_completion"):
            raw = self.host.chat_completion(
                messages,
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )
        elif hasattr(self.host, "generate"):
            raw = self.host.generate(
                prompt=prompt,
                config={
                    "messages": messages,
                    "model": resolved_model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream,
                },
            )
        else:
            raise LLMRequestError("Host object exposes neither chat_completion nor generate.")

        normalized = self._normalize_response(raw, fallback_model=resolved_model)
        completion_tokens = int(normalized.get("completion_tokens", self.count_tokens(normalized.get("content", ""))) or 0)
        self.request_count += 1
        self.total_tokens += prompt_tokens + completion_tokens
        normalized["prompt_tokens"] = int(normalized.get("prompt_tokens", prompt_tokens) or prompt_tokens)
        normalized["completion_tokens"] = completion_tokens
        normalized["elapsed_time"] = float(normalized.get("elapsed_time", time.time() - start) or 0.0)
        normalized["provider"] = self._provider_name
        normalized["model"] = str(normalized.get("model", resolved_model)).strip() or resolved_model
        return normalized

    def get_cost_summary(self) -> Dict[str, Any]:
        return {
            "provider": self._provider_name,
            "session_cost": self.session_cost,
            "daily_cost": self.daily_cost,
            "request_count": self.request_count,
            "total_tokens": self.total_tokens,
        }

    def count_tokens(self, text: str) -> int:
        if self._token_counter is not None:
            return max(0, int(self._token_counter(text)))
        if not text:
            return 0
        return max(1, len(str(text)) // 2)

    def _host_can_generate(self) -> bool:
        if hasattr(self.host, "can_generate"):
            return bool(self.host.can_generate())
        if hasattr(self.host, "has_llm"):
            return bool(self.host.has_llm())
        if hasattr(self.host, "has_capability"):
            return bool(self.host.has_capability("llm"))
        return hasattr(self.host, "chat_completion") or hasattr(self.host, "generate")

    def _normalize_response(self, raw: Any, fallback_model: str) -> Dict[str, Any]:
        if isinstance(raw, dict):
            content = ""
            if isinstance(raw.get("content"), str):
                content = str(raw.get("content", "")).strip()
            elif isinstance(raw.get("message"), dict):
                content = self._extract_text_content(raw.get("message", {}))
            else:
                choices = raw.get("choices", [])
                first = choices[0] if choices else {}
                if isinstance(first, dict) and isinstance(first.get("message"), dict):
                    content = self._extract_text_content(first.get("message", {}))
            usage = raw.get("usage", {}) if isinstance(raw.get("usage", {}), dict) else {}
            return {
                "content": content,
                "model": str(raw.get("model", fallback_model)).strip() or fallback_model,
                "prompt_tokens": int(raw.get("prompt_tokens", usage.get("prompt_tokens", 0)) or 0),
                "completion_tokens": int(raw.get("completion_tokens", usage.get("completion_tokens", 0)) or 0),
                "raw": raw,
            }
        if isinstance(raw, str):
            return {
                "content": raw.strip(),
                "model": fallback_model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "raw": {"content": raw},
            }
        content = str(getattr(raw, "content", "") or "").strip()
        return {
            "content": content,
            "model": fallback_model,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "raw": {"content": content},
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
                    nested = HostProvidedLLM._extract_text_content(text)
                    if nested:
                        return nested
            for key in ("reasoning_content", "reasoning"):
                text = value.get(key)
                if isinstance(text, str) and text.strip():
                    return text.strip()
            return ""
        return str(value or "").strip()
