# Character Overview Frontend PRD v1

## 1. Goal

Define the first real `角色页` for `zaomeng`.

This page should promote character data from a modal-review artifact into a first-class product page.

It should answer:

- 这个角色是谁
- 目前稳不稳
- 哪些字段还需要补
- 我现在能拿这个角色做什么

## 2. Product Role

The Character Overview page is the core of the character-asset vision.

Current equivalent:

- persona review modal

Target role:

- a dedicated page object
- dossier-like
- review-first but action-ready

## 3. User Story

As a user, when I open a character, I want to:

1. understand the role quickly
2. see key fields first
3. detect weak or missing areas
4. complete or refine fields
5. start a relevant session from that character

## 4. Placement

Recommended initial integration:

- launch from the character list inside the Work Overview
- in early implementation, the page can still live inside the current detail side as a routed or swapped panel

This keeps migration incremental.

## 5. Above-the-Fold Structure

Recommended section order:

1. Character Hero
2. Key Fields Grid
3. Action Row
4. Voice + Relation Summary
5. Character Health

## 6. Character Hero

### Required content

- character name
- work title
- story role
- stability badge
- last updated

### Primary actions

- `校对字段`
- `代入开聊`
- `导出角色`

### Secondary actions

- `查看版本`
- `查看关系`
- `继续增量蒸馏`

## 7. Key Fields Grid

### Purpose

This should be the page's heart.

### Required fields

- core identity
- story role
- identity anchor
- temperament type
- soul goal
- core traits
- key bonds
- speech style
- worldview
- belief anchor
- moral bottom line
- restraint threshold
- stress response

### Presentation rules

- compact card layout
- label and value clearly separated
- missing values visually obvious
- weak values visually obvious
- AI completion entry visible on:
  - empty fields
  - weak fields
  - evidence-thin fields

This is important because current behavior already showed the user that "empty only" is not enough.

## 8. Secondary Field Area

This area should be below the key grid and collapsed by default.

Suggested groups:

1. `内核细调`
2. `对白细调`
3. `情绪细调`

This mirrors the current review grouping and keeps continuity.

## 9. Voice Summary

### Purpose

Bridge structured fields and conversation trust.

### Required content

- one-line speaking summary
- signature phrases
- sentence habits
- typical lines

This section should make the character feel speakable, not just documented.

## 10. Relation Summary

### Purpose

Explain who matters to this character.

### Required content

- top related characters
- short relation label
- tension or closeness hint
- open relation graph action

This should remain summary-first.

## 11. Character Health Block

### Purpose

Show whether the asset is trustworthy.

### Required items

- completeness score
- number of weak key fields
- AI-completed field count
- manually edited field count
- last incremental distill time

### Suggested labels

- `关键字段已齐`
- `还有 3 处待补`
- `最近做过增量蒸馏`
- `含 AI 补全字段`

## 12. Action Logic

### `校对字段`

Short term:

- opens current persona review modal on this character

Long term:

- opens full editable character page mode

### `AI 补全`

Should support:

- empty fields
- weak fields
- evidence-thin fields

Status messages should clearly distinguish:

- using model knowledge
- web fallback
- no reliable completion possible

### `继续增量蒸馏`

Should be clearly described as incremental, not re-distill.

### `代入开聊`

Starts an `act` session with this character preselected.

### `以自己入场`

Should be available from this page as a secondary CTA or inside the shared session-entry module.

## 13. Data Requirements

### Must-have data

- normalized character fields
- field grouping
- preview values
- relation summary
- source paths if needed for review actions

### Nice-to-have data

- field confidence or weakness hints
- edit provenance
- last modification timestamps by field
- incremental distill markers

## 14. State Rules

### Loading state

Show character-specific skeleton sections, not a generic spinner only.

### Missing character state

If a character asset is incomplete or missing:

- show a recovery message
- offer `继续增量蒸馏`

### Weak-field state

Weak fields should show:

- a soft warning tone
- `AI 补全`
- `手动校对`

### Fully healthy state

Use a calm stable tone, not celebratory overload.

## 15. Suggested Visual Tone

The page should feel like:

- a dossier
- a role sheet
- a literary character profile

It should not feel like:

- a raw form dump
- a generic admin settings page

## 16. Suggested Implementation Phases

### Phase 1

- create a read-first Character Overview panel
- show key fields
- add health summary
- deep-link from work page

### Phase 2

- connect existing persona review modal as an action from this page
- expose AI completion more clearly
- expose relation summary

### Phase 3

- add versions and field history
- add export package view

## 17. Out of Scope

Do not include in v1:

- complete in-page editing for every field
- relation graph editing
- multiplayer review
- public publishing

## 18. Success Criteria

The page is successful if a user can:

1. understand the character in under 15 seconds
2. identify weak fields without opening every editor
3. complete or correct a weak field with low confusion
4. start a session from the character naturally

## 19. Engineering Notes

Recommended code starting points:

- [settings-modal.html](d:/work2/Dreamforge/src/web/static/fragments/settings-modal.html)
- [run-detail.js](d:/work2/Dreamforge/src/web/static/js/run-detail.js)
- [main.js](d:/work2/Dreamforge/src/web/static/js/main.js)
- [modal.css](d:/work2/Dreamforge/src/web/static/styles/modal.css)

This page should be built by extracting and elevating the current persona-review logic, not by rewriting character review from zero.
