#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path


def _load_packages_module():
    import importlib.util
    import sys
    import types

    module_path = Path("src/web/run_ops/packages.py").resolve()
    spec = importlib.util.spec_from_file_location("run_ops_packages_for_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec: {module_path}")

    src_web_pkg = types.ModuleType("src.web")
    src_web_pkg.__path__ = []  # type: ignore[attr-defined]
    src_web_run_ops_pkg = types.ModuleType("src.web.run_ops")
    src_web_run_ops_pkg.__path__ = []  # type: ignore[attr-defined]
    src_web_manifest_pkg = types.ModuleType("src.web.manifest")
    src_web_manifest_pkg.__path__ = []  # type: ignore[attr-defined]

    compat_module = types.ModuleType("src.web.manifest.compat")
    compat_module.rewrite_run_root_paths = lambda manifest, source_root, target_root: manifest
    compat_module.apply_imported_run_semantics = (
        lambda manifest, target_root, new_run_id, imported_at, package_filename, builtin_source: manifest
    )

    state_module = types.ModuleType("src.web.run_ops.state")
    state_module.derive_summary_graph_status = lambda manifest: "pending"
    state_module.derive_summary_status_text = lambda manifest: "ready"

    sys.modules.setdefault("src.web", src_web_pkg)
    sys.modules.setdefault("src.web.run_ops", src_web_run_ops_pkg)
    sys.modules.setdefault("src.web.manifest", src_web_manifest_pkg)
    sys.modules["src.web.manifest.compat"] = compat_module
    sys.modules["src.web.run_ops.state"] = state_module

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_packages = _load_packages_module()
read_run_package_metadata = _packages.read_run_package_metadata


class PackageManifestCompatibilityTests(unittest.TestCase):
    def _build_package(self, root: Path, filename: str, package_manifest: dict, *, with_run_manifest: bool = True) -> Path:
        package_path = root / filename
        with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "package_manifest.json",
                json.dumps(package_manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            )
            if with_run_manifest:
                archive.writestr(
                    "run/run_manifest.json",
                    json.dumps({"run_id": "legacy-run", "webui": {"run_dir": "run"}}, ensure_ascii=False, indent=2).encode("utf-8"),
                )
        return package_path

    def test_read_metadata_accepts_legacy_schema_and_fills_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = self._build_package(
                Path(tmp),
                "legacy.zaomeng-run.zip",
                {
                    "kind": "zaomeng_web_run_package",
                    "schema_version": 0,
                    "package_id": "legacy",
                    "title": "旧包",
                    "novel_id": "hongloumeng",
                    "status": "ready",
                    "has_relation_graph": True,
                    "exported_at": "2026-05-20T00:00:00Z",
                },
            )
            metadata = read_run_package_metadata(package_path)
            self.assertIsNotNone(metadata)
            assert metadata is not None
            self.assertEqual(metadata["package_id"], "legacy")
            self.assertEqual(metadata["character_count"], 0)
            self.assertEqual(metadata["builtin"], False)
            self.assertEqual(metadata["summary"]["status_text"], "ready")
            self.assertEqual(metadata["summary"]["graph_status"], "complete")

    def test_read_metadata_rejects_unknown_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = self._build_package(
                Path(tmp),
                "future.zaomeng-run.zip",
                {
                    "kind": "zaomeng_web_run_package",
                    "schema_version": 99,
                    "package_id": "future",
                    "title": "未来包",
                    "novel_id": "hongloumeng",
                    "status": "ready",
                    "exported_at": "2026-05-20T00:00:00Z",
                },
            )
            metadata = read_run_package_metadata(package_path)
            self.assertIsNone(metadata)

    def test_read_metadata_fills_missing_summary_fields_in_current_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = self._build_package(
                Path(tmp),
                "v1.zaomeng-run.zip",
                {
                    "kind": "zaomeng_web_run_package",
                    "schema_version": 1,
                    "package_id": "v1",
                    "title": "当前包",
                    "novel_id": "hongloumeng",
                    "status": "ready",
                    "character_count": "2",
                    "has_relation_graph": False,
                    "summary": {"status_text": ""},
                    "exported_at": "2026-05-20T00:00:00Z",
                },
            )
            metadata = read_run_package_metadata(package_path)
            self.assertIsNotNone(metadata)
            assert metadata is not None
            self.assertEqual(metadata["character_count"], 2)
            self.assertEqual(metadata["summary"]["status_text"], "ready")
            self.assertEqual(metadata["summary"]["graph_status"], "pending")


if __name__ == "__main__":
    unittest.main()
