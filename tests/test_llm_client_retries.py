#!/usr/bin/env python3

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import error

from src.core.config import Config, clear_config_cache
from src.core.exceptions import LLMRequestError
from src.core.llm_client import LLMClient
from src.utils.file_utils import clear_markdown_data_cache


class _Headers:
    def get_content_charset(self):
        return "utf-8"


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")
        self.headers = _Headers()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class LLMRetryTests(unittest.TestCase):
    def setUp(self):
        clear_config_cache()
        clear_markdown_data_cache()

    def tearDown(self):
        clear_config_cache()
        clear_markdown_data_cache()

    def _make_client(self) -> LLMClient:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config_path = Path(tmp.name) / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "llm:",
                    "  provider: openai",
                    "  model: gpt-test",
                    "  api_key: test-key",
                    "  retry_attempts: 3",
                    "  retry_backoff_seconds: 0.01",
                    "  retry_backoff_multiplier: 2",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return LLMClient(Config(str(config_path)))

    def _make_local_client(self) -> LLMClient:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config_path = Path(tmp.name) / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "llm:",
                    "  provider: local-rule-engine",
                    "  model: local-rule-engine",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return LLMClient(Config(str(config_path)))

    def test_default_config_prefers_auto_provider(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config_path = Path(tmp.name) / "config.yaml"
        config_path.write_text("", encoding="utf-8")

        client = LLMClient(Config(str(config_path)))

        self.assertEqual(client.llm_config.get("provider"), "auto")
        self.assertEqual(client.provider_name(), "local-rule-engine")

    def test_post_json_retries_url_errors_then_succeeds(self):
        client = self._make_client()
        with patch(
            "src.core.llm_client.request.urlopen",
            side_effect=[error.URLError("temporary"), _Response({"ok": True})],
        ) as urlopen, patch("src.core.llm_client.time.sleep") as sleep:
            result = client._post_json(url="https://example.test", payload={"ping": "pong"})

        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(0.01)

    def test_post_json_wraps_connection_reset_as_llm_request_error(self):
        client = self._make_client()
        with patch(
            "src.core.llm_client.request.urlopen",
            side_effect=ConnectionResetError("[WinError 10054] remote host closed connection"),
        ) as urlopen, patch("src.core.llm_client.time.sleep") as sleep:
            with self.assertRaises(LLMRequestError) as ctx:
                client._post_json(url="https://example.test", payload={"ping": "pong"})

        self.assertIn("LLM 连接失败", str(ctx.exception))
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_post_json_does_not_retry_non_retryable_http_errors(self):
        client = self._make_client()
        http_error = error.HTTPError(
            url="https://example.test",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"bad request"}'),
        )
        with patch("src.core.llm_client.request.urlopen", side_effect=http_error) as urlopen, patch(
            "src.core.llm_client.time.sleep"
        ) as sleep:
            with self.assertRaises(LLMRequestError):
                client._post_json(url="https://example.test", payload={"ping": "pong"})

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_local_provider_auto_promotes_to_openai_when_env_key_exists(self):
        client = self._make_local_client()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}, clear=False):
            self.assertEqual(client.provider_name(), "openai")
            self.assertTrue(client.is_generation_enabled())
            self.assertEqual(client._resolve_model_name(client.provider_name()), "gpt-4.1-mini")

    def test_local_provider_uses_env_model_for_ollama(self):
        client = self._make_local_client()
        with patch.dict("os.environ", {"OLLAMA_MODEL": "qwen2.5:14b"}, clear=False):
            self.assertEqual(client.provider_name(), "ollama")
            self.assertEqual(client._resolve_model_name("ollama"), "qwen2.5:14b")

    def test_host_bridge_has_highest_auto_detection_priority(self):
        client = self._make_local_client()
        with patch.dict(
            "os.environ",
            {
                "ZAOMENG_HOST_BRIDGE_URL": "http://127.0.0.1:8765",
                "OPENAI_API_KEY": "env-key",
            },
            clear=False,
        ):
            self.assertEqual(client.provider_name(), "host-bridge")
            self.assertEqual(client._resolve_model_name("host-bridge"), "host-default")
            self.assertEqual(client._resolve_host_bridge_url(), "http://127.0.0.1:8765/chat/completions")

    def test_host_bridge_parses_simple_bridge_payload(self):
        client = self._make_local_client()
        with patch.dict("os.environ", {"ZAOMENG_HOST_BRIDGE_URL": "http://127.0.0.1:8765"}, clear=False), patch(
            "src.core.llm_client.request.urlopen",
            return_value=_Response(
                {
                    "content": "桥接回复",
                    "model": "host-llm",
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                }
            ),
        ):
            result = client.chat_completion([{"role": "user", "content": "你好"}])

        self.assertEqual(result["provider"], "host-bridge")
        self.assertEqual(result["content"], "桥接回复")
        self.assertEqual(result["model"], "host-llm")


    def test_openai_like_extracts_text_from_content_parts(self):
        client = self._make_client()
        with patch(
            "src.core.llm_client.request.urlopen",
            return_value=_Response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "text", "text": "???"},
                                    {"type": "text", "text": "???"},
                                ]
                            }
                        }
                    ],
                    "model": "gpt-test",
                    "usage": {"prompt_tokens": 3, "completion_tokens": 5},
                }
            ),
        ):
            result = client.chat_completion([{"role": "user", "content": "??"}])

        self.assertEqual(result["content"], "???\n???")


if __name__ == "__main__":
    unittest.main()
