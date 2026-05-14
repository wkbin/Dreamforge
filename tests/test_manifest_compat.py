from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.web.manifest.compat import coerce_manifest_path, relative_to_run_dir, rewrite_run_root_paths, rewrite_string_path


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


if __name__ == "__main__":
    unittest.main()
