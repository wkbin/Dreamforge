#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from src.core.config import Config
from src.core.cli_app import ZaomengCLI
from src.core.exceptions import ZaomengError
from src.core.host_llm_adapter import HostProvidedLLM
from src.core.runtime_factory import RuntimeDependencyOverrides, build_runtime_parts


class _HostGenerateOnly:
    def __init__(self):
        self.calls = []

    def has_capability(self, name: str) -> bool:
        return name == "llm"

    def generate(self, *, prompt: str, config: dict):
        self.calls.append((prompt, config))
        return {"content": "宿主改写后的回复", "model": "host-model"}


class _HostChatStructuredContent:
    def chat_completion(self, messages, *, model=None, temperature=None, max_tokens=None, stream=False):
        del messages, model, temperature, max_tokens, stream
        return {
            "message": {
                "content": [
                    {"type": "text", "text": "第一句"},
                    {"type": "text", "text": "第二句"},
                ]
            },
            "model": "host-structured",
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        }


class _HostContext:
    def __init__(self, host):
        self.host = host


class HostLLMAdapterTests(unittest.TestCase):
    def test_host_provided_llm_wraps_generate_style_host(self):
        host = _HostGenerateOnly()
        adapter = HostProvidedLLM(host, provider_name="openclaw-host", model_name="host-default")

        result = adapter.chat_completion(
            [{"role": "system", "content": "你是林黛玉"}, {"role": "user", "content": "今日心事如何？"}],
            temperature=0.3,
            max_tokens=80,
        )

        self.assertEqual(result["content"], "宿主改写后的回复")
        self.assertEqual(result["provider"], "openclaw-host")
        self.assertEqual(result["model"], "host-model")
        self.assertEqual(len(host.calls), 1)
        self.assertIn("user: 今日心事如何？", host.calls[0][0])
        self.assertEqual(host.calls[0][1]["temperature"], 0.3)

    def test_from_host_context_uses_context_host(self):
        host = _HostGenerateOnly()
        adapter = HostProvidedLLM.from_host_context(_HostContext(host), provider_name="hermes-host")

        self.assertTrue(adapter.is_generation_enabled())
        self.assertEqual(adapter.get_cost_summary()["provider"], "hermes-host")

    def test_runtime_parts_accept_host_provided_llm_override(self):
        host = _HostGenerateOnly()
        adapter = HostProvidedLLM(host, provider_name="openclaw-host")
        parts = build_runtime_parts(Config(), overrides=RuntimeDependencyOverrides(llm=adapter))

        self.assertIs(parts.llm, adapter)
        self.assertTrue(parts.chat_engine._should_use_llm_generation())

    def test_runtime_parts_build_host_llm_from_context(self):
        host = _HostGenerateOnly()
        parts = build_runtime_parts(Config(), host_context=_HostContext(host), host_llm_provider_name="openclaw-host")

        self.assertIsInstance(parts.llm, HostProvidedLLM)
        self.assertTrue(parts.llm.is_generation_enabled())
        self.assertTrue(parts.chat_engine._should_use_llm_generation())
        self.assertEqual(parts.llm.get_cost_summary()["provider"], "openclaw-host")

    def test_cli_from_host_context_reuses_host_llm(self):
        host = _HostGenerateOnly()
        cli = ZaomengCLI.from_host_context(_HostContext(host), config=Config())

        self.assertIsInstance(cli.parts.llm, HostProvidedLLM)
        self.assertTrue(cli.parts.chat_engine._should_use_llm_generation())

        fresh = cli._fresh_runtime_parts()

        self.assertIsInstance(fresh.llm, HostProvidedLLM)
        self.assertTrue(fresh.chat_engine._should_use_llm_generation())

    def test_cli_requires_llm_for_runtime_commands(self):
        cli = ZaomengCLI(config=Config())

        with self.assertRaises(ZaomengError):
            cli._require_generation_llm(cli.parts, "chat")

    def test_host_chat_completion_parses_structured_message_content(self):
        host = _HostChatStructuredContent()
        adapter = HostProvidedLLM(host, provider_name="openclaw-host", model_name="host-default")

        result = adapter.chat_completion([{"role": "user", "content": "请继续"}])

        self.assertEqual(result["content"], "第一句\n第二句")
        self.assertEqual(result["model"], "host-structured")
        self.assertEqual(result["prompt_tokens"], 12)
        self.assertEqual(result["completion_tokens"], 8)


if __name__ == "__main__":
    unittest.main()
