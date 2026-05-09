# zaomeng Product Execution Plan v1

## 1. Purpose

This document turns the roadmap into a practical 4-week execution plan.

It is optimized for:

- one primary builder
- fast iteration
- visible product progress each week
- low risk of getting trapped in over-design

## 2. Guiding Rules

Execution should follow these rules:

1. Build page-level product structure before polishing micro-interactions.
2. Prefer visible progress over hidden infrastructure.
3. Keep every week shippable.
4. Avoid parallel redesigns across too many surfaces.
5. Each week should end with one clear demo story.

## 3. 4-Week Goal

At the end of 4 weeks, `zaomeng` should feel like:

- a work-centered product
- with character pages
- with more trustworthy session memory
- and with outputs users can share

## 4. Week-by-Week Plan

### Week 1: Work and Character Product Shell

#### Week Goal

Make the product feel structured around `作品` and `角色`, not just scattered panels.

#### Primary Deliverables

1. Work Overview page
2. Character Overview page
3. shared status vocabulary
4. unified session-entry module

#### UI Scope

Build:

- Work header
- progress strip
- character list
- recent sessions card
- relation graph quick card
- Character header
- key fields section
- character health summary
- shared mode-entry card for `act` / `insert` / `observe`

Do not build yet:

- full version history
- complex exports
- public sharing
- branching playback

#### Backend Scope

Add or reuse API payloads for:

- work summary view
- character summary view
- session list summary
- relation graph status summary

If possible, prefer composing existing data instead of inventing new storage.

#### Success Criteria

- a user can open one work and instantly understand readiness
- a user can open one character and instantly understand stability
- a user can start a session from either page without confusion

#### Demo Story

"Import a work -> inspect one character -> start a session from that character."

### Week 2: Character Trust and Editability

#### Week Goal

Make character assets feel editable, inspectable, and worth keeping.

#### Primary Deliverables

1. Character version history
2. field change history
3. weak-field highlighting
4. relation metadata edit surface

#### UI Scope

Build:

- version timeline card
- field source tags:
  - distill
  - AI complete
  - manual edit
  - incremental distill
- relation edit panel
- better weak-field state presentation

Do not build yet:

- multi-user collaboration
- role-card marketplace
- advanced diff visualizations

#### Backend Scope

Add or reuse:

- field update audit data
- version snapshot persistence
- relation metadata write path

Keep the first version simple:

- append-only snapshots are fine
- no need for a heavy revision system yet

#### Success Criteria

- a user can tell what changed, when, and why
- AI completion no longer feels like hidden mutation
- incremental distill becomes visible and trustworthy

#### Demo Story

"Open a character -> see weak fields -> AI complete one field -> inspect the change history."

### Week 3: Session Memory and World State

#### Week Goal

Make ongoing sessions feel like they remember change.

#### Primary Deliverables

1. Session memory summary
2. relationship drift summary
3. scene recap block
4. visible world-state hints

#### UI Scope

Build:

- session memory card
- recent relation changes card
- current scene state summary
- recap block above transcript or beside transcript

Do not build yet:

- full timeline replay
- complex state machines
- auto-generated lore encyclopedia

#### Backend Scope

Introduce lightweight post-turn summaries such as:

- what changed in the scene
- who moved closer or further apart
- what new tension appeared
- whether the user's standing changed

First pass can be summary-first, not simulation-first.

#### Success Criteria

- after several turns, the session feels more coherent
- users can understand "what just changed" without rereading the whole transcript
- `observe` mode becomes more meaningful

#### Demo Story

"Run a 10-turn session -> inspect memory summary -> see relation and world-state drift."

### Week 4: Sharing and Product Presentation

#### Week Goal

Make the product easy to show, explain, and spread.

#### Primary Deliverables

1. shareable character card view
2. shareable relation graph snapshot
3. shareable session highlight
4. onboarding and empty-state polish

#### UI Scope

Build:

- clean read-only share view for character
- clean read-only share view for session highlight
- relation graph snapshot page or image-friendly layout
- polished empty states for:
  - no works
  - no characters
  - no sessions
  - no self cards

Do not build yet:

- public feed
- user profiles
- social network features

#### Backend Scope

Keep sharing simple:

- local read-only routes
- exportable static snapshots
- minimal metadata

#### Success Criteria

- users can show results with one link or one screenshot
- the product can be understood through outputs
- onboarding feels less like a tool demo and more like a real app

#### Demo Story

"Open a work -> inspect a character -> continue a session -> share a clean result card."

## 5. Recommended Build Order Inside Each Week

Within each week, use this order:

1. data shape
2. page skeleton
3. primary actions
4. status states
5. visual polish

This prevents spending energy on visuals before the product object is clear.

## 6. Daily Rhythm Suggestion

Recommended rhythm for a solo builder:

### Monday

- define the week's scope
- freeze what is explicitly out of scope

### Tuesday

- backend shape and data composition

### Wednesday

- page skeleton and primary actions

### Thursday

- state handling, empty states, recovery paths

### Friday

- polish, screenshots, note what shipped

### Weekend or buffer

- bug cleanup or small delight features only

## 7. Scope Control

If time gets tight, cut in this order:

1. animations
2. decorative polish
3. secondary tabs
4. advanced filters
5. export variations

Do not cut:

1. object clarity
2. primary CTA flow
3. empty-state guidance
4. failure-state clarity

## 8. Engineering Notes

To keep delivery smooth:

1. Reuse existing run and persona data whenever possible.
2. Introduce page-level APIs only when composition becomes too painful on the client.
3. Keep session memory additive; do not rewrite old transcript logic too early.
4. Preserve current dialogue modes and improve the entry framing instead of reinventing them.

## 9. Acceptance Checklist

At the end of the 4-week cycle, ask:

1. Can a new user understand the product quickly?
2. Do characters feel like assets, not temporary blobs?
3. Do sessions feel like they remember what changed?
4. Can the product be shown through outputs?

If the answer is "yes" to all four, the cycle worked.

## 10. Immediate Recommendation

If work starts right away, begin with this exact slice:

1. Work Overview page skeleton
2. Character Overview page skeleton
3. shared session-entry module

That is the smallest build that changes the product's perceived shape.
