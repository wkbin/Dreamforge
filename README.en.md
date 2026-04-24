# zaomeng

[中文](README.zh.md) | [English](README.en.md)

Local toolkit for novel character distillation, relationship extraction, and roleplay chat. The current version runs on a local rule engine and does not require any cloud model or API key.

## Quick Start

```bash
pip install -r requirements.txt
cp config.yaml.example config.yaml
python -m src.core.main distill --novel data/sample_novel.txt --force
python -m src.core.main extract --novel data/sample_novel.txt --force
```

On Windows:

```powershell
Copy-Item config.yaml.example config.yaml
```

## Quick Integration

Repository:

```text
https://github.com/wkbin/zaomeng.git
```

### OpenClaw

Recommended install:

```bash
openclaw skills install wkbin/zaomeng-skill
```

Repository script install (for local development or environments without ClawHub):

```bash
python scripts/install_skill.py --openclaw-dir <openclaw-skills-root>
```

Manual install, choose one:

```bash
# Option 1: clone the repo and copy the adapter
git clone https://github.com/wkbin/zaomeng.git
mkdir -p <openclaw-skills-root>/zaomeng-skill
cp zaomeng/openclaw-skill/SKILL.md <openclaw-skills-root>/zaomeng-skill/SKILL.md
```

```bash
# Option 2: download only the adapter file
mkdir -p <openclaw-skills-root>/zaomeng-skill
curl -L https://raw.githubusercontent.com/wkbin/zaomeng/main/openclaw-skill/SKILL.md -o <openclaw-skills-root>/zaomeng-skill/SKILL.md
```

Command mapping inside OpenClaw:

```bash
python -m src.core.main distill --novel <path> [--characters A,B] [--force]
python -m src.core.main extract --novel <path> [--force]
python -m src.core.main chat --novel <path-or-name> --mode observe|act [--character <name>]
python -m src.core.main view --character <name> [--novel <path-or-name>]
python -m src.core.main correct --session <id> --message <raw> --corrected <fixed>
```

The same `zaomeng-skill` also works in Hermes Agent with the same command mapping, so there is no separate integration path to maintain in the docs.

### Your Own Project

Recommended via ClawHub CLI:

```bash
npx clawhub@latest install zaomeng-skill
```

If your project already has a `skills/` root, you can also use the repository install script:

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

If you want to install directly into a project root:

```bash
python scripts/install_skill.py --project-root <your-project-root>
```

To override the installed skill folder name:

```bash
python scripts/install_skill.py --project-root <your-project-root> --skill-name zaomeng-skill
```

If you prefer not to run the installer script, you can integrate manually:

```bash
# Option 1: clone the repo and copy the whole generic skill directory
git clone https://github.com/wkbin/zaomeng.git
mkdir -p <your-project-root>/skills
cp -r zaomeng/skills/zaomeng-skill <your-project-root>/skills/
```

```bash
# Option 2: download only the generic SKILL.md
mkdir -p <your-project-root>/skills/zaomeng-skill
curl -L https://raw.githubusercontent.com/wkbin/zaomeng/main/skills/zaomeng-skill/SKILL.md -o <your-project-root>/skills/zaomeng-skill/SKILL.md
```

## Core Commands

```bash
python -m src.core.main distill --novel data/sample_novel.txt --force
python -m src.core.main distill --novel data/sample_novel.txt --characters 林黛玉,贾宝玉 --force
python -m src.core.main extract --novel data/sample_novel.txt --force
python -m src.core.main chat --novel data/sample_novel.txt --mode observe
python -m src.core.main chat --novel data/sample_novel.txt --mode act --character 林黛玉
python -m src.core.main view --character 林黛玉 --novel data/sample_novel.txt
python -m src.core.main correct --session <ID> --message "<raw>" --corrected "<fixed>" --character 林黛玉
```

Inline chat commands:

- `/save`
- `/reflect`
- `/correct 角色|对象|原句|修正句|原因`
- `/quit`

## Output Layout

Artifacts are isolated by novel to avoid cross-novel contamination:

- `data/characters/<novel_id>/`
- `data/relations/<novel_id>/`
- `data/sessions/`
- `data/corrections/`

For `data/sample_novel.txt`, the default output is:

- `data/characters/sample_novel/*.json`
- `data/relations/sample_novel/sample_novel_relations.json`

## Current Implementation Notes

- Input formats: `.txt` and `.epub`
- Distilled profiles include `novel_id`, `source_path`, and lightweight evidence counters
- Relationships are created only for character pairs that co-occur in the same sentence
- Chat sessions load character and relationship assets from the scoped novel namespace first

## Project Structure

```text
src/core/main.py
src/modules/distillation.py
src/modules/relationships.py
src/modules/chat_engine.py
src/modules/reflection.py
src/modules/speaker.py
src/utils/
tests/test_relation_behavior.py
```

## License

MIT
