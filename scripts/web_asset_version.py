#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path


STATIC_VERSION_RELATIVE_PATH = Path("src/web/static/version.txt")
INDEX_HTML_RELATIVE_PATH = Path("src/web/static/index.html")
BOOTSTRAP_JS_RELATIVE_PATH = Path("src/web/static/js/bootstrap.js")
APP_CSS_RELATIVE_PATH = Path("src/web/static/styles/app.css")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def read_web_asset_version(repo_root: Path) -> str:
    version_path = repo_root / STATIC_VERSION_RELATIVE_PATH
    if not version_path.exists():
        raise FileNotFoundError(f"Missing static asset version file: {version_path}")
    return version_path.read_text(encoding="utf-8").strip()


def _replace_once(pattern: str, replacement: str, content: str, *, path: Path) -> str:
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Expected to update exactly one version token in {path}")
    return updated


def sync_web_asset_version(repo_root: Path, version: str) -> str:
    version = str(version).strip()
    if not version:
        raise ValueError("Static asset version cannot be empty.")

    version_path = repo_root / STATIC_VERSION_RELATIVE_PATH
    index_path = repo_root / INDEX_HTML_RELATIVE_PATH
    bootstrap_path = repo_root / BOOTSTRAP_JS_RELATIVE_PATH
    app_css_path = repo_root / APP_CSS_RELATIVE_PATH

    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text(version + "\n", encoding="utf-8")

    index_content = _replace_once(
        r'(/web/styles/app\.css\?v=)[^"]+',
        rf"\g<1>{version}",
        _read_text(index_path),
        path=index_path,
    )
    index_content = _replace_once(
        r'(/web/js/bootstrap\.js\?v=)[^"]+',
        rf"\g<1>{version}",
        index_content,
        path=index_path,
    )
    _write_text(index_path, index_content)

    bootstrap_content = _replace_once(
        r'const version = "[^"]+";',
        f'const version = "{version}";',
        _read_text(bootstrap_path),
        path=bootstrap_path,
    )
    _write_text(bootstrap_path, bootstrap_content)

    app_css_content = _read_text(app_css_path)
    for relative_css in ("base.css", "workspace.css", "dialogue.css", "modal.css", "responsive.css"):
        app_css_content = _replace_once(
            rf'(\./{re.escape(relative_css)}\?v=)[^")]+',
            rf"\g<1>{version}",
            app_css_content,
            path=app_css_path,
        )
    _write_text(app_css_path, app_css_content)
    return version


def generate_web_asset_version(*, now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return current.strftime("%Y%m%d%H%M%S")


def bump_web_asset_version(repo_root: Path, version: str = "") -> str:
    resolved_version = str(version).strip() or generate_web_asset_version()
    return sync_web_asset_version(repo_root, resolved_version)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync or bump the web static asset cache-busting version.")
    parser.add_argument("--version", help="Explicit static asset version to write.")
    parser.add_argument("--bump", action="store_true", help="Generate a fresh timestamp-style version automatically.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    if args.version and args.bump:
        raise ValueError("Use either --version or --bump, not both.")

    if args.version:
        version = sync_web_asset_version(repo_root, args.version)
    elif args.bump:
        version = bump_web_asset_version(repo_root)
    else:
        version = sync_web_asset_version(repo_root, read_web_asset_version(repo_root))

    print(f"Synchronized web static asset version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
