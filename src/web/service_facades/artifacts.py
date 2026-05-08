from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.web.artifacts import (
    export_relations_source,
    load_profile_source,
    load_relations_source,
    materialize_profile_source,
    resolve_persona_dir,
    resolve_relations_file,
    resolve_run_file,
    write_persona_profile,
)
from src.web.artifacts import (
    coerce_relation_evidence,
    relation_type_label,
    split_relation_pair,
)
from src.web.artifacts import list_relation_details as build_relation_details_payload
from src.web.artifacts import (
    ingest_character_result as apply_character_ingest,
    ingest_relation_result as apply_relation_ingest,
)
from src.web.review import (
    apply_persona_review_updates,
    get_persona_review_payload,
    read_persona_review_fields,
    resolve_persona_review_source,
    save_persona_review_payload,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ArtifactServiceMixin:
    def ingest_character_result(
        self,
        run_id: str,
        *,
        character: str,
        content_base64: str,
        filename: str = "PROFILE.generated.md",
    ) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)
        refreshed = apply_character_ingest(
            run_id=run_id,
            runs_root=self.runs_root,
            manifest=manifest,
            character=character,
            content_base64=content_base64,
            filename=filename,
            materialize_profile_source=materialize_profile_source,
            discover_artifacts=self._discover_artifacts,
            utc_now=_utc_now,
        )
        self._write_json(manifest_path, refreshed)
        return self._serialize_manifest(refreshed)

    def ingest_relation_result(
        self,
        run_id: str,
        *,
        content_base64: str,
        filename: str = "relations.md",
    ) -> dict[str, Any]:
        manifest_path = self._manifest_path(run_id)
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(run_id)
        refreshed = apply_relation_ingest(
            run_id=run_id,
            runs_root=self.runs_root,
            manifest_path=manifest_path,
            manifest=manifest,
            content_base64=content_base64,
            filename=filename,
            export_relations_source=lambda relation_source: export_relations_source(
                relation_source,
                novel_id=str(manifest.get("novel_id", "")).strip() or run_id,
                manifest_path=manifest_path,
            ),
            discover_artifacts=self._discover_artifacts,
            utc_now=_utc_now,
        )
        self._write_json(manifest_path, refreshed)
        return self._serialize_manifest(refreshed)

    def get_persona_review(self, run_id: str, character: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        persona_dir = resolve_persona_dir(manifest, character)
        return get_persona_review_payload(
            run_id=run_id,
            character=character,
            persona_dir=persona_dir,
            resolve_persona_review_source=resolve_persona_review_source,
            load_profile_source=load_profile_source,
            read_persona_review_fields=read_persona_review_fields,
        )

    def save_persona_review(self, run_id: str, character: str, fields: dict[str, str]) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        persona_dir = resolve_persona_dir(manifest, character)
        result = save_persona_review_payload(
            run_id=run_id,
            character=character,
            fields=fields,
            manifest=manifest,
            persona_dir=persona_dir,
            resolve_persona_review_source=resolve_persona_review_source,
            load_profile_source=load_profile_source,
            apply_persona_review_updates=apply_persona_review_updates,
            write_persona_profile=write_persona_profile,
            discover_artifacts=self._discover_artifacts,
            get_persona_review=self.get_persona_review,
            utc_now=_utc_now,
        )
        self._write_json(self._manifest_path(run_id), result["manifest"])
        return result["payload"]

    def list_relation_details(self, run_id: str) -> dict[str, Any]:
        manifest = self._require_manifest(run_id)
        relations_file = resolve_relations_file(manifest)
        payload = load_relations_source(relations_file)
        return build_relation_details_payload(
            run_id=run_id,
            manifest=manifest,
            relations_file=relations_file,
            payload=payload,
            split_relation_pair=split_relation_pair,
            relation_type_label=relation_type_label,
            coerce_relation_evidence=coerce_relation_evidence,
        )

    def resolve_run_file(self, run_id: str, relative_path: str) -> Path:
        return resolve_run_file(
            runs_root=self.runs_root,
            run_id=run_id,
            relative_path=relative_path,
        )
