# zaomeng.skill

[中文](README.md) | [English](README.en.md)

`zaomeng` is a local novel-character toolkit.

It does three things:

- distills characters from novels
- extracts character relationships from novels
- lets those characters enter group chat or roleplay in character

It is not a generic chatbot.  
It is better understood as a fiction character engine.

License: the main project is `AGPL-3.0-only`; the `clawhub-zaomeng-skill` subdirectory remains `MIT-0`

The current recommended direction is:

- markdown-first storage: character and relation data no longer treat legacy JSON as the source of truth
- natural-language first: distill first, then enter `act` / `observe` through natural-language intent
- embedded minimal runtime in the skill package: `clawhub-zaomeng-skill` now ships with a packaged minimal runtime
- layered constraints: `output_schema.md` handles format, `style_differ.md` handles anti-homogenization, and `logic_constraint.md` handles persona-stability and anti-OOC rules
- layered dialogue generation: `zaomeng` keeps persona, relation, and memory constraints, while a real LLM can turn them into more natural final dialogue when configured

## Dialogue Generation

Chat now supports two generation paths:

- `local-rule-engine`
  Fully local rule-based generation with no external model call.
- Real LLM chat generation
  `zaomeng` prepares persona, relation, and memory constraints first, then a real model produces the final line. In group chat, later speakers can see replies already produced earlier in the same turn.

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

## Installation

You can choose the installation path that matches how you want to use it.

Important:

- the current `clawhub-zaomeng-skill` package includes an embedded minimal runtime, so runtime cloning is no longer the primary path
- `openclaw skills install ...` and `clawhub ... install ...` install the skill package; `clawhub-zaomeng-skill` includes the packaged runtime plus documentation
- if the host cannot execute local Python commands, or lacks required dependencies, the real workflow still cannot run
- if you want to modify code, run tests, or use the main repository CLI directly, cloning the repository is still the best option

### 1. Clone the repository directly

If you want to run the full project locally, use the CLI directly, or modify the code, cloning the repo is the best option:

```bash
git clone https://github.com/wkbin/zaomeng.git
cd zaomeng
```

### 2. Install into OpenClaw

If you mainly want to use it as a skill inside OpenClaw:

```bash
openclaw skills install wkbin/zaomeng-skill
```

This installs the skill package, not the full `zaomeng` development repository.  
The current `clawhub-zaomeng-skill` package includes an embedded minimal runtime, so hosts that allow local command execution can use the packaged runtime directly.

### 3. Install with ClawHub

If you use ClawHub, pick the command that matches your toolchain:

```bash
npx clawhub@latest install zaomeng-skill
```

```bash
pnpm dlx clawhub@latest install zaomeng-skill
```

```bash
bunx clawhub@latest install zaomeng-skill
```

Again, this installs the skill package, not the full local `zaomeng` development repository.
The current `clawhub-zaomeng-skill` package includes an embedded minimal runtime, so hosts that allow local command execution can use the packaged runtime directly.

### 4. Install into an existing local skills directory

If your own project already has a `skills/` directory, you can also install the skill there:

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

## Runtime Requirement

To run the real workflow, the host environment needs at least one of these:

- the ability to run the main repository CLI directly
- or the ability to run the packaged minimal runtime inside `clawhub-zaomeng-skill`

If the host does not allow local command execution, or lacks required Python dependencies, the real `zaomeng` CLI workflow cannot run.

## Example 1: Act Mode

