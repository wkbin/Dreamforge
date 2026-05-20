from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def _load_compat_module():
    module_path = Path("src/web/manifest/compat.py").resolve()
    spec = importlib.util.spec_from_file_location("manifest_compat", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_compat = _load_compat_module()
apply_imported_run_semantics = _compat.apply_imported_run_semantics
coerce_manifest_path = _compat.coerce_manifest_path
relative_to_run_dir = _compat.relative_to_run_dir
rewrite_run_root_paths = _compat.rewrite_run_root_paths
rewrite_string_path = _compat.rewrite_string_path
reconcile_discovered_artifacts = _compat.reconcile_discovered_artifacts


class ManifestCompatTests(unittest.TestCase):
    def test_coerce_manifest_path_ignores_non_path_legacy_values(self):
        self.assertIsNone(coerce_manifest_path({"a": "b"}))
        self.assertIsNone(coerce_manifest_path(["a", "b"]))
        self.assertIsNone(coerce_manifest_path(""))

    def test_coerce_manifest_path_tolerates_os_errors(self):
        too_long = "x" * 5000
        self.assertIsNone(coerce_manifest_path(too_long))

    def test_relative_to_run_dir_accepts_casefolded_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "runs" / "run-demo"
            nested = run_dir / "dialogue" / "dlg-1" / "turns" / "turn-1.payload.json"
            nested.parent.mkdir(parents=True, exist_ok=True)
            nested.write_text("{}", encoding="utf-8")

            relative = relative_to_run_dir(nested, Path(str(run_dir).upper()))

            self.assertEqual(relative, Path("dialogue") / "dlg-1" / "turns" / "turn-1.payload.json")

    def test_rewrite_string_path_accepts_mixed_windows_slashes(self):
        source_root = Path(r"D:\work2\Dreamforge\.zaomeng-web\runs\run-old")
        target_root = Path(r"/tmp/zaomeng/runs/run-new")

        rewritten = rewrite_string_path(
            r"D:/work2/Dreamforge/.zaomeng-web/runs/run-old\payloads\distill_王熙凤.json",
            source_root=source_root,
            target_root=target_root,
        )

        self.assertIn("/tmp/zaomeng/runs/run-new", rewritten.replace("\\", "/"))
        self.assertTrue(rewritten.replace("\\", "/").endswith("/payloads/distill_王熙凤.json"))

    def test_rewrite_run_root_paths_walks_nested_manifest_shapes(self):
        source_root = Path(r"D:\work2\Dreamforge\.zaomeng-web\runs\run-old")
        target_root = Path(r"/tmp/zaomeng/runs/run-new")
        payload = {
            "webui": {"run_dir": str(source_root)},
            "artifact_index": {
                "characters": [
                    {"name": "王熙凤", "profile_file": str(source_root / "artifacts" / "characters" / "demo" / "王熙凤" / "PROFILE.generated.md")}
                ]
            },
            "artifacts": {
                "payloads": {
                    "distill_王熙凤": str(source_root / "payloads" / "distill_王熙凤.json"),
                }
            },
        }

        rewritten = rewrite_run_root_paths(payload, source_root=source_root, target_root=target_root)

        self.assertEqual(rewritten["webui"]["run_dir"], str(target_root))
        self.assertIn(str(target_root), rewritten["artifact_index"]["characters"][0]["profile_file"])
        self.assertIn(str(target_root), rewritten["artifacts"]["payloads"]["distill_王熙凤"])

    def test_reconcile_discovered_artifacts_clears_stale_relation_graph_when_missing(self):
        manifest = {
            "locked_characters": ["甲", "乙"],
            "artifacts": {"relation_graph": {"relations_file": "/old/relation.md"}},
            "artifact_index": {
                "characters": [{"name": "甲", "persona_dir": "/old/a"}],
                "relation_graph": {"relations_file": "/old/relation.md"},
            },
            "progress": {"graph_status": "complete", "completed_characters": ["甲"], "completed_count": 1},
        }

        updated = reconcile_discovered_artifacts(
            manifest,
            character_index=[],
            relation_graph=None,
        )

        self.assertEqual(updated["artifact_index"]["characters"], [])
        self.assertEqual(updated["artifacts"]["character_dirs"], {})
        self.assertEqual(updated["artifacts"]["relation_graph"], {})
        self.assertEqual(updated["artifact_index"]["relation_graph"], {})
        self.assertEqual(updated["progress"]["completed_characters"], [])
        self.assertEqual(updated["progress"]["completed_count"], 0)
        self.assertEqual(updated["progress"]["graph_status"], "pending")

    def test_reconcile_discovered_artifacts_preserves_failed_graph_status_when_missing(self):
        manifest = {
            "progress": {"graph_status": "failed"},
            "artifacts": {"relation_graph": {"relations_file": "/old/relation.md"}},
            "artifact_index": {"relation_graph": {"relations_file": "/old/relation.md"}},
        }

        updated = reconcile_discovered_artifacts(
            manifest,
            character_index=[],
            relation_graph=None,
        )

        self.assertEqual(updated["progress"]["graph_status"], "failed")
        self.assertEqual(updated["artifacts"]["relation_graph"], {})
        self.assertEqual(updated["artifact_index"]["relation_graph"], {})

    def test_reconcile_discovered_artifacts_filters_missing_payload_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing_payload = Path(tmp) / "payload.json"
            existing_payload.write_text("{}", encoding="utf-8")
            manifest = {
                "artifacts": {
                    "payloads": {
                        "distill": str(existing_payload),
                        "relation": str(Path(tmp) / "missing.json"),
                        "empty": "",
                    }
                }
            }

            updated = reconcile_discovered_artifacts(
                manifest,
                character_index=[],
                relation_graph=None,
            )

            self.assertEqual(updated["artifacts"]["payloads"], {"distill": str(existing_payload)})

    def test_apply_imported_run_semantics_for_import_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp) / "runs" / "run-new"
            manifest = {
                "novel_id": "hongloumeng",
                "file_urls": {"manifest": "/old"},
            }
            updated = apply_imported_run_semantics(
                manifest,
                target_root=target_root,
                new_run_id="run-new",
                imported_at="2026-05-20T00:00:00Z",
                package_filename="demo.zaomeng-run.zip",
                builtin_source=False,
            )
            self.assertEqual(updated["run_id"], "run-new")
            self.assertEqual(updated["entrypoint"], "import")
            self.assertEqual(updated["imported_from"]["package_filename"], "demo.zaomeng-run.zip")
            self.assertNotIn("file_urls", updated)
            self.assertEqual(updated["events"][-1]["stage"], "run_imported")
            self.assertTrue(str(updated["webui"]["artifact_dir"]).replace("\\", "/").endswith("/artifacts"))

    def test_apply_imported_run_semantics_for_builtin_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp) / "runs" / "run-new"
            manifest = {"novel_id": "hongloumeng"}
            updated = apply_imported_run_semantics(
                manifest,
                target_root=target_root,
                new_run_id="run-new",
                imported_at="2026-05-20T00:00:00Z",
                package_filename="builtin.zaomeng-run.zip",
                builtin_source=True,
            )
            self.assertEqual(updated["entrypoint"], "builtin")
            self.assertEqual(updated["events"][-1]["stage"], "builtin_cloned")
            self.assertEqual(updated["imported_from"]["builtin_source"], True)


if __name__ == "__main__":
    unittest.main()
