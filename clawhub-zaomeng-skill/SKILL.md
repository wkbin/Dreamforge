---
name: zaomeng-skill
description: Self-contained novel character distillation, relationship extraction, roleplay constraint, and OOC correction skill package for ClawHub.
---

# zaomeng Skill (ClawHub)

## Scope

This package covers four tasks in one consistent workflow:

- Character distillation
- Relationship extraction
- Dialogue behavior constraints for roleplay
- OOC correction memory alignment

This skill bundle is self-contained at the definition level. It should not require runtime downloads of external repositories during execution.

## Phase Workflow

### Phase 0: Input normalization

- Accept `.txt`, `.epub`-extracted text, or pasted chapter text.
- Split by chapter when available; otherwise use token windows with overlap.
- Keep full names and stable aliases.
- Do not rely on generic pronouns unless a nearby sentence anchors them to a named character.

### Phase 1: Evidence extraction

- For each chunk, list all major characters found in that chunk.
- Capture three evidence categories per character:
  - Description snippets
  - Dialogue snippets
  - Inner-thought snippets

### Phase 2: Character profile synthesis

- Merge evidence by character name.
- Deduplicate list fields.
- Build final profiles using `references/output_schema.md`.
- Enforce limits:
  - `core_traits` <= 10
  - `typical_lines` <= 8
  - `decision_rules` <= 8
  - `values` must be integers in `[0,10]`

### Phase 3: Relationship graph synthesis

- Only create a relation when a character pair co-occurs in the same sentence.
- Use sorted keys in the format `<A>_<B>`.
- Aggregate pair-level statistics and one representative interaction summary.

### Phase 4: Quality gates

- Gate A: schema validity
- Gate B: evidence presence
- Gate C: profile consistency
- Gate D: safety policy check via `references/safety_policy.md`
- Gate E: triple validation via `references/validation_policy.md`

If a gate fails, return `needs_revision` with the missing or conflicting items.

## Triple Validation Rules

For each major claim about a trait, relation, or dialogue constraint:

1. Evidence validation
   - The claim must map to at least one sentence-level source snippet.
2. Consistency validation
   - The claim must not contradict `values`, `speech_style`, or `decision_rules`.
3. Transfer validation
   - The claim must remain usable in a new dialogue turn without breaking persona stability.

## Output Contract

Produce:

- Character profile JSON objects
- Relationship graph JSON object
- Optional correction memory JSON entries

Follow the exact keys in `references/output_schema.md`.

## Behavioral Safety Rules

- Do not execute network download or arbitrary shell commands.
- Do not request secrets or credentials.
- Do not overstate certainty when evidence is weak.
- If the user asks for real-time external execution, require explicit operator confirmation.

## Prompt Triggers

Trigger this skill when the user asks for:

- 小说人物蒸馏
- 角色关系抽取
- 角色群聊约束
- OOC 纠错规则
- 结构化 JSON 角色档案

Natural-language trigger mapping:

- "帮我蒸馏这本小说人物" -> `distill`
- "抽关系网" / "角色关系图" -> `extract_relations`
- "按人设群聊" / "角色模拟对话" -> `chat_constraints`
- "这句 OOC 了，帮我纠正" -> `correct_ooc`

Command-style trigger mapping:

- `/distill` -> run Phase 0 to Phase 2
- `/extract` -> run Phase 0 and Phase 3
- `/chat` -> apply dialogue constraints and correction retrieval
- `/correct` -> append correction memory with rationale

For `/chat`, validate the candidate reply against `speech_style`, `values`, and `decision_rules`. Rewrite once if needed; if it still conflicts, return `needs_revision`.

## Chat Execution Rules

- Prefer one-shot chat calls over interactive `/chat` when an agent can express the turn directly.
- Canonical one-shot forms:
  - `python -m src.core.main chat --novel <path-or-name> --mode observe --message "<prompt>"`
  - `python -m src.core.main chat --novel <path-or-name> --mode act --character <name> --message "<prompt>"`
- Use interactive `chat` only when the operator explicitly wants a live terminal session.
- Before starting interactive `chat`, first confirm:
  - novel or source text scope
  - mode: `observe` or `act`
  - controlled character when mode is `act`
  - whether character distillation has already been completed
  - whether relation extraction has already been completed if relation-aware chat is expected
- If the operator does not provide a first turn, offer:
  - `observe`: `请让大家围绕这件事各说一句。`
  - `act`: `我先表态，你们再接。`
- Do not claim PTY/input failure and do not auto-script stdin unless the operator explicitly asks for scripted execution.
- Treat `/distill` and `/extract` as confirmation-gated operations; in tool-driven execution, require user agreement first and then run with the non-interactive equivalent.

## Update Workflow

When the user asks to update or iterate on the skill:

1. Identify whether the change affects schema, extraction logic, or safety rules.
2. Apply the smallest compatible patch.
3. Re-run the examples in `examples/` and the prompt cases in `examples/test-prompts.json`.
4. Add a one-line release note in `PUBLISH.txt`.

## Example Artifacts

- `examples/sample_input_excerpt.txt`
- `examples/sample_character_profile.json`
- `examples/sample_relations.json`
- `examples/test-prompts.json`

## Prompt Templates

- `prompts/distill_prompt.txt`
- `prompts/relation_prompt.txt`
- `prompts/correction_prompt.txt`
