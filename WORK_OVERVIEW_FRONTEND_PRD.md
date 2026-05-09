# Work Overview Frontend PRD v1

## 1. Goal

Define the first real `作品页` for `zaomeng`.

This page should turn the current run-detail area into a clearer product surface.

It should answer, at a glance:

- 这本作品现在整理到哪一步了
- 角色准备得怎么样
- 关系图谱能不能看
- 现在最值得做的下一步是什么

## 2. Product Role

This page becomes the default home of a selected work.

Current equivalent:

- `workflow-strip.html`
- `run-detail.js`

Target role:

- less like a stack of utility panels
- more like a work dashboard

## 3. User Story

As a user, after I open one work, I want to:

1. understand overall progress
2. see which characters are ready or weak
3. jump into relation review or character review
4. start a session from the work

## 4. Page Placement

Recommended placement in current UI:

- keep it in the `workflow-strip-root` area
- evolve the current detail column into a real Work Overview

This avoids a full navigation rewrite in the first step.

## 5. Above-the-Fold Structure

Recommended section order:

1. Work Hero
2. Progress Strip
3. Primary Action Row
4. Three-panel body

## 6. Work Hero

### Required content

- work title
- source name
- total character count
- overall status
- elapsed time when available

### Suggested copy examples

- `这卷已经整理完成，可以继续校对人物或直接开聊。`
- `这卷还在整理中，人物与关系会依次浮现。`
- `这卷停在半途，可以继续蒸馏把它接上。`

### Primary CTA placement

Right side or under the hero:

- `继续蒸馏`
- `开始聊天`
- `查看关系图`

## 7. Progress Strip

### Purpose

Summarize readiness in a compact, scan-friendly row.

### Required items

- text import status
- character distill status
- key review status
- relation graph status
- latest update

### Visual rule

Each item should feel like a status chip/card, not a paragraph.

### Suggested states

- `未开始`
- `进行中`
- `已完成`
- `待校对`
- `已中断`
- `图谱失败但不影响聊天`

## 8. Primary Action Row

### Primary actions

1. `继续蒸馏`
2. `校对人物`
3. `开始聊天`

### Secondary actions

1. `关系明细`
2. `导出摘要`
3. `查看时间线`

### Current mapping

- `detail-redistill-button`
- `open-persona-review-button`
- `detail-start-chat-button`
- `open-relation-details-button`

The PRD recommends keeping these actions, but regrouping them visually.

## 9. Main Body Layout

Recommended three-block structure:

### 9.1 Left Block: Character Readiness

Purpose:

- quickly show who is ready, weak, or missing detail

Required content per character:

- name
- readiness badge
- weak key-field count
- last updated hint
- open action

Suggested quick badges:

- `稳定`
- `待补全`
- `待校对`
- `增量更新`

### 9.2 Center Block: Work Summary

Purpose:

- provide narrative context for the current state

Required content:

- one short work summary line
- current progress message
- recent events
- current bottleneck

This block can reuse current data from:

- `run.summary`
- `run.progress`
- `run.events`

### 9.3 Right Block: Sessions and Graph

Purpose:

- connect work state to action

Required content:

- latest sessions list
- relation graph preview/status
- quick session entry card

The quick session entry card should expose:

1. `act`
2. `insert`
3. `observe`

## 10. Lower Sections

After the main three-block area, show:

1. `需要优先校对的人物`
2. `最近会话`
3. `关系图谱状态`
4. `本轮时间线`

This reuses existing information but makes the order product-first.

## 11. Data Requirements

### Must-have data

- run title
- source title
- locked characters
- artifact_index characters
- summary status
- progress message
- timeline events
- relation graph existence/status
- recent sessions

### Nice-to-have derived data

- per-character weak-field count
- last reviewed timestamp
- relation graph warning message

## 12. Frontend State Rules

### Loading state

Show a full-page skeleton or soft loading state in the work body.

### Empty state

When no characters exist yet:

- explain that characters appear after distillation
- emphasize `继续蒸馏`

### Partial-failure state

If relation graph fails:

- show a soft warning card
- explicitly state that chatting still works

### Running state

If workflow is in progress:

- highlight current progress
- keep `停止蒸馏` visible
- soften non-primary actions instead of hiding all of them

## 13. Interaction Rules

### Clicking a character

Should open the future Character Overview page.

### Clicking `校对人物`

Short term:

- still opens current modal

Long term:

- goes to Character Overview

### Clicking `开始聊天`

Should open the shared session-entry module prefilled from the work.

## 14. Suggested Implementation Phases

### Phase 1

- restructure the existing `workflow-strip`
- introduce clear sections
- reuse current APIs

### Phase 2

- add character readiness summary
- add recent sessions summary into the work page
- refine status vocabulary

### Phase 3

- deep-link from work page into character page

## 15. Out of Scope

Do not include in v1:

- full editable character cards in-page
- branch replay
- public sharing
- graph editing

## 16. Success Criteria

The page is successful if a user can:

1. understand work readiness in under 10 seconds
2. identify which character needs attention next
3. start a session without confusion
4. understand graph failure as non-blocking

## 17. Engineering Notes

Recommended code starting points:

- [workflow-strip.html](d:/work2/Dreamforge/src/web/static/fragments/workflow-strip.html)
- [run-detail.js](d:/work2/Dreamforge/src/web/static/js/run-detail.js)
- [bookshelf.js](d:/work2/Dreamforge/src/web/static/js/bookshelf.js)
- [workspace.css](d:/work2/Dreamforge/src/web/static/styles/workspace.css)

This page should be implemented as an evolution of the existing work detail surface, not a full replacement in one jump.
