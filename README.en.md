# zaomeng

[中文](README.md) | [English](README.en.md)

> *“Some characters were not fully written away. They were only never truly awakened.”*

**Let characters step off the page and breathe a second time.**

[![License: AGPL-3.0-only](https://img.shields.io/badge/License-AGPL--3.0--only-8A2BE2.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-6f42c1.svg)](https://github.com/wkbin/zaomeng)
[![LLM-first](https://img.shields.io/badge/Workflow-LLM--first-2ea44f.svg)](https://github.com/wkbin/zaomeng)

&nbsp;

[Install](#install) · [Usage](#usage) · [Incremental Distillation](#incremental-distillation) · [中文](README.md)

Distill Chinese novel characters into reusable persona bundles, export relationship graphs, and let them speak again with their own personality, stance, bonds, and memory intact.

`zaomeng` is not a generic chatbot project.  
It is a focused workflow for character distillation, relationship extraction, graph export, and in-character interaction.

- distill character bundles from novels
- extract relationships and export graphs
- let characters enter `act` / `insert` / `observe`

If what you want is not “an AI chatting pleasantly,” but “Lin Daiyu sounds like Lin Daiyu, Qi Xia sounds like Qi Xia, and a whole cast can share one scene without collapsing into one voice,” that is exactly what this project is trying to do.

It is not trying to put a thin chatbot layer on top of fictional people.  
It is trying to do something more demanding:

- make characters reusable beyond a single summary
- make relationships visible, traceable, and reusable
- make dialogue sound like something that specific person would actually say

## Install 🚀

### Install the skill

The main publishable surface of this project is the `zaomeng-skill/` bundle.

```bash
# Install into OpenClaw
openclaw skills install wkbin/zaomeng-skill

# Install into ClawHub
npx clawhub@latest install zaomeng-skill
pnpm dlx clawhub@latest install zaomeng-skill
bunx clawhub@latest install zaomeng-skill

# Install into a local skills directory
python scripts/install_skill.py --skills-dir <your-skills-root>
```

### Dependencies 🧩

```bash
pip install -r requirements.txt
```

If you only want to run the Web UI or use the one-line installer, this is usually enough:

```bash
pip install -r requirements.runtime.txt
```

### Web UI 🖥️

If you want a direct product entrypoint instead of starting from the skill or CLI, you can run the Web UI.

#### One-line Install (Linux / macOS / WSL2 / Termux)

```bash
curl -fsSL https://raw.githubusercontent.com/wkbin/zaomeng/main/scripts/install.sh | bash
source ~/.bashrc
zaomeng
```

If you use `zsh`, replace the second line with:

```bash
source ~/.zshrc
```

The installer will:

- download the repository into `~/.local/share/zaomeng`
- create an isolated virtual environment
- install the lighter `requirements.runtime.txt` by default
- create a `~/.local/bin/zaomeng` launcher
- add `~/.local/bin` to your shell `PATH`

After installation, `zaomeng` starts the Web UI by default. You can also run:

```bash
zaomeng uninstall
zaomeng update
zaomeng web --reload
zaomeng bump-web-assets
zaomeng install-skill --skills-dir <your-skills-root>
```

#### Manual Start

If you prefer to clone the repository and run it locally, use:

```bash
git clone https://github.com/wkbin/zaomeng.git
cd zaomeng
pip install -r requirements.txt
python scripts/run_webui.py --reload
```

Then open `http://127.0.0.1:8000` and go through the full workflow in one place:

1. configure a model first
2. upload a novel and lock the cast
3. automatically distill characters and generate the relationship graph
4. enter `act` / `insert` / `observe`

The current Web UI already supports:

- a guided linear workflow, without requiring the user to understand the skill ecosystem first
- saving model settings and launching distillation directly from the UI
- volume-aware excerpt suggestions, including estimated chunk count, model calls, rough token cost, and time range
- tracking character distillation progress and graph artifacts in one place
- a bookshelf-style workbench where you can return to a run and keep distilling, review personas, inspect relations, or jump into chat
- persona review pages with key-field completion, evidence-gap checks, and secondary-field tuning
- creating, editing, selecting, and reusing scene cards, self cards, and opening presets
- automatic next-scene recommendation during chat, with in-session scene switching
- session restore, recent-session resume, group chat continuation, and direct workbench entry into a scene
- dialogue context compression that trims persona / relation context around active participants and injects session memory summaries
- viewing transcripts, continuing group chat, and deleting recent sessions in the same interface
- incremental distillation and re-distillation entrypoints

If you want to use `zaomeng` as an actual product entry instead of only as a skill companion, the Web UI is now the most complete primary surface.

## What You Can Do With It ✨

### 1. Distill Characters 🎭

Give it a novel, and it will try to build reusable persona bundles from the original text, including:

- core identity
- core motivation
- personality tone
- speaking style
- decision logic
- emotional triggers
- key bonds
- character arc

The goal is not a one-page summary. The goal is a persona bundle that can keep supporting later dialogue, roleplay, correction, and incremental updates.

### 2. Export Relationship Graphs 🕸️

It does not stop at structured relationship fields. It also exports visual graphs so you can quickly see:

- who trusts whom
- who depends on whom
- where tension, rivalry, or conflict lives

Typical outputs include:

- relationship Markdown
- Mermaid source
- HTML graph
- SVG graph

### 3. Enter Character Interaction 💬

After distillation, there are now **3 modes**:

- `act`: you speak as one character, either one-on-one or by joining a group scene directly
- `insert`: you do not play an existing character; you enter the scene as yourself and interact with the cast directly
- `observe`: you stay out of the scene and watch several characters carry the scene forward

The simplest way to think about them:

- use `act` when you want to step in as a role
- use `insert` when you want yourself to enter the fictional world
- use `observe` when you want to watch the cast interact without speaking as anyone

In `insert`, the first session creates a lightweight scene card for you, usually including:

- how the cast should address you
- what identity you have inside the scene
- whether you want natural, immersive, or probing interaction
- how much your presence should affect the scene

The chat entry is also no longer just “pick characters and start talking.”  
You can now layer these helpers before or during a session:

- scene cards: define location, atmosphere, dramatic drive, and opening situation for a scene
- self cards: prepare your identity, tone, motive, and in-scene role for `insert`
- opening presets: bundle mode, participants, scene card, and self card into a reusable starting setup
- automatic scene recommendation: while a session is running, the system can suggest a more suitable next scene card

## Usage 🛠️

The recommended order is simple:

1. provide the novel text or file
2. specify which characters you want distilled
3. wait for persona bundles and the relationship graph
4. then enter `act`, `insert`, or `observe`

### Natural-language requests that work well

```text
Distill Lin Daiyu, Jia Baoyu, and Xue Baochai from this novel
```

```text
After distillation, put Lin Daiyu, Jia Baoyu, and Xue Baochai into group chat mode
```

```text
Let me play Jia Baoyu. Lin Daiyu should answer me
```

```text
Let me enter Dream of the Red Chamber as myself and talk with Lin Daiyu and Jia Baoyu
```

```text
Generate the relationship graph. I want the HTML and SVG versions
```

## How It Works Now 🧠

The current version is **LLM-first**:

- the host or runtime LLM does the actual language generation
- `zaomeng` prepares prompts, persona bundles, relationship context, and helper outputs
- `zaomeng-skill` prefers reusing the model capability already provided by the host

The emphasis is no longer “hardcode a pile of rules and glue lines together.” The emphasis is giving the model clearer persona, relationship, and scene constraints so the output sounds more like the source character.

At the same time, the Web UI dialogue pipeline is now more serious about surviving long sessions:

- sessions maintain summarized memory instead of endlessly stuffing raw history into context
- persona context is trimmed toward currently active participants instead of expanding every character every turn
- relationship excerpts are cut down to what the current scene and participants actually need
- reply suggestions, observer-mode nudges, and scene-switch prompts all reuse this compressed context

## Incremental Distillation ♻️

The project supports incremental distillation.

If a character from the same novel has already been distilled, the next pass does not blindly rebuild from scratch. It tries to reuse:

- `PROFILE`
- split persona files
- `MEMORY`
- user corrections

This works especially well for:

- serialized fiction with new chapters
- long novels processed in batches
- repeated correction loops that keep improving persona quality

## Project Layout 📦

The repository is currently split into three main layers:

- `src/`: core source code
- `zaomeng-skill/`: the publishable skill bundle
- `tests/`: regression tests

The most important assets inside the skill bundle are usually:

- `prompts/`
- `references/`
- `tools/prepare_novel_excerpt.py`
- `tools/build_prompt_payload.py`
- `tools/export_relation_graph.py`

## One-line Summary ✨

`zaomeng` is not trying to be “an AI that can talk.”  
It is trying to let fictional people speak again with their own personality, relationships, tone, and memory intact.

## License

Main project: `AGPL-3.0-only`  
`zaomeng-skill`: `MIT-0`
