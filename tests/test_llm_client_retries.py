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


if __name__ == "__main__":
    unittest.main()