```
User      ❯  Let me play Jia Baoyu and chat with Lin Daiyu.
            Set the scene at Qinfang Pavilion in the Grand View Garden,
            on a spring afternoon, with Daiyu standing by the bridge watching fish.

zaomeng   ❯  (On a spring afternoon, sunlight filters through willow branches
            and falls across the waters of Qinfang Stream.
            Daiyu stands alone by the bridge, one hand resting lightly
            against the rail as she watches the koi drifting below.
            The wind lifts the edge of her skirt and a few loose strands
            by her temple. She seems lost in thought.
            In her hand is a fallen flower she must have picked up
            without thinking, her fingers holding it a little too tightly.)

User      ❯  Cousin Lin, in weather this warm, why are you standing here alone
            and drifting into thought?
            If the wind keeps up, you'll grow faint if you stay too long.

zaomeng   ❯  (At the sound of his voice, she does not turn at once.
            Her eyes remain fixed on the glittering water and the fish below.
            After a while she answers softly.)
            You do concern yourself with too much.
            I am only watching fish, and the fish do not seem to mind me there.
            That is more than can be said for lively places full of people,
            where one more person is always in the way.
            (Her fingers unconsciously rub at the fallen flower.
            A few petals break loose and drift onto the water,
            only to be pecked away by the fish.
            Then she turns her face slightly, glancing at Baoyu from the corner of her eye,
            her tone still cool.)
            If anyone is likely to grow faint, it is probably you.
            On such a fine day, why are you not off keeping Baochai company over tea and chess?
            Yet here you are, coming to this quiet place to look for me.
            Aren't you afraid someone will say you still have no proper sense of yourself?

User      ❯  How did such a fine afternoon turn into words so full of jealousy?
            For me, no lively place in the world is worth half the charm
            of Qinfang Bridge when you are standing here.

zaomeng   ❯  (The flower in her hand trembles.
            Her fingers tighten slightly around it.
            A faint flush slowly reaches the tips of her ears,
            yet she turns her face aside so he cannot see it clearly.)
            ...Hmph.
            (There is a brief silence. When she speaks again,
            her voice is a little softer than before,
            as though the spring breeze had worn down one sharp edge.)
            You have said such things more than once.
            However pleasant they sound, too many repetitions make them less rare.
            (A koi flicks its tail, splashing a few drops of water onto the back of her hand.
            She lowers her eyes to look at it, and suddenly murmurs:)
            "Soft the east wind beyond the peach-blossom curtain;
            within it, the morning toilette lies still undone..."
            (The moment the words leave her mouth she seems to realize she has betrayed herself.
            The flush deepens. She lifts the broken flower as though to hide the corner of her mouth,
            her gaze sliding away into the distance.)
            ...I was only watching fish. I was not reciting poetry for your sake.
            If you find it dull here, then go elsewhere.
            You need not stand here and offend my eyes.
```

## Example 2: Group Chat Mode (Observe)

```
User      ❯  Put Jia Baoyu, Lin Daiyu, and Xue Baochai into group chat mode
            (no scene specified).

zaomeng   ❯  All character profiles and relationship data have been loaded.
            Setting the scene...
            🎭 Group chat mode started
            📍 Scene: Hengwu Court, autumn afternoon.
               Baochai is inside sorting colored thread.
               Baoyu comes to borrow a book and finds Daiyu already there.
               The three gather in Baochai's quarters.
            ⏰ Timeline: after Chapter 42
               (The Golden Orchid vow has passed.
               Daiyu and Baochai appear reconciled on the surface,
               but the undercurrent of the triangle remains.)

Baoyu (stepping into Hengwu Court, delighted to see Daiyu there as well):

How fortunate that both my dear sisters are here!
I only came to borrow a book from Baochai,
yet Lin妹妹 is here too, and that saves me another walk.
The weather is so fine today. Why don't we all sit together and talk for a while?

Baochai (setting down her needlework with a faint smile):

You have arrived at just the right time.
I do happen to have a newly acquired copy of Guangyun here.
If you want to borrow it, take it.
Only do not leave it lying in Yihong Courtyard to gather dust again,
as you did last time. That would be a waste of the book.
As for Cousin Lin, she came to see me.
Sit down. I shall have Ying'er bring tea.

Daiyu (leaning sideways against the couch, her eyes passing over Baoyu as she speaks lightly):

Then I came at the wrong time.
Had I known you were here, I would not have come,
lest someone say again that I have come only to disturb your private talk.

(more dialogue omitted...)

zaomeng   > 🌸 Group chat paused

            That was the first round of group chat, generated from the three characters'
            distilled personalities, speech styles, and relationship dynamics.
            You can now:

            continue the conversation
            cut into one character's line
            change the scene
            or end the chat
```

## How To Use It

The correct order is not to jump straight into chat.  
**You always start by providing the novel first, then distilling the characters. Only after distillation should you enter group chat or roleplay.**

The most common user flow is:

1. attach the novel file, or provide the file path
2. describe which characters you want distilled
3. after distillation finishes, enter roleplay or group chat

## One Complete Example

### Step 1: provide the novel, then say who you want distilled

For example, after providing *Dream of the Red Chamber*, you say:

```text
Distill Lin Daiyu and Jia Baoyu for me
```

The system will process the novel and generate character profiles plus relationship data for them.

### Step 2: after distillation, enter chat

Then you say:

