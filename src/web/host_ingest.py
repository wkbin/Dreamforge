from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Any


def _helper_root() -> Path:
    return Path(__file__).resolve().parents[2] / "zaomeng-skill" / "tools"


HELPER_ROOT = _helper_root()
if str(HELPER_ROOT) not in sys.path:
    sys.path.insert(0, str(HELPER_ROOT))

from _skill_support.persona_bundle import (  # type: ignore  # noqa: E402
    load_existing_persona_bundle,
    load_profile_source,
    materialize_persona_bundle,
    render_profile_md,
)
from _skill_support.relation_graph_export import export_relation_graph, _load_relations_payload  # type: ignore  # noqa: E402


def decode_text_content(content_base64: str) -> str:
    raw = base64.b64decode(str(content_base64 or ""), validate=True)
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def materialize_profile_source(profile_source: str | Path, output_dir: str | Path) -> dict[str, Any]:
    source = Path(profile_source)
    profile = load_profile_source(source)
    target_dir = materialize_persona_bundle(output_dir, profile)
    generated_files = sorted(path.name for path in target_dir.glob("*.generated.md"))
    editable_files = sorted(path.name for path in target_dir.glob("*.md") if not path.name.endswith(".generated.md"))
    return {
        "character": str(profile.get("name", "")).strip() or target_dir.name,
        "novel_id": str(profile.get("novel_id", "")).strip(),
        "profile_source": str(source.resolve()),
        "persona_dir": str(target_dir.resolve()),
        "generated_files": generated_files,
        "editable_files": editable_files,
    }


def load_persona_bundle(persona_dir: str | Path) -> dict[str, Any]:
    return load_existing_persona_bundle(persona_dir)


def write_persona_profile(persona_dir: str | Path, profile: dict[str, Any]) -> Path:
    target_dir = Path(persona_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    editable_profile = target_dir / "PROFILE.md"
    editable_profile.write_text(render_profile_md(profile), encoding="utf-8")
    return editable_profile


def export_relations_source(relations_file: str | Path, *, novel_id: str | None = None, manifest_path: str | Path | None = None) -> dict[str, str]:
    return export_relation_graph(relations_file, novel_id=novel_id, manifest_path=manifest_path)


def load_relations_source(relations_file: str | Path) -> dict[str, Any]:
    return _load_relations_payload(Path(relations_file))
