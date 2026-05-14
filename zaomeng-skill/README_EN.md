# zaomeng-skill

`zaomeng-skill` is a host-driven skill for Chinese novel character distillation, relationship extraction, relationship graph export, and in-character dialogue.

Its operating model is simple:

- read the novel content
- prepare excerpts, prompts, and references
- hand them to the host LLM for generation
- materialize the canonical profile into a complete persona bundle

This skill runs inside a host-managed environment. The host performs the actual model calls, and the packaged Python helper dependencies are declared in `requirements.txt`.

## Overview

| Item | Value |
| --- | --- |
| Name | `zaomeng-skill` |
| Mode | LLM-first |
| Host Targets | OpenClaw, ClawHub, Hermes, other host-managed agents |
| Core Capabilities | character distillation, relation extraction, graph export, host-driven dialogue |
| License | `MIT-0` |

## What It Does

### 1. Distill Characters

Extract structured character profiles from novel text, covering dimensions such as:

- core identity
- core motivation
- personality base
- decision logic
- character arc
- key bonds
- speech and expression style
- value tradeoffs
- hidden desire
- private self

### 2. Extract Relationships

Extract pairwise relationships from same-scene interactions and output:

- relationship markdown
- Mermaid source
- HTML visualization
- SVG graph

### 3. Enter Character Chat

Three play modes are supported:

- `act`
  you play one character, either one-on-one or by joining a group scene directly
- `insert`
  you enter the scene as yourself rather than as an existing novel character
- `observe`
  multiple characters continue a scene, topic, or opening line while you watch

These dialogue modes are host-driven. `zaomeng-skill` provides persona bundles, relation artifacts, prompt constraints, and run-state files. It no longer treats an embedded `chat CLI` as the primary packaged capability.

### 4. Save Corrections

If a line is clearly out of character, the correction can be written back into memory and reused in later turns.

## Workflow

### Standard Flow

1. provide the novel file or text
2. generate a character-aware excerpt
3. build a distill or relation prompt payload
4. hand the payload to the host LLM
5. if the host writes `PROFILE.generated.md`, materialize the persona bundle
6. export the relationship graph
7. then enter `act`, `insert`, or `observe`

For multi-character distillation, do not just clip the opening of the novel. Pass `--characters` so the helper can pull windows around the requested cast, especially when one of them first appears much later in the source.

### Incremental Distillation

If a character bundle already exists for the same novel, the skill automatically treats the next distillation as an incremental update:

- detect `data/characters/<novel_id>/<character_name>/`
- merge existing `PROFILE`, split persona files, and `MEMORY` into `request.existing_profiles`
- mark `request.update_mode` as `incremental`
- write the incremental context into `run_manifest.json -> artifacts.distill_context`

The distill payload also exposes `request.excerpt_focus`:

- `requested_characters`
- `matched_characters`
- `missing_characters`
- `strategy`

The host can use this to detect missing cast coverage before the LLM starts distilling from the wrong evidence.

### Automatic Chunking For Long Novels

When the excerpt becomes too large, the skill now switches to chunked mode automatically instead of forcing the host to guess a smaller limit:

- `request.chunk_mode = chunked`
- `meta.chunk_count` shows how many chunks were created
- `meta.merge_required = true`
- `chunks[]` contains ready-to-run partial payloads
- `merge_payload` provides the template for merging chunk drafts into the final artifact

Recommended host flow:

1. check whether the payload is `chunked`
2. if yes, run the LLM over `chunks[]` in order
3. place each partial result into `merge_payload.request.chunk_drafts`
4. run one final merge call to obtain the final `PROFILE.generated.md` or `RELATION_GRAPH`

Short inputs still stay on the old single-pass path.

### Distill Post-Process

Once the host LLM writes `PROFILE.generated.md`, do not stop at that single file.  
Run `tools/materialize_persona_bundle.py` immediately to materialize the canonical profile into a complete persona bundle, including:

- `SOUL.generated.md`
- `GOALS.generated.md`
- `STYLE.generated.md`
- `TRAUMA.generated.md`
- `IDENTITY.generated.md`
- `BACKGROUND.generated.md`
- `CAPABILITY.generated.md`
- `BONDS.generated.md`
- `CONFLICTS.generated.md`
- `ROLE.generated.md`
- `AGENTS.generated.md`
- `MEMORY.generated.md`
- `NAVIGATION.generated.md`

### Dialogue Handoff

After distillation and graph export complete, the host can enter dialogue directly. Recommended host inputs:

- `PROFILE.md`
- split persona files such as `SOUL.md`, `GOALS.md`, and `STYLE.md`
- `MEMORY.md`
- relationship markdown
- graph HTML / SVG
- `run_manifest.json`

