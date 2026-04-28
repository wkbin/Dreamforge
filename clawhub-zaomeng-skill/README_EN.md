# zaomeng-skill

`zaomeng-skill` is a skill package for Chinese novel character distillation, relationship extraction, one-on-one roleplay, and group character chat.

It is not a generic chat template. It is a local rule-based workflow built around one principle: distill first, then let characters speak according to their profiles.

More precisely:

- `zaomeng` is responsible for character distillation, relationship extraction, persona navigation, persistent memory, and OOC constraints
- by default, `zaomeng` can still be used purely as the persona-and-constraint layer
- when a real LLM is configured, `zaomeng chat` can now also generate the final natural reply under persona, relation, and memory constraints

License: `MIT-0` (MIT No Attribution)

## What's New In This Version

The current release line is `3.1.0`. The main changes are:

- markdown-first storage: persona data no longer treats legacy JSON as the source of truth
- `clawhub-zaomeng-skill` now includes an embedded minimal runtime, instead of treating runtime cloning from an external repository as the primary path
- natural-language-first usage: distill first, then enter `act` or `observe`
- layered persona constraints: format, anti-homogenization, and logic floor are separated
- phase-1 dialogue upgrade: real LLM chat generation, ordered group-chat interactions, and optional silence for low-relevance characters

## Dialogue Generation Modes

You can now use chat in two ways:

- `local-rule-engine`
  Fully local rule-based generation with no external model call.
- Real LLM
  `zaomeng` first prepares persona, relation, and memory constraints, then calls an external model to produce the final reply.

Example configuration:

```yaml
llm:
  provider: "openai"               # or openai-compatible / anthropic / ollama
  model: "gpt-4.1-mini"
  api_key: ""
  api_key_env: "OPENAI_API_KEY"
  base_url: ""
  temperature: 0.7
  max_tokens: 300

chat_engine:
  generation_mode: "auto"          # auto / rule-only / llm-only
  enable_turn_interactions: true
  allow_character_silence: true
  min_reply_relevance: 4
```

## What It Does

### 1. Distill Characters

Extract character profiles from raw novel text and cover a richer set of dimensions, such as:

- core identity
- core motivation
- personality base
- decision logic
- character arc
- key bonds
- language expression style
- value tradeoff system
- hidden desire
- private self

### 2. Extract Relationships

Extract pairwise relationship graphs from same-scene interactions and generate both graph-level and character-side relation layers.

### 3. Enter Character Chat

Two main interaction modes are supported:

- `act`
  You control one character's line, and the other characters respond in character
- `observe`
  Multiple characters interact around a scene, topic, or opening line

### 4. Save Corrections

If a line is clearly out of character, you can write the correction back into memory and keep using that correction in later dialogue.

## Installation

### OpenClaw

```bash
openclaw skills install wkbin/zaomeng-skill
```

### ClawHub

```bash
npx clawhub@latest install zaomeng-skill
```

```bash
pnpm dlx clawhub@latest install zaomeng-skill
```

```bash
bunx clawhub@latest install zaomeng-skill
```

### Install Into A Local Skills Directory

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

## Runtime Requirements

To run the real workflow, the host environment should support:

- local Python command execution
- `PyYAML`
- `ebooklib` when reading `.epub`
- optional `tiktoken` for more accurate token estimation

The packaged runtime entrypoint inside the skill is:

```text
runtime/zaomeng_cli.py
```

The runtime source tree is split into two layers:

- thin runtime-owned wrappers: `runtime/src/core/main.py`, `runtime/src/core/runtime_factory.py`, `runtime/src/core/logging_utils.py`
- mirrored shared implementation: `runtime/src/core/cli_app.py`, `runtime/src/core/runtime_parts.py`, `runtime/src/core/logging_setup.py`, plus shared `modules/` and `utils/`

## Recommended Usage Flow

The correct order is not to jump into chat immediately.  
**Provide the novel first, distill the characters, and only then enter chat.**

The most common user flow is:

1. provide the novel file or file path
2. say which characters you want distilled in natural language
3. after distillation finishes, enter `act` or `observe`

## Natural-Language Examples

### Distill

```text
Distill Lin Daiyu and Jia Baoyu for me
```

```text
Extract personas for Liu Bei, Zhang Fei, and Guan Yu from this novel
```

### Enter Act Mode

```text
Let me play Jia Baoyu and chat with Lin Daiyu
```

```text
I will play Baoyu. Let Daiyu reply to me
```

### Enter Observe Mode

```text
Enter Liu Bei, Zhang Fei, Guan Yu group chat mode
```

```text
Let everyone say one line about the alliance with Sun Quan
```

## CLI Examples

If you run the packaged runtime directly, use commands like these:

```bash
py -3 runtime/zaomeng_cli.py distill --novel <path> --characters A,B
py -3 runtime/zaomeng_cli.py extract --novel <path>
py -3 runtime/zaomeng_cli.py chat --novel <path-or-name> --mode auto --message "Let me play A and chat with B"
py -3 runtime/zaomeng_cli.py view --character <name> --novel <path-or-name>
py -3 runtime/zaomeng_cli.py correct --session <id> --message <raw> --corrected <fixed> --character <name>
```

## Persona Bundle Structure

The main character storage is now a markdown persona bundle. The common directory shape is:

```text
runtime/data/characters/<novel_id>/<character_name>/
```

Common files:

- `NAVIGATION.generated.md`
- `NAVIGATION.md`
- `PROFILE.generated.md`
- `PROFILE.md`
- `RELATIONS.generated.md`
- `RELATIONS.md`
- `MEMORY.md`

Depending on available evidence, optional focused persona files may also be generated:

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

This version splits constraints into three layers:

- `references/output_schema.md`
  format and field contract
- `references/style_differ.md`
  anti-homogenization and style differentiation
- `references/logic_constraint.md`
  global persona floor, anti-OOC rules, and mode boundaries

If you are checking output quality, these three files should be read together rather than reading only the schema.

## README.md vs SKILL.md

- `README.md` is for users and focuses on installation, usage, and outputs
- `SKILL.md` is for hosts and agents and focuses on execution rules, invocation constraints, and forbidden behavior

## Publishing Notes

If you publish this skill on its own, it is best to include at least:

- `README.md`
- `README_EN.md`
- `SKILL.md`
- `INSTALL.md`
- `MANIFEST.md`
- `PUBLISH.md`
- `prompts/`
- `references/`
- `runtime/`

## License

`MIT-0`
