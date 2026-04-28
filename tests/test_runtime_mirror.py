#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from scripts.check_runtime_mirror import (
    build_report,
    load_manifest_patterns,
    load_runtime_owned_patterns,
    sync_mirror,
    validate_manifest,
)


class RuntimeMirrorTests(unittest.TestCase):
    def test_runtime_mirror_manifest_has_explicit_entries(self):
        patterns = load_manifest_patterns()
        self.assertTrue(patterns)
        self.assertIn("core/cli_app.py", patterns)
        self.assertIn("core/logging_setup.py", patterns)
        self.assertIn("core/runtime_parts.py", patterns)
        self.assertIn("modules/chat_engine.py", patterns)
        self.assertNotIn("core/**/*.py", patterns)
        self.assertTrue(all("*" not in pattern for pattern in patterns))
        self.assertTrue(load_runtime_owned_patterns())
        self.assertEqual(validate_manifest(), [])

    def test_runtime_mirror_matches_source_tree(self):
        report = build_report()
        self.assertTrue(
            report.is_clean(),
            msg=(
                "Runtime mirror drift detected: "
                f"missing_in_runtime={report.missing_in_runtime}, "
                f"missing_in_source={report.missing_in_source}, "
                f"content_mismatches={report.content_mismatches}"
            ),
        )

    def test_sync_mirror_copies_updates_and_removes_extra_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "src"
            runtime_root = root / "runtime"
            (source_root / "pkg").mkdir(parents=True, exist_ok=True)
            runtime_pkg = runtime_root / "pkg"
            runtime_pkg.mkdir(parents=True, exist_ok=True)

            (source_root / "pkg" / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")
            (source_root / "pkg" / "beta.py").write_text("print('beta')\n", encoding="utf-8")
            (runtime_root / "pkg" / "alpha.py").write_text("print('stale')\n", encoding="utf-8")
            (runtime_root / "pkg" / "extra.py").write_text("print('extra')\n", encoding="utf-8")

            patterns = ["pkg/**/*.py"]
            result = sync_mirror(source_root=source_root, runtime_root=runtime_root, patterns=patterns)

            self.assertEqual(sorted(result.copied), ["pkg/alpha.py", "pkg/beta.py"])
            self.assertEqual(result.removed, ["pkg/extra.py"])
            report = build_report(source_root=source_root, runtime_root=runtime_root, patterns=patterns)
            self.assertTrue(report.is_clean())

    def test_build_report_ignores_files_outside_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "src"
            runtime_root = root / "runtime"
            (source_root / "pkg").mkdir(parents=True, exist_ok=True)
            (runtime_root / "pkg").mkdir(parents=True, exist_ok=True)
            (source_root / "pkg" / "kept.py").write_text("print('kept')\n", encoding="utf-8")
            (source_root / "misc").mkdir(parents=True, exist_ok=True)
            (source_root / "misc" / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
            (runtime_root / "pkg" / "kept.py").write_text("print('kept')\n", encoding="utf-8")

            report = build_report(
                source_root=source_root,
                runtime_root=runtime_root,
                patterns=["pkg/**/*.py"],
            )

            self.assertTrue(report.is_clean())

    def test_runtime_mirror_manifest_is_a_curated_source_subset(self):
        manifest_entries = sorted(load_manifest_patterns())
        source_python_files = {
            path.relative_to(Path("src")).as_posix()
            for path in Path("src").rglob("*.py")
        }
        self.assertTrue(set(manifest_entries).issubset(source_python_files))
        self.assertNotIn("core/main.py", manifest_entries)
        self.assertNotIn("core/runtime_factory.py", manifest_entries)
        self.assertNotIn("core/logging_utils.py", manifest_entries)

    def test_runtime_owned_wrapper_files_exist(self):
        runtime_owned = set(load_runtime_owned_patterns())
        for relative_path in runtime_owned:
            target = Path("clawhub-zaomeng-skill/runtime/src") / Path(relative_path)
            self.assertTrue(target.exists(), msg=f"Missing runtime-owned file: {relative_path}")

    def test_runtime_mirror_manifest_rejects_overlapping_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / ".runtime-mirror.json"
            manifest_path.write_text(
                '{\n  "include": ["core/config.py"],\n  "runtime_owned": ["core/config.py"]\n}\n',
                encoding="utf-8",
            )
            errors = validate_manifest(manifest_path)
            self.assertTrue(errors)
            self.assertTrue(any("overlap" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