Host mode interpretation:

- `act`: the user speaks as one character
- `insert`: the user enters the scene as themselves
- `observe`: the user watches the cast continue the scene

If the host also wants next-beat recommendation, scene-shift text, and auto-opening hints, it can additionally call:

- `python tools/build_scene_recommendation_payload.py --context-file <context.json>`

Reference example:

- `examples/scene_recommendation_context.example.json`

## Installation

### OpenClaw

```bash
openclaw skills install wkbin/zaomeng-skill
```

### ClawHub

```bash
npx clawhub@latest install zaomeng-skill
pnpm dlx clawhub@latest install zaomeng-skill
bunx clawhub@latest install zaomeng-skill
```

### Install Into A Local Skills Directory

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

## Helper Commands

```bash
python tools/init_host_run.py --novel <path> --characters A,B --output <run_manifest.json>
python tools/prepare_novel_excerpt.py --novel <path> [--characters A,B] [--max-sentences 120] [--max-chars 50000]
python tools/build_prompt_payload.py --mode distill|relation --novel <path> [--characters A,B] [--characters-root <data/characters or data/characters/<novel_id>>] [--update-mode auto|create|incremental]
python tools/materialize_persona_bundle.py --profile-file <character-dir/PROFILE.generated.md>
python tools/export_relation_graph.py --relations-file <relation-result.md>
python tools/verify_host_workflow.py --characters-root <characters/<novel_id>> [--relations-file <relation-result.md>]
python tools/build_scene_recommendation_payload.py --context-file <context.json>
```

```bash
python tools/prepare_novel_excerpt.py --novel shirizhongyan.txt --characters 齐夏,肖冉,章晨泽 --max-chars 50000
```

If the JSON output includes `chunks` and `merge_payload`, the host should treat that run as an automatic chunked distillation / extraction flow.

If the host wants to record execution progress into `run_manifest.json`, it can also call:

```bash
python tools/update_run_progress.py --run-manifest <run_manifest.json> --stage chunk_started --message "running chunk 1" --chunk-capability distill --chunk-mode chunked --chunk-count 6 --current-chunk 1 --chunk-label start-1 --chunk-status running --merge-required --merge-status pending
```

This will populate:

- `progress.chunking`
- `summary.chunking`

## Recommended Usage

Do not jump into chat first.  
**Provide the novel, distill the characters, then enter dialogue.**

The most common user flow is:

1. provide the novel file or path
2. specify which characters to distill
3. let the host report stage-by-stage progress
4. inspect persona files or relationship graphs
5. enter `act`, `insert`, or `observe`

## Examples

### Distill

```text
Distill Lin Daiyu and Jia Baoyu from this novel
```

```text
Extract character profiles for Liu Bei, Zhang Fei, and Guan Yu
```

### Enter act

```text
Let me play Jia Baoyu and have Lin Daiyu reply
```

```text
I will speak as Baoyu, and you let Daiyu answer me
```

### Enter observe

```text
Start a Liu Bei, Zhang Fei, and Guan Yu group chat
```

```text
Let everyone say one line about whether to ally with Sun Quan
```

### Enter insert

```text
Let me enter Dream of the Red Chamber as myself and talk with Lin Daiyu and Jia Baoyu
```

```text
Put me into a Three Kingdoms scene as a newly arrived guest, and let me speak with Liu Bei and the others
```

## Persona Bundle Layout

The character directory usually looks like this:

```text
runtime/data/characters/<novel_id>/<character_name>/
```

Common files:

- `PROFILE.generated.md`
- `PROFILE.md`
- `NAVIGATION.generated.md`
- `NAVIGATION.md`
- `MEMORY.generated.md`
- `MEMORY.md`

Depending on available evidence, split persona files may also exist:

- `SOUL.generated.md`
- `GOALS.generated.md`
- `STYLE.generated.md`
- `TRAUMA.generated.md`
- `IDENTITY.generated.md`
- `BACKGROUND.generated.md`
- `CAPABILITY.generated.md`
- `BONDS.generated.md`
- `CONFLICTS.generated.md`
- `ROLE.generated.md`

## Constraint Files

- `references/output_schema.md`
  output format and field definition
- `references/style_differ.md`
  anti-homogenization and style differentiation
- `references/logic_constraint.md`
  persona boundaries and anti-OOC rules
- `references/validation_policy.md`
  output validation and self-check policy
- `references/capability_index.md`
  host-facing index for `distill`, `materialize`, `export_graph`, and `verify_workflow`
- `references/chat_contract.md`
  host-facing handoff guidance for `act`, `insert`, and `observe`

## License

`MIT-0`
