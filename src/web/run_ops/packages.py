from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from src.web.manifest.compat import apply_imported_run_semantics, rewrite_run_root_paths
from src.web.run_ops.state import derive_summary_graph_status, derive_summary_status_text
from src.utils.file_utils import safe_filename

PACKAGE_KIND = "zaomeng_web_run_package"
PACKAGE_SCHEMA_VERSION = 1
PACKAGE_LEGACY_SCHEMA_VERSION = 0
SUPPORTED_PACKAGE_SCHEMA_VERSIONS = {PACKAGE_LEGACY_SCHEMA_VERSION, PACKAGE_SCHEMA_VERSION}
PACKAGE_SUFFIX = ".zaomeng-run.zip"
PACKAGE_ROOT = "run"


def package_filename_slug(title: str, *, fallback: str) -> str:
    slug = safe_filename(str(title or "").strip()) or safe_filename(fallback) or "novel"
    return slug[:80]


def build_package_filename(*, title: str, novel_id: str, run_id: str) -> str:
    slug = package_filename_slug(title or novel_id, fallback=run_id)
    return f"{slug}{PACKAGE_SUFFIX}"


def export_run_package(
    *,
    run_id: str,
    run_dir: Path,
    manifest: dict[str, Any],
    builtin: bool,
    utc_now: Callable[[], str],
) -> tuple[Path, str]:
    status = str(manifest.get("status", "")).strip()
    if status == "running":
        raise ValueError("这本书还在整理中，等这一轮结束后再导出小说包。")

    exports_dir = run_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    title = _package_title(manifest)
    filename = build_package_filename(
        title=title,
        novel_id=str(manifest.get("novel_id", "")).strip() or run_id,
        run_id=run_id,
    )
    package_path = exports_dir / filename

    with tempfile.TemporaryDirectory(prefix="zaomeng-export-") as tmpdir:
        staging_root = Path(tmpdir)
        staged_run_dir = staging_root / PACKAGE_ROOT
        shutil.copytree(
            run_dir,
            staged_run_dir,
            ignore=shutil.ignore_patterns("dialogue", "exports", "__pycache__", "*.pyc"),
        )
        _strip_export_only_paths(staged_run_dir)
        package_manifest = _build_package_manifest(
            manifest=manifest,
            builtin=builtin,
            exported_at=utc_now(),
        )
        (staging_root / "package_manifest.json").write_text(
            json.dumps(package_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(staging_root / "package_manifest.json", "package_manifest.json")
            for path in sorted(staged_run_dir.rglob("*")):
                if path.is_dir():
                    continue
                archive.write(path, path.relative_to(staging_root).as_posix())
    return package_path, filename


def list_run_packages(packages_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not packages_root.exists():
        return items
    for package_path in sorted(packages_root.glob(f"*{PACKAGE_SUFFIX}"), reverse=True):
        metadata = read_run_package_metadata(package_path)
        if not metadata:
            continue
        items.append(metadata)
    items.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return items


def read_run_package_metadata(package_path: Path) -> dict[str, Any] | None:
    if not package_path.exists() or not package_path.is_file():
        return None
    try:
        with zipfile.ZipFile(package_path) as archive:
            manifest = _read_package_manifest(archive)
    except (OSError, ValueError, zipfile.BadZipFile):
        return None
    if not manifest:
        return None
    package_id = str(manifest.get("package_id", "")).strip() or package_path.stem
    title = str(manifest.get("title", "")).strip() or package_id
    return {
        "package_id": package_id,
        "title": title,
        "novel_id": str(manifest.get("novel_id", "")).strip(),
        "status": str(manifest.get("status", "")).strip(),
        "character_count": int(manifest.get("character_count", 0) or 0),
        "has_relation_graph": bool(manifest.get("has_relation_graph", False)),
        "updated_at": str(manifest.get("exported_at", "")).strip() or str(manifest.get("updated_at", "")).strip(),
        "filename": package_path.name,
        "package_path": str(package_path.resolve()),
        "builtin": bool(manifest.get("builtin", False)),
        "summary": dict(manifest.get("summary", {}) or {}),
    }


def import_run_package(
    *,
    package_path: Path,
    runs_root: Path,
    new_run_id: str,
    builtin_source: bool,
    utc_now: Callable[[], str],
    load_manifest: Callable[[Path], dict[str, Any] | None],
    write_json: Callable[[Path, dict[str, Any]], None],
    discover_artifacts: Callable[[dict[str, Any]], dict[str, Any]],
    serialize_manifest: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    target_run_dir = runs_root / new_run_id
    if target_run_dir.exists():
        raise ValueError("新书卷目录已经存在，请稍后再试。")

    with tempfile.TemporaryDirectory(prefix="zaomeng-import-") as tmpdir:
        extract_root = Path(tmpdir)
        with zipfile.ZipFile(package_path) as archive:
            _read_package_manifest(archive)
            archive.extractall(extract_root)
        source_run_dir = extract_root / PACKAGE_ROOT
        if not source_run_dir.exists():
            raise ValueError("小说包缺少 run 数据目录。")
        shutil.copytree(source_run_dir, target_run_dir)

    manifest_path = target_run_dir / "run_manifest.json"
    manifest = load_manifest(manifest_path)
    if not manifest:
        raise ValueError("小说包缺少有效的 run_manifest.json。")

    source_run_dir = Path(str(manifest.get("webui", {}).get("run_dir", "")).strip() or target_run_dir)
    rewritten = rewrite_imported_run_manifest(
        manifest,
        source_run_dir=source_run_dir,
        target_run_dir=target_run_dir,
        new_run_id=new_run_id,
        imported_at=utc_now(),
        package_filename=package_path.name,
        builtin_source=builtin_source,
    )
    refreshed = discover_artifacts(rewritten)
    write_json(manifest_path, refreshed)
    return serialize_manifest(refreshed)


def rewrite_imported_run_manifest(
    manifest: dict[str, Any],
    *,
    source_run_dir: Path,
    target_run_dir: Path,
    new_run_id: str,
    imported_at: str,
    package_filename: str,
    builtin_source: bool,
) -> dict[str, Any]:
    source_root = source_run_dir.resolve(strict=False)
    target_root = target_run_dir.resolve(strict=False)
    rewritten = rewrite_run_root_paths(manifest, source_root=source_root, target_root=target_root)
    return apply_imported_run_semantics(
        rewritten,
        target_root=target_root,
        new_run_id=new_run_id,
        imported_at=imported_at,
        package_filename=package_filename,
        builtin_source=builtin_source,
    )


def _build_package_manifest(
    *,
    manifest: dict[str, Any],
    builtin: bool,
    exported_at: str,
) -> dict[str, Any]:
    title = _package_title(manifest)
    package_id = package_filename_slug(title, fallback=str(manifest.get("run_id", "run")).strip() or "run")
    relation_graph = dict(manifest.get("artifact_index", {}).get("relation_graph", {}) or {})
    characters = list(manifest.get("artifact_index", {}).get("characters", []) or [])
    return {
        "kind": PACKAGE_KIND,
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "title": title,
        "novel_id": str(manifest.get("novel_id", "")).strip(),
        "original_run_id": str(manifest.get("run_id", "")).strip(),
        "status": str(manifest.get("status", "")).strip(),
        "character_count": len(characters),
        "has_relation_graph": bool(relation_graph.get("relations_file")),
        "summary": {
            "status_text": derive_summary_status_text(manifest),
            "graph_status": derive_summary_graph_status(manifest),
        },
        "exported_at": exported_at,
        "updated_at": str(manifest.get("updated_at", "")).strip(),
        "builtin": builtin,
    }


def _package_title(manifest: dict[str, Any]) -> str:
    novel_id = str(manifest.get("novel_id", "")).strip()
    return novel_id or str(manifest.get("run_id", "")).strip() or "未命名书卷"


def _read_package_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        with archive.open("package_manifest.json") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
    except KeyError as exc:
        raise ValueError("小说包缺少 package_manifest.json。") from exc
    if not isinstance(payload, dict):
        raise ValueError("小说包元数据格式不正确。")
    if str(payload.get("kind", "")).strip() != PACKAGE_KIND:
        raise ValueError("不是可识别的造梦小说包。")
    return _normalize_package_manifest(payload)


def _normalize_package_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    schema_version = _coerce_schema_version(payload.get("schema_version"), default=PACKAGE_LEGACY_SCHEMA_VERSION)
    if schema_version not in SUPPORTED_PACKAGE_SCHEMA_VERSIONS:
        raise ValueError(
            f"小说包 schema_version={schema_version} 暂不支持（当前支持：{sorted(SUPPORTED_PACKAGE_SCHEMA_VERSIONS)}）。"
        )
    normalized = _migrate_legacy_package_manifest(payload, schema_version=schema_version)
    summary_payload = dict(normalized.get("summary", {}) or {})
    status = str(normalized.get("status", "")).strip()
    graph_status = str(summary_payload.get("graph_status", "")).strip()
    if not graph_status:
        graph_status = "complete" if bool(normalized.get("has_relation_graph", False)) else "pending"
    normalized["summary"] = {
        "status_text": str(summary_payload.get("status_text", "")).strip() or status,
        "graph_status": graph_status,
    }
    normalized["builtin"] = bool(normalized.get("builtin", False))
    normalized["character_count"] = _coerce_non_negative_int(normalized.get("character_count"), default=0)
    normalized["has_relation_graph"] = bool(normalized.get("has_relation_graph", False))
    normalized["schema_version"] = PACKAGE_SCHEMA_VERSION
    return normalized


def _migrate_legacy_package_manifest(payload: dict[str, Any], *, schema_version: int) -> dict[str, Any]:
    normalized = dict(payload)
    if schema_version == PACKAGE_LEGACY_SCHEMA_VERSION:
        relation_graph = bool(normalized.get("has_relation_graph", False))
        summary_payload = dict(normalized.get("summary", {}) or {})
        normalized["summary"] = {
            "status_text": str(summary_payload.get("status_text", "")).strip() or str(normalized.get("status", "")).strip(),
            "graph_status": str(summary_payload.get("graph_status", "")).strip() or ("complete" if relation_graph else "pending"),
        }
        normalized["builtin"] = bool(normalized.get("builtin", False))
        normalized["character_count"] = _coerce_non_negative_int(normalized.get("character_count"), default=0)
        normalized["has_relation_graph"] = relation_graph
    return normalized


def _coerce_schema_version(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"小说包 schema_version 非法：{value!r}") from exc


def _coerce_non_negative_int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        coerced = int(value)
    elif isinstance(value, (int, float)):
        coerced = int(value)
    else:
        text = str(value).strip()
        if not text:
            return default
        try:
            coerced = int(text)
        except ValueError:
            return default
    return max(coerced, 0)


def _strip_export_only_paths(run_dir: Path) -> None:
    dialogue_dir = run_dir / "dialogue"
    if dialogue_dir.exists():
        shutil.rmtree(dialogue_dir, ignore_errors=False)
