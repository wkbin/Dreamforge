---
name: openclaw-zaomeng
description: OpenClaw adapter for zaomeng local character distillation, relationship extraction, and roleplay chat.
---

# OpenClaw Adapter

Use these CLI commands as the canonical entrypoints:

- `python -m src.core.main distill --novel <path> [--characters A,B] [--force]`
- `python -m src.core.main extract --novel <path> [--output <path>] [--force]`
- `python -m src.core.main chat --novel <path-or-name> --mode observe --message "<prompt>"`
- `python -m src.core.main chat --novel <path-or-name> --mode act --character <name> --message "<prompt>"`
- `python -m src.core.main chat --novel <path-or-name> --mode observe|act [--character <name>]`
- `python -m src.core.main view --character <name> [--novel <path-or-name>]`
- `python -m src.core.main correct --session <id> --message <raw> --corrected <fixed> [--character <name>]`

## Chat Execution Rule

- Prefer `chat ... --message "..."` for agent-driven runs.
- Treat plain `chat` without `--message` as an interactive terminal session.
- Before running interactive `chat`, confirm:
  - novel path or novel name
  - mode: `observe` or `act`
  - controlled character when mode is `act`
  - whether `distill` has already been run
  - whether `extract` has already been run if relation-aware replies are desired
- Use these starter turns when the user does not provide one:
  - `observe`: `请让大家围绕这件事各说一句。`
  - `act`: `我先表态，你们再接。`
- Do not claim PTY failure and do not simulate stdin or auto-script chat turns unless the user explicitly asks for that behavior.

## I/O Contract

- Character profiles: `data/characters/<novel_id>/<character>.json`
- Relationship graph: `data/relations/<novel_id>/<novel_id>_relations.json`
- Session data: `data/sessions/<session_id>.json`
- Correction data: `data/corrections/correction_<session>_<ts>.json`

## Runtime Rules

- Require confirmation before high-cost distill/extract runs unless `--force` is present.
- In agent-driven runs, do not wait for confirmation prompts and then improvise stdin injection.
- First ask the user whether the run should proceed, then execute `distill` or `extract` with `--force`.
- Keep chat turns local-only and compact.
- Apply correction memory before speech generation.
- Preserve UTF-8 JSON outputs with stable keys.
- Do not require cloud LLM or OpenAI API keys.
