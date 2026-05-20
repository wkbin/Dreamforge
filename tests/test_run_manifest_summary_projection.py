#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_state_module():
    module_path = Path("src/web/run_ops/state.py").resolve()
    spec = importlib.util.spec_from_file_location("run_ops_state", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_state = _load_state_module()
derive_summary_graph_status = _state.derive_summary_graph_status
derive_summary_status_text = _state.derive_summary_status_text
project_manifest_summary = _state.project_manifest_summary


class RunManifestSummaryProjectionTests(unittest.TestCase):
    def test_running_payload_ready_projects_waiting_for_host_generation(self):
        manifest = {
            "status": "running",
            "progress": {
                "stage": "relation_payload_ready",
                "completed_count": 0,
                "total_characters": 2,
                "graph_status": "pending",
            },
            "control": {"stop_requested": False},
            "summary": {},
            "locked_characters": ["A", "B"],
        }
        self.assertEqual(derive_summary_status_text(manifest), "waiting_for_host_generation")

    def test_running_with_all_characters_done_and_pending_graph_projects_graph_pending(self):
        manifest = {
            "status": "running",
            "progress": {
                "stage": "distilling",
                "completed_count": 2,
                "total_characters": 2,
                "graph_status": "pending",
            },
            "control": {"stop_requested": False},
            "summary": {},
            "locked_characters": ["A", "B"],
        }
        self.assertEqual(derive_summary_status_text(manifest), "graph_pending")

    def test_ready_projects_workflow_complete(self):
        manifest = {
            "status": "ready",
            "progress": {"graph_status": "complete", "completed_count": 2, "total_characters": 2},
            "control": {"stop_requested": False},
            "summary": {},
            "locked_characters": ["A", "B"],
        }
        self.assertEqual(derive_summary_status_text(manifest), "workflow_complete")
        self.assertEqual(derive_summary_graph_status(manifest), "complete")

    def test_project_summary_writes_consistent_fields(self):
        manifest = {
            "status": "stopped",
            "progress": {"completed_count": 1, "total_characters": 3, "graph_status": "running"},
            "control": {"stop_requested": True},
            "timing": {"elapsed_text": "3分钟"},
            "summary": {},
            "locked_characters": ["A", "B", "C"],
        }
        summary = project_manifest_summary(manifest)
        self.assertEqual(summary["status_text"], "stopped")
        self.assertEqual(summary["graph_status"], "running")
        self.assertEqual(summary["characters_total"], 3)
        self.assertEqual(summary["characters_completed"], 1)
        self.assertEqual(summary["elapsed_text"], "3分钟")


if __name__ == "__main__":
    unittest.main()
