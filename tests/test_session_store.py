#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from src.core.config import Config
from src.core.path_provider import PathProvider
from src.core.session_store import MarkdownSessionStore
from src.utils.file_utils import load_markdown_data


class SessionStoreTests(unittest.TestCase):
    def test_markdown_session_store_persists_session_and_relation_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config()
            config.update({"paths": {"sessions": str(root / "sessions")}})
            store = MarkdownSessionStore(PathProvider(config))
            session = {
                "id": "abc123",
                "novel_id": "sanguo",
                "mode": "observe",
                "updated_at": 1234567890,
                "characters": ["刘备", "关羽"],
                "state": {
                    "relations": {
                        "matrix": {"关羽_刘备": {"trust": 9}},
                        "delta": {"关羽_刘备": {"trust": 10}},
                    }
                },
            }

            store.save_session(session)
            store.save_relation_snapshot(session)

            loaded_session = store.load_session("abc123", default=None)
            loaded_snapshot = load_markdown_data(root / "sessions" / "abc123_relations.md", default=None)

            self.assertEqual(loaded_session["id"], "abc123")
            self.assertEqual(loaded_session["novel_id"], "sanguo")
            self.assertEqual(loaded_snapshot["session_id"], "abc123")
            self.assertEqual(loaded_snapshot["relation_matrix"]["关羽_刘备"]["trust"], 9)
            self.assertEqual(loaded_snapshot["relation_delta"]["关羽_刘备"]["trust"], 10)

    def test_session_store_compresses_context_and_supports_long_term_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config()
            config.update({"paths": {"sessions": str(root / "sessions")}})
            store = MarkdownSessionStore(PathProvider(config))
            session = {
                "id": "mem123",
                "novel_id": "hongloumeng",
                "mode": "observe",
                "history": [
                    {"speaker": "林黛玉", "message": f"第{i}句提到了宝玉和心事。", "ts": i}
                    for i in range(32)
                ],
                "state": {"memory": {"summary": {}}},
            }

            updated = store.compress_context(session)
            self.assertLess(len(updated["history"]), 32)
            memory_summary = updated.get("state", {}).get("memory", {}).get("summary", {})
            self.assertTrue(memory_summary.get("summary"))
            self.assertGreater(memory_summary.get("compressed_turns", 0), 0)

            memory_payload = load_markdown_data(root / "sessions" / "mem123_memory.md", default={})
            self.assertGreater(len(memory_payload.get("entries", [])), 0)

            hits = store.search_long_term_memory("mem123", "宝玉 心事", top_k=3)
            self.assertTrue(hits)
            self.assertIn("text", hits[0])

    def test_session_store_search_recomputes_local_vectors_from_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config()
            config.update({"paths": {"sessions": str(root / "sessions")}})
            store = MarkdownSessionStore(PathProvider(config))

            store.append_long_term_memory(
                "mem456",
                "宝玉还惦记着黛玉的心事。",
                metadata={"speaker": "旁白"},
            )
            memory_path = root / "sessions" / "mem456_memory.md"
            payload = load_markdown_data(memory_path, default={})
            payload["entries"][0]["vector"] = [999.0, 1.0, 0.0]
            memory_path.write_text("", encoding="utf-8")
            from src.utils.file_utils import save_markdown_data

            save_markdown_data(memory_path, payload, title="SESSION_LONG_TERM_MEMORY", summary=["- session_id: mem456"])

            hits = store.search_long_term_memory("mem456", "黛玉 心事", top_k=1)
            self.assertTrue(hits)
            self.assertIn("黛玉", hits[0]["text"])

    def test_session_store_compression_prefers_salient_conflict_and_action_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config()
            config.update({"paths": {"sessions": str(root / "sessions")}})
            store = MarkdownSessionStore(PathProvider(config))
            session = {
                "id": "salient123",
                "novel_id": "demo",
                "mode": "observe",
                "history": [
                    {"speaker": "林黛玉", "message": "这只是平常一句闲话。", "ts": 1},
                    {"speaker": "贾宝玉", "message": "我明天会亲自去把这件事说清。", "ts": 2},
                    {"speaker": "林黛玉", "message": "你不要再拿这种话来搪塞我。", "ts": 3},
                    {"speaker": "旁白", "message": "（门忽然被推开，屋里一下静了。）", "ts": 4},
                ]
                + [
                    {"speaker": "袭人", "message": f"普通补充句子{i}", "ts": 10 + i}
                    for i in range(30)
                ],
                "state": {"memory": {"summary": {}}},
            }

            updated = store.compress_context(session, max_recent_turns=8)
            summary = updated["state"]["memory"]["summary"]

            self.assertIn("明天会亲自去把这件事说清", summary.get("summary", ""))
            self.assertTrue(any("不要再拿这种话来搪塞我" in item for item in summary.get("key_points", [])))
            self.assertIn("未完事项", summary.get("summary", ""))
            self.assertIn("冲突张力", summary.get("summary", ""))


if __name__ == "__main__":
    unittest.main()