```text
Let me play Jia Baoyu and chat with Lin Daiyu
```

Now the system enters the flow where you play Baoyu and Daiyu replies.

Then you continue with:

```text
Sister, are you feeling well today?
```

The system treats that as Baoyu's actual line and lets Daiyu answer.

### Step 3: multi-character chat also comes after distillation

For example, after providing *Romance of the Three Kingdoms* and distilling Liu Bei, Zhang Fei, and Guan Yu, you can say:

```text
Enter Liu Bei, Zhang Fei, Guan Yu group chat mode
```

Then continue with:

```text
Liu Bei: Brothers, now that the fighting has briefly eased, this is a rare moment of calm.
```

Now the system lets Zhang Fei and Guan Yu respond.

## Things You Can Say Directly

### Distill characters

```text
Distill Lin Daiyu and Jia Baoyu for me
```

```text
Extract character personas for Liu Bei, Zhang Fei, and Guan Yu from this novel
```

### Enter roleplay after distillation

```text
Let me play Jia Baoyu and chat with Lin Daiyu
```

### Enter group chat after distillation

```text
Enter Liu Bei, Zhang Fei, Guan Yu group chat mode
```

### Make everyone speak immediately

```text
Let everyone say one line about the alliance with Sun Quan
```

## What It Can Do

### 1. Character Distillation

Extract major characters from `.txt` or `.epub` novels and build markdown character profiles.

The current profile aims to cover a much richer character space, including:

- core identity
- core motivation
- personality base
- decision logic
- arc
- key bonds
- symbolic traits
- world-rule fit
- value tradeoffs
- emotional reaction pattern
- cognitive preference
- language expression style
- strengths and fatal weaknesses
- background and survival condition
- hidden desire
- action tendency
- trauma imprint
- social mode
- inner conflict
- story role
- fears and taboo triggers
- belief anchor
- cognitive limits
- stance stability
- reward / grievance logic
- private self

Representative fields now include:

- `core_traits`
- `values`
- `speech_style`
- `typical_lines`
- `decision_rules`
- `identity_anchor`
- `soul_goal`
- `core_identity`
- `faction_position`
- `background_imprint`
- `world_rule_fit`
- `social_mode`
- `hidden_desire`
- `inner_conflict`
- `story_role`
- `belief_anchor`
- `private_self`
- `stance_stability`
- `reward_logic`
- `strengths`
- `weaknesses`
- `cognitive_limits`
- `fear_triggers`
- `key_bonds`
- `action_style`
- `life_experience`
- `taboo_topics`
- `forbidden_behaviors`

### 2. Relationship Extraction

Build a relationship graph from the novel. Current core fields include:

- `trust`
- `affection`
- `power_gap`
- `conflict_point`
- `typical_interaction`

### 3. Character Chat

Two chat styles are supported:

- `observe`
  You provide a scene, topic, or opening line and let characters interact naturally
- `act`
  You control one character directly while others reply in character

### 4. Correction Memory

If a line is clearly out of character, you can save a correction.  
Later conversations will try to avoid the same kind of mistake.

### 5. Markdown Persona Bundle

Character storage is now markdown-first rather than legacy JSON-first.

Each character directory now follows a navigation + generated layer + override layer pattern. Common files include:

- `data/characters/<novel_id>/<character>/NAVIGATION.generated.md`
- `data/characters/<novel_id>/<character>/NAVIGATION.md`
- `data/characters/<novel_id>/<character>/PROFILE.generated.md`
- `data/characters/<novel_id>/<character>/PROFILE.md`
- `data/characters/<novel_id>/<character>/RELATIONS.generated.md`
- `data/characters/<novel_id>/<character>/RELATIONS.md`
- `data/characters/<novel_id>/<character>/MEMORY.md`

Depending on evidence quality, the distillation step may also generate optional focused persona files:

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

At runtime, loading starts from:

- `NAVIGATION.generated.md`
- `NAVIGATION.md`

and then follows `load_order` to assemble the final persona.

### 6. Constraint Reference Files

The current skill/runtime constraint stack is split into three layers:

- `references/output_schema.md`
  format and field contract
- `references/style_differ.md`
  anti-homogenization and style separation
- `references/logic_constraint.md`
  global persona floor, anti-OOC rules, and mode boundaries

## Quick Start

### 1. Prepare a novel file

Supported formats:

- `.txt`
- `.epub`

### 2. Distill first, then chat

