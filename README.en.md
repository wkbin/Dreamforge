# 造梦.skill

[中文](README.md) | [English](README.en.md)

Local toolkit for novel character distillation, relationship extraction, roleplay chat, and correction memory.

This project is not meant to be a generic chatbot. Its purpose is to turn novel text into reusable character assets:

- character profiles
- relationship graphs
- dialogue constraints
- correction memory
- agent-ready skill packages

The current version runs on a local rule engine and does not require any cloud model or API key. It is suitable for offline analysis, roleplay experiments, fanfiction workflows, literature research, and agent orchestration.

## What It Does

### 1. Character Distillation

Extract major characters from `.txt` or `.epub` novels and build structured profiles, including:

- `core_traits`
- `values`
- `speech_style`
- `typical_lines`
- `decision_rules`
- `arc`
- `evidence`

Useful for:

- organizing character sheets
- summarizing original character design
- producing reusable assets for later chat and story experiments

### 2. Relationship Extraction

Build a relationship graph from the novel. Current fields include:

- `trust`
- `affection`
- `power_gap`
- `conflict_point`
- `typical_interaction`

The current edge-building strategy is sentence-level co-occurrence, which is more conservative and more useful for downstream roleplay than rough chunk-level co-occurrence.

### 3. Roleplay Chat

Start local multi-character dialogue using distilled profiles and relationship data.

Supported modes:

- `observe`
  You provide a scene or opening prompt, and the system lets characters react naturally.
- `act`
  You control one character, and the rest respond according to profile and relationship state.

During chat, the system supports:

- `/save`
- `/reflect`
- `/correct character|target|original|corrected|reason`
- `/quit`

### 4. Correction Memory

When a character says something clearly out of character, you can save a correction:

```bash
python -m src.core.main correct \
  --session <session_id> \
  --message "Baoyu says he wants to leave the Jia household and become a merchant" \
  --corrected "Baoyu has little interest in worldly ambition and would rather stay among poetry, gardens, and the inner household" \
  --character 贾宝玉
```

Corrections are stored in `data/corrections/` and later chat runs try to avoid repeating similar OOC behavior.

### 5. Fast Agent Integration

The repository ships with:

- `openclaw-skill/`
- `hermes-skill/`
- `skills/zaomeng-skill/`
- `clawhub-zaomeng-skill/`

You can plug the project into OpenClaw, Hermes Agent, ClawHub CLI, or your own local project.

## Core Play Patterns

### Pattern 1: Distill characters first, then enter chat

Using *Dream of the Red Chamber* as an example:

```bash
python -m src.core.main distill --novel data/hongloumeng.txt --characters 林黛玉,贾宝玉 --force
python -m src.core.main extract --novel data/hongloumeng.txt --force
```

This generates novel-scoped outputs:

- `data/characters/hongloumeng/*.json`
- `data/relations/hongloumeng/hongloumeng_relations.json`

The system now supports reliable two-character aliases when explicit targets are provided, for example:

- `林黛玉 -> 黛玉`
- `贾宝玉 -> 宝玉`

So even if the source text frequently uses `黛玉` and `宝玉` instead of full names, distillation and relationship extraction can still match the evidence more reliably.

### Pattern 2: Observe mode

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode observe --message "Please let everyone speak around Daiyu's arrival at the Jia household."
```

This is not a fire-and-forget command. It is an interactive session, so you should provide an opening prompt such as:

```text
Please let everyone speak naturally around Daiyu's arrival at the Jia household.
```

Useful for:

- observing natural interaction between characters
- seeing how relationship values affect tone and behavior
- checking whether the distilled personas feel faithful to the source

### Pattern 3: Act mode

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode act --character 林黛玉 --message "Baoyu, why are you looking at me like that today?"
```

In this mode, you control the named character and others reply. Good first turns include:

```text
I will speak first. The rest of you continue from there.
```

Or something more scene-specific:

```text
Baoyu, why did you arrive so late again today?
```

Useful for:

- immersive roleplay
- testing a character under a specific relationship state
- branching-scene experiments

### Pattern 4: Inspect a character profile

```bash
python -m src.core.main view --character 林黛玉 --novel data/hongloumeng.txt
python -m src.core.main view --character 贾宝玉 --novel data/hongloumeng.txt
```

`view` currently shows one character at a time. For multiple characters, browse:

- `data/characters/<novel_id>/`

Useful for:

- checking distillation quality
- comparing values and speech styles across roles
- preparing manual adjustments

### Pattern 5: Edit relationships, then re-enter chat

If the automatic relationship extraction is not detailed enough, you can edit the relation file manually and then run chat again:

