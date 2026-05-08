#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.web_asset_version import (
    bump_web_asset_version,
    generate_web_asset_version,
    read_web_asset_version,
    sync_web_asset_version,
)


class WebAssetVersionTests(unittest.TestCase):
    def test_sync_web_asset_version_updates_all_static_entrypoints(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "src" / "web" / "static" / "js").mkdir(parents=True, exist_ok=True)
            (repo_root / "src" / "web" / "static" / "styles").mkdir(parents=True, exist_ok=True)

            (repo_root / "src" / "web" / "static" / "version.txt").write_text("old\n", encoding="utf-8")
            (repo_root / "src" / "web" / "static" / "index.html").write_text(
                '<link rel="stylesheet" href="/web/styles/app.css?v=old" />\n'
                '<script src="/web/js/bootstrap.js?v=old"></script>\n',
                encoding="utf-8",
            )
            (repo_root / "src" / "web" / "static" / "js" / "bootstrap.js").write_text(
                '(() => {\n  const version = "old";\n})();\n',
                encoding="utf-8",
            )
            (repo_root / "src" / "web" / "static" / "styles" / "app.css").write_text(
                '@import url("./base.css?v=old");\n'
                '@import url("./workspace.css?v=old");\n'
                '@import url("./dialogue.css?v=old");\n'
                '@import url("./modal.css?v=old");\n'
                '@import url("./responsive.css?v=old");\n',
                encoding="utf-8",
            )

            sync_web_asset_version(repo_root, "202605080001")

            self.assertEqual(read_web_asset_version(repo_root), "202605080001")
            self.assertIn("app.css?v=202605080001", (repo_root / "src" / "web" / "static" / "index.html").read_text(encoding="utf-8"))
            self.assertIn('const version = "202605080001";', (repo_root / "src" / "web" / "static" / "js" / "bootstrap.js").read_text(encoding="utf-8"))
            app_css = (repo_root / "src" / "web" / "static" / "styles" / "app.css").read_text(encoding="utf-8")
            self.assertEqual(app_css.count("202605080001"), 5)

    def test_bump_web_asset_version_generates_timestamp_like_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "src" / "web" / "static" / "js").mkdir(parents=True, exist_ok=True)
            (repo_root / "src" / "web" / "static" / "styles").mkdir(parents=True, exist_ok=True)
            (repo_root / "src" / "web" / "static" / "version.txt").write_text("old\n", encoding="utf-8")
            (repo_root / "src" / "web" / "static" / "index.html").write_text(
                '<link rel="stylesheet" href="/web/styles/app.css?v=old" />\n'
                '<script src="/web/js/bootstrap.js?v=old"></script>\n',
                encoding="utf-8",
            )
            (repo_root / "src" / "web" / "static" / "js" / "bootstrap.js").write_text(
                '(() => {\n  const version = "old";\n})();\n',
                encoding="utf-8",
            )
            (repo_root / "src" / "web" / "static" / "styles" / "app.css").write_text(
                '@import url("./base.css?v=old");\n'
                '@import url("./workspace.css?v=old");\n'
                '@import url("./dialogue.css?v=old");\n'
                '@import url("./modal.css?v=old");\n'
                '@import url("./responsive.css?v=old");\n',
                encoding="utf-8",
            )

            version = bump_web_asset_version(repo_root)

            self.assertRegex(version, r"^\d{14}$")
            self.assertEqual(read_web_asset_version(repo_root), version)

    def test_generate_web_asset_version_format(self):
        version = generate_web_asset_version()
        self.assertRegex(version, r"^\d{14}$")


if __name__ == "__main__":
    unittest.main()