Using *Dream of the Red Chamber* as an example:

```bash
python -m src.core.main distill --novel data/hongloumeng.txt --characters 林黛玉,贾宝玉 --force
python -m src.core.main extract --novel data/hongloumeng.txt --force
```

This creates:

- `data/characters/hongloumeng/<character>/`
- `data/relations/hongloumeng/hongloumeng_relations.md`

### 3. After distillation, start chatting

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode auto --message "让我扮演贾宝玉和林黛玉聊天"
python -m src.core.main chat --novel data/hongloumeng.txt --session <session_id> --message "妹妹今日可大安了？"
```

If you want a multi-character group chat:

```bash
python -m src.core.main chat --novel data/sanguo.txt --mode auto --message "进入刘备、张飞、关羽群聊模式"
python -m src.core.main chat --novel data/sanguo.txt --session <session_id> --message "刘备：二位贤弟，近日战事稍歇。"
```

If you are using the packaged runtime inside `clawhub-zaomeng-skill`, the corresponding entrypoint is:

```bash
py -3 runtime/zaomeng_cli.py distill --novel <path> --characters A,B
py -3 runtime/zaomeng_cli.py extract --novel <path>
py -3 runtime/zaomeng_cli.py chat --novel <path-or-name> --mode auto --message "让我扮演A和B聊天"
```

## Other Commands

### View a character profile

```bash
python -m src.core.main view --character 林黛玉 --novel data/hongloumeng.txt
```

### Save a correction

```bash
python -m src.core.main correct \
  --session <session_id> \
  --message "Baoyu plans to leave home and become a merchant" \
  --corrected "Baoyu has long disliked worldly ambition and would rather remain among poetry, gardens, and intimate company" \
  --character 贾宝玉
```

## Command Overview

```bash
python -m src.core.main distill --novel <path> [--characters A,B] [--output <dir>] [--force]
python -m src.core.main extract --novel <path> [--output <path>] [--force]
python -m src.core.main chat --novel <path-or-name> --mode auto|observe|act [--character <name>] [--session <id>] [--message <text>]
python -m src.core.main view --character <name> [--novel <path-or-name>]
python -m src.core.main correct --session <id> --message <raw> --corrected <fixed> [--character <name>] [--target <name>] [--reason <text>]
```

## Project Structure

```text
Dreamforge/
├─ src/                          # main source code
│  ├─ core/                      # entrypoint, config, dependency wiring, rule loading
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ contracts.py
│  │  ├─ llm_client.py
│  │  ├─ path_provider.py
│  │  └─ rulebook.py
│  ├─ modules/                   # business modules: distillation, relations, chat, correction, speaking
│  │  ├─ distillation.py
│  │  ├─ relationships.py
│  │  ├─ chat_engine.py
│  │  ├─ reflection.py
│  │  └─ speaker.py
│  └─ utils/                     # shared helpers for files, parsing, token counting
│     ├─ file_utils.py
│     ├─ text_parser.py
│     └─ token_counter.py
├─ rules/                        # repository-level editable rule files
│  ├─ distillation_rules.md
│  └─ relationship_rules.md
├─ clawhub-zaomeng-skill/        # standalone ClawHub/OpenClaw skill package
│  ├─ README.md
│  ├─ README_EN.md
│  ├─ SKILL.md
│  ├─ INSTALL.md
│  ├─ MANIFEST.md
│  ├─ PUBLISH.md
│  ├─ prompts/                   # packaged prompt templates
│  ├─ references/                # schema, anti-homogenization, logic constraints
│  ├─ examples/                  # sample persona and relation outputs
│  └─ runtime/                   # packaged minimal runtime
│     ├─ zaomeng_cli.py
│     ├─ requirements.txt
│     ├─ rules/
│     └─ src/
├─ skills/                       # other skill directories
│  └─ zaomeng-skill/
├─ openclaw-skill/               # OpenClaw-side integration
├─ hermes-skill/                 # Hermes-side integration
├─ scripts/                      # install and helper scripts
├─ tests/                        # regression and behavior tests
│  └─ test_relation_behavior.py
├─ data/                         # local runtime data: characters, relations, sessions
├─ README.md                     # Chinese documentation
├─ README.en.md                  # English documentation
├─ LICENSE                       # repository license
└─ requirements.txt              # main project dependencies
```

## License

Main project: `AGPL-3.0-only`

`clawhub-zaomeng-skill`: `MIT-0`
