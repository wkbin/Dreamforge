#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地统计客户端（无模型依赖）
负责 token 估算、费用统计、预算控制
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tiktoken
except Exception:
    tiktoken = None

from .config import Config
from src.utils.file_utils import load_markdown_data, save_markdown_data


class LLMClient:
    """Local usage tracker for compatibility with existing modules."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.cost_config = self.config.get_cost_config()
        self.engine_config = self.config.get("engine", {})

        self.session_cost = 0.0
        self.daily_cost = 0.0
        self.last_reset_date = datetime.now().date()
        self.request_count = 0
        self.total_tokens = 0

        self._load_cost_stats()

        try:
            self.encoder = tiktoken.get_encoding("cl100k_base") if tiktoken else None
        except Exception:
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
            except Exception:
                pass
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
            raise Exception(f"日预算已用完: ${self.daily_cost:.2f} >= ${daily_budget:.2f}")
        threshold = float(self.cost_config.get("warning_threshold", 0.8))
        if self.daily_cost >= daily_budget * threshold:
            remaining = daily_budget - self.daily_cost
            print(f"警告: 日预算已使用 {self.daily_cost / daily_budget * 100:.1f}%")
            print(f"剩余预算: ${remaining:.2f}")

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self.encoder:
            return len(self.encoder.encode(text))
        return max(1, len(text) // 2)

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Local engine pseudo-cost so budget control still works.
        # Can be configured to 0 for completely free mode.
        unit = float(self.engine_config.get("pseudo_cost_per_1k_tokens_usd", 0.001))
        return ((prompt_tokens + completion_tokens) / 1000.0) * unit

    def estimate_cost(self, text: str, expected_completion_ratio: float = 0.5) -> float:
        prompt_tokens = self.count_tokens(text)
        completion_tokens = int(prompt_tokens * expected_completion_ratio)
        return self._calculate_cost(prompt_tokens, completion_tokens)

    def record_usage(self, prompt_tokens: int, completion_tokens: int = 0, elapsed_time: float = 0.0):
        self._check_budget()
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(prompt_tokens, completion_tokens)
        self.session_cost += cost
        self.daily_cost += cost
        self.request_count += 1
        self.total_tokens += total_tokens
        self._save_cost_stats()
        if self.cost_config.get("enable_cost_warning", True):
            print(
                f"[Tokens: {prompt_tokens}+{completion_tokens}={total_tokens}] "
                f"[Cost: ${cost:.4f}] [Time: {elapsed_time:.2f}s]"
            )
            print(f"[Session: ${self.session_cost:.4f}] [Daily: ${self.daily_cost:.4f}]")
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "elapsed_time": elapsed_time,
        }

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        # Compatibility shim: local mode does not call external models.
        start = time.time()
        prompt = "\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in messages)
        prompt_tokens = self.count_tokens(prompt)
        content = "本地模式未启用云模型。请使用规则引擎发言。"
        completion_tokens = self.count_tokens(content)
        usage = self.record_usage(prompt_tokens, completion_tokens, time.time() - start)
        usage["content"] = content
        usage["model"] = "local-rule-engine"
        return usage

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
        }

    def reset_session_cost(self):
        self.session_cost = 0.0
        print("会话成本统计已重置")
