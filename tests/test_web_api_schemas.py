from __future__ import annotations

import unittest

from pydantic import ValidationError

from src.web.api.schemas import CreateRunRequest, DialogueResponseItem, IngestDialogueTurnRequest


class WebApiSchemasTests(unittest.TestCase):
    def test_create_run_request_requires_non_empty_characters(self):
        with self.assertRaises(ValidationError):
            CreateRunRequest(
                novel_name="demo.txt",
                novel_content_base64="ZGVtbw==",
                characters=[],
            )

    def test_ingest_dialogue_turn_request_requires_non_empty_responses(self):
        with self.assertRaises(ValidationError):
            IngestDialogueTurnRequest(responses=[])

    def test_ingest_dialogue_turn_request_accepts_responses(self):
        payload = IngestDialogueTurnRequest(
            responses=[DialogueResponseItem(speaker="林黛玉", message="你来了。")]
        )

        self.assertEqual(len(payload.responses), 1)


if __name__ == "__main__":
    unittest.main()
