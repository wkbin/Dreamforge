# Host Workflow Example

This example shows one complete host-side flow:

1. initialize `run_manifest.json`
2. build distill payload
3. choose single-pass or chunked execution
4. call the host LLM and write `PROFILE.generated.md`
5. materialize persona bundles
6. generate / merge the relationship result and export the graph
7. verify workflow completeness
8. hand off to host-driven dialogue

## 1. Initialize The Run

```bash
python tools/init_host_run.py --novel data/hongloumeng.txt --characters 林黛玉,贾宝玉,薛宝钗 --output runtime/run_manifest.json
```

Host expectation:

- `runtime/run_manifest.json` is created
- locked characters are recorded
- progress starts at `characters_locked`

## 2. Build Distill Payload

```bash
python tools/build_prompt_payload.py --mode distill --novel data/hongloumeng.txt --characters 林黛玉,贾宝玉,薛宝钗 --output runtime/distill_payload.json --run-manifest runtime/run_manifest.json
```

Host expectation:

- `runtime/distill_payload.json` is ready
- the host LLM reads this payload
- `run_manifest.json` records payload paths and status updates

The payload now supports two execution shapes:

- `request.chunk_mode = single`
  - the host can send the whole payload directly to the LLM
- `request.chunk_mode = chunked`
  - the host should iterate `chunks[]`
  - collect each chunk result as a partial draft
  - then execute `merge_payload` once to obtain the final artifact

Useful fields:

- `chunks[]`
- `merge_payload`
- `host_plan`
- `meta.chunk_count`
- `meta.merge_required`

`run_manifest.json` will also expose:

- `progress.chunking.distill`
- `summary.chunking.distill`

## 3. Generate Canonical Profiles

### A. Single-pass path

If `request.chunk_mode = single`, the host writes one canonical file per character directly:

```text
runtime/data/characters/hongloumeng/林黛玉/PROFILE.generated.md
runtime/data/characters/hongloumeng/贾宝玉/PROFILE.generated.md
runtime/data/characters/hongloumeng/薛宝钗/PROFILE.generated.md
```

Recommended host progress updates during generation:

```bash
python tools/update_run_progress.py --run-manifest runtime/run_manifest.json --stage character_started --character 林黛玉 --message "正在蒸馏林黛玉"
python tools/update_run_progress.py --run-manifest runtime/run_manifest.json --stage character_completed --character 林黛玉 --message "林黛玉已完成"
```

Repeat for each character.

### B. Chunked path

If `request.chunk_mode = chunked`, the host should:

1. iterate `distill_payload.json -> chunks[]`
2. call the host LLM once per chunk
3. store each partial result
4. place those partial drafts into `merge_payload.request.chunk_drafts`
5. call the host LLM once more with `merge_payload`
6. write the final merged `PROFILE.generated.md`

Chunk progress can also be written back into the manifest:

```bash
python tools/update_run_progress.py --run-manifest runtime/run_manifest.json --stage chunk_started --message "正在执行第 1 块" --chunk-capability distill --chunk-mode chunked --chunk-count 6 --current-chunk 1 --chunk-label 前段-1 --chunk-status running --merge-required --merge-status pending
python tools/update_run_progress.py --run-manifest runtime/run_manifest.json --stage merge_started --message "正在合并人物草稿" --chunk-capability distill --chunk-mode chunked --chunk-count 6 --current-chunk 6 --chunk-label 后段-2 --chunk-status complete --merge-required --merge-status running
python tools/update_run_progress.py --run-manifest runtime/run_manifest.json --stage merge_completed --message "人物草稿已合并" --chunk-capability distill --chunk-mode chunked --chunk-count 6 --current-chunk 6 --chunk-label 后段-2 --chunk-status complete --merge-required --merge-status complete
```

## 4. Materialize Persona Bundles

```bash
python tools/materialize_persona_bundle.py --profile-file runtime/data/characters/hongloumeng/林黛玉/PROFILE.generated.md --run-manifest runtime/run_manifest.json
python tools/materialize_persona_bundle.py --profile-file runtime/data/characters/hongloumeng/贾宝玉/PROFILE.generated.md --run-manifest runtime/run_manifest.json
python tools/materialize_persona_bundle.py --profile-file runtime/data/characters/hongloumeng/薛宝钗/PROFILE.generated.md --run-manifest runtime/run_manifest.json
```

Host expectation:

- split persona files appear
- `ARTIFACT_STATUS.generated.json` appears in each character directory
- `run_manifest.json` records each character directory

## 5. Generate Relation Result And Export Graph

The relation payload follows the same rule:

- `single`: generate the final relation markdown directly
- `chunked`: run `chunks[]`, collect partial relation drafts, then execute `merge_payload`

After the final merged relationship markdown exists, the host writes:

```text
runtime/data/relations/hongloumeng_relations.md
```

Then export the graph:

```bash
python tools/export_relation_graph.py --relations-file runtime/data/relations/hongloumeng_relations.md --run-manifest runtime/run_manifest.json
```

Host expectation:

- `*_relations.html`
- `*_relations.svg`
- `*_relations.mermaid.md`
- graph status JSON
- `run_manifest.json -> progress.chunking.relation` if the host reports chunk progress

## 6. Verify Workflow

```bash
python tools/verify_host_workflow.py --characters-root runtime/data/characters/hongloumeng --relations-file runtime/data/relations/hongloumeng_relations.md --run-manifest runtime/run_manifest.json
```

Host expectation:

- workflow verification JSON is written
- `run_manifest.json` ends in a complete state

## 7. Hand Off To Dialogue

At this point, the host already has everything needed to enter `act`, `insert`, or `observe`:

- character directories
- `PROFILE.md`
- split persona files
- `MEMORY.md`
- relation markdown
- graph HTML / SVG
- `run_manifest.json`

The host now drives the dialogue directly with its own LLM.

## Recommended UI / Agent Surfacing

After the workflow completes, a host can safely surface:

- character directories
- relationship graph HTML / SVG
- workflow summary from `run_manifest.json`
- a clear invitation to enter `act`, `insert`, or `observe`

For long novels, the host can also surface:

- total distill chunks
- current chunk number
- whether merge is pending / running / complete
- total relation chunks

## Cross References

- `references/capability_index.md`
- `references/chat_contract.md`
