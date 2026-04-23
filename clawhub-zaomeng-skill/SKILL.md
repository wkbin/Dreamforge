---
name: zaomeng-skill
description: 自包含的小说角色蒸馏与关系构建技能。用于从小说片段提取角色心智档案、关系网和群聊行为约束，输出标准 JSON，并通过一致性和安全门槛校验。
---

# Zaomeng Skill (ClawHub)

## Scope

Execute four tasks in one consistent format:
- Character distillation
- Relationship extraction
- Dialogue behavior constraints for roleplay
- OOC correction memory alignment

This skill is local-first and self-contained at the skill-definition level.
Do not require runtime download of external repositories during execution.

## Phase Workflow

Phase 0: Input normalization
- Accept `.txt` / `.epub` extracted text or pasted chapters.
- Split by chapter; if unavailable, split by token window (`8000` with `200` overlap).
- Keep character full names and unique aliases; avoid generic pronouns unless adjacent-name anchored.

Phase 1: Evidence extraction
- For each chunk, output all major characters in that chunk.
- Capture three evidence types per character:
- Description snippets
- Dialogue snippets
- Inner-thought snippets

Phase 2: Character profile synthesis
- Merge chunk evidence by character name.
- Deduplicate list fields.
- Build final profile using the schema in `references/output_schema.md`.
- Enforce limits:
- `core_traits` <= 10
- `typical_lines` <= 8
- `decision_rules` <= 8
- `values` integers in `[0,10]`

Phase 3: Relationship graph synthesis
- Only process chunks where two or more characters co-occur.
- Use sorted key format `<A>_<B>`.
- Aggregate pair-level stats and one-line interaction summary.

Phase 4: Quality gates
- Gate A: Schema validity (all required keys present)
- Gate B: Evidence coverage (each profile has at least 1 evidence item)
- Gate C: Consistency check (speech style and decision rules do not contradict values)
- Gate D: Safety policy check via `references/safety_policy.md`

If any gate fails, return a `needs_revision` result with missing items.

## Output Contract

Produce:
- Character profiles JSON object list
- Relationship graph JSON object
- Optional correction memory JSON entries

Follow exact keys and ranges in `references/output_schema.md`.

## Behavioral Safety Rules

- Do not execute network download or arbitrary shell commands.
- Do not request secrets (API keys, tokens, credentials).
- Do not claim certainty when evidence is weak; label as low-confidence.
- If user asks for real-time external execution, require explicit operator confirmation.

## Prompt Triggers

Trigger this skill when user asks for:
- 小说人物蒸馏 / 角色人设提取
- 角色关系网生成
- 角色群聊设定或 OOC 纠错规则
- 输出结构化 JSON 角色档案

## Example Artifacts

- `examples/sample_input_excerpt.txt`
- `examples/sample_character_profile.json`
- `examples/sample_relations.json`