- inspect `data/relations/hongloumeng/hongloumeng_relations.json`
- adjust or add a specific pair
- run `chat` again

For example:

```json
{
  "林黛玉_贾宝玉": {
    "trust": 8,
    "affection": 9,
    "power_gap": 2,
    "conflict_point": "Golden Jade destiny vs. Wood-Stone bond",
    "typical_interaction": "Daiyu questions him, Baoyu tries to soothe her, tension softens briefly"
  }
}
```

This is especially useful for relationships with layered emotional history that current rules cannot fully reconstruct.

## Dream Of The Red Chamber Examples

### Example 1: Observe Daiyu and Baoyu

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode observe --message "Scene: Inside Rongguo House, Daiyu has just arrived, and Baoyu is meeting her for the first time. Let the relevant characters begin naturally."
```

Suggested first turn:

```text
Scene: Inside Rongguo House, Daiyu has just arrived, and Baoyu is meeting her for the first time. Let the relevant characters begin naturally.
```

### Example 2: You play Daiyu

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode act --character 林黛玉 --message "Baoyu, why are you looking at me like that today?"
```

You might type:

```text
Baoyu, why are you looking at me like that today?
```

### Example 3: Correct an OOC reply

```bash
python -m src.core.main correct \
  --session <session_id> \
  --message "Baoyu plans to leave home and build a business" \
  --corrected "Baoyu despises worldly advancement and would rather remain in the world of poetry, gardens, and the inner chambers" \
  --character 贾宝玉
```

## Good Use Cases

### 1. Fanfiction workflows

- place original characters into alternate scenarios
- test how a scene changes if one crucial line is different
- draft missing conversations between known characters

### 2. Literature research

- compare character traits in a structured way
- analyze the social graph of a novel
- study dialogue style and interaction patterns

### 3. Story experiments

- begin from a canonical scene prompt
- modify a conflict point
- observe how different relationship values change behavior

### 4. Agent use

- reuse characters as persona assets
- plug them into OpenClaw / Hermes / ClawHub workflows
- use them for multi-agent simulation, branching narrative experiments, or persona-constraint testing

## Configuration

### 1. Value dimensions

You can adapt `values_dimensions` in `config.yaml` to better fit a specific work:

```yaml
distillation:
  values_dimensions:
    - "情缘"
    - "才情"
    - "命运"
    - "家族责任"
    - "个人追求"
    - "礼教束缚"
```

### 2. Chat parameters

```yaml
chat_engine:
  max_history_turns: 20
  max_speakers_per_turn: 6
  token_limit_per_turn: 800
```

Useful for:

- keeping more context
- allowing more speakers per round
- increasing dialogue capacity in dense scenes

## Command Overview

```bash
python -m src.core.main distill --novel <path> [--characters A,B] [--output <dir>] [--force]
python -m src.core.main extract --novel <path> [--output <path>] [--force]
python -m src.core.main chat --novel <path-or-name> --mode observe|act [--character <name>] [--session <id>] [--message <text>]
python -m src.core.main view --character <name> [--novel <path-or-name>]
python -m src.core.main correct --session <id> --message <raw> --corrected <fixed> [--character <name>] [--target <name>] [--reason <text>]
```

Interaction notes:

- `chat` is interactive, so prepare the first user turn before entering the session
- `distill` and `extract` ask for confirmation by default
- in agent-driven or tool-driven flows, get user approval first and then use `--force`

## Quick Integration

Repository:

```text
https://github.com/wkbin/zaomeng.git
```

### OpenClaw

Recommended:

```bash
openclaw skills install wkbin/zaomeng-skill
```

### Your Own Project

Recommended via ClawHub CLI:

```bash
npx clawhub@latest install zaomeng-skill
```

If your project already has a `skills/` directory:

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

## Current Implementation Notes

- Input formats: `.txt` and `.epub`
- Character profiles are written to `data/characters/<novel_id>/`
- Relationship graphs are written to `data/relations/<novel_id>/`
- Chat loads novel-scoped character and relation data first
- Relationship scoring is currently rule-based and sentence-scoped: reliable, but still limited
- `view` currently shows one character at a time
- The current system is local-rule-engine-first and does not rely on external cloud models

## Project Structure

```text
src/core/main.py
src/modules/distillation.py
src/modules/relationships.py
src/modules/chat_engine.py
src/modules/reflection.py
src/modules/speaker.py
src/utils/
openclaw-skill/
hermes-skill/
skills/zaomeng-skill/
clawhub-zaomeng-skill/
tests/test_relation_behavior.py
```

## License

[MIT](LICENSE)
