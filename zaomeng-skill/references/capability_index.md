# Capability Index

## Purpose

This document is the host-side index for the standard `zaomeng` capabilities.

Use it as the first stop when the host needs to answer:

- which helper should I call
- what files should I expect
- how do I know whether this capability succeeded

## Capability List

| Capability | Entry | Primary Output | Success Marker |
| --- | --- | --- | --- |
| `distill` | `tools/build_prompt_payload.py --mode distill` | distill payload JSON | capability status with `status=ready` and `success=true` |
| `materialize` | `tools/materialize_persona_bundle.py` | persona bundle files | `ARTIFACT_STATUS.generated.json` plus capability status |
| `export_graph` | `tools/export_relation_graph.py` | relationship graph HTML / SVG / Mermaid | graph `.status.json` plus capability status |
| `verify_workflow` | `tools/verify_host_workflow.py` | workflow verification JSON | capability status with `status=complete` and `success=true` |

## 1. Distill

Entry:

```bash
python tools/build_prompt_payload.py --mode distill --novel <path> --characters A,B --output <distill_payload.json> --run-manifest <run_manifest.json>
```

Standard outputs:

- distill payload JSON
- optional capability status JSON
- optional `run_manifest.json` updates

Payload contract:

- `request.chunk_mode = single|chunked`
- `chunks[]` for partial distill execution when the excerpt is too large
- `merge_payload` for final profile merge
- `host_plan.execution = single_pass|sequential_chunks_then_merge`
- `meta.chunk_count`
- `meta.merge_required`

Host responsibility after this step:

- if `single`, hand the payload to the host LLM and write `PROFILE.generated.md`
- if `chunked`, iterate `chunks[]`, collect partial drafts, fill `merge_payload.request.chunk_drafts`, then execute the merge payload and write the final `PROFILE.generated.md`

Recommended manifest fields to read:

- `artifacts.chunking.distill`
- `progress.chunking.distill`
- `summary.chunking.distill`

Reference:

- `references/output_schema.md`

## 2. Materialize

Entry:

```bash
python tools/materialize_persona_bundle.py --profile-file <character-dir/PROFILE.generated.md> --run-manifest <run_manifest.json>
```

Standard outputs:

- split persona markdown files
- `ARTIFACT_STATUS.generated.json`
- optional capability status JSON

Reference:

- `references/output_schema.md`

## 3. Export Graph

Entry:

```bash
python tools/export_relation_graph.py --relations-file <relations.md> --run-manifest <run_manifest.json>
```

Standard outputs:

- `*_relations.html`
- `*_relations.svg`
- `*_relations.mermaid.md`
- graph `.status.json`

If relation extraction is chunked on the host side, the same contract applies:

- `request.chunk_mode = single|chunked`
- `chunks[]`
- `merge_payload`
- `meta.chunk_count`
- `meta.merge_required`

Recommended manifest fields to read:

- `artifacts.chunking.relation`
- `progress.chunking.relation`
- `summary.chunking.relation`

Reference:

- `examples/sample_relations.md`

## 4. Verify Workflow

Entry:

```bash
python tools/verify_host_workflow.py --characters-root <characters/<novel_id>> --relations-file <relations.md> --run-manifest <run_manifest.json>
```

Standard outputs:

- workflow verification JSON
- capability status JSON

Recommended use:

- run after materialize and export graph
- treat it as the final host-side completeness check

## Dialogue Stage

`act`, `insert`, and `observe` are host-driven dialogue modes, but the skill now provides packaged helpers for the most repetitive dialogue-side work.

At dialogue time, the host should read:

- persona bundle files under `runtime/data/characters/<novel_id>/<character_name>/`
- `MEMORY.md`
- relation markdown and graph artifacts
- `run_manifest.json`
- constraint references such as `output_schema.md`, `style_differ.md`, and `logic_constraint.md`

Reference:

- `references/chat_contract.md`

Optional helpers for the dialogue stage:

- `tools/manage_self_card.py`
  - manage self-insert cards
  - build random self-card generation payloads
- `tools/build_persona_autofill_payload.py`
  - build one-field persona autofill payloads
  - parse model output for direct form write-back
- `tools/build_dialogue_suggestion_payload.py`
  - build one-line suggestion payloads for `act` / `insert` / `observe`
  - provide compact retry payloads for long-context fallback

## Read Order

Recommended host read order across the structured workflow:

1. read capability status first
2. read the primary output for the current capability
3. if present, read `run_manifest.json` for the updated cross-step index

After the workflow completes, hand off to the dialogue stage described in `references/chat_contract.md`.

## End-To-End Example

For one complete host-side chain from run initialization to dialogue handoff, see:

- `examples/host_workflow_example.md`
