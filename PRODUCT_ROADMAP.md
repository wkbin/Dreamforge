# zaomeng Product Roadmap v1

## 1. Product Positioning

`zaomeng` is not a general-purpose AI chat shell.

It is better positioned as:

**a Chinese-fiction character asset workshop + interactive story playground**

This positioning has two visible layers:

- Fun layer:
  - chat with book characters
  - self-insert into the story world
  - observe mode to push the plot forward
- Asset layer:
  - character distillation
  - persona review and correction
  - field completion
  - relation extraction
  - relation graph export
  - self card / role card management

The long-term moat is the asset layer, not the input box.

Suggested external one-liner:

> Turn Chinese-fiction characters from vague impressions into reusable character assets that can be reviewed, completed, exported, and brought into live dialogue.

## 2. Product Vision

The project should help users move through four steps smoothly:

1. Read a novel or import a text.
2. Distill people, relationships, and speaking styles into structured assets.
3. Review and refine those assets until they feel trustworthy.
4. Reuse them in dialogue, story simulation, and downstream creation.

In short:

**`zaomeng` should become an operating system for fictional characters, not just a chat page.**

## 3. Core Product Thesis

Three beliefs should guide feature decisions:

1. A stable character is more valuable than a flashy one-off reply.
2. Structured assets beat disposable prompts.
3. Dialogue is the hook, but asset quality is the foundation.

This means new features should be prioritized when they improve one or more of:

- character stability
- reusability
- reviewability
- shareability

## 4. Product Lanes

### 4.1 Character Asset Workshop

This is the primary lane and the strongest differentiator.

Core outcomes:

- extract character profiles from long-form Chinese fiction
- review and correct core fields
- complete weak or missing fields
- version and export role cards
- maintain a reusable character library per work

Why this lane matters:

- strongest moat versus generic AI chat products
- most aligned with current architecture
- easiest to explain as a serious tool

### 4.2 Interactive Story Playground

This is the growth and sharing lane.

Core outcomes:

- act as a chosen character
- self-insert into the story
- observe mode to steer the next beat
- generate suggestions that follow persona and context
- create memorable, shareable scenes

Why this lane matters:

- more emotionally engaging
- easier to spread socially
- helps users feel the value of the asset layer

### 4.3 Creator Companion

This is a later productivity lane for heavier users.

Core outcomes:

- export character analysis
- summarize conflict lines and relation changes
- help fanfic or derivative writing stay in character
- offer role consistency checks

Why this lane matters:

- opens a clearer pro-user workflow
- supports creators, analysts, and roleplay communities

## 5. Strategic Choice

Recommended strategy for the next phase:

**Lead with the Character Asset Workshop, and use the Interactive Story Playground as the distribution hook.**

This means:

- product messaging should emphasize reusable character assets
- demos and social posts should emphasize self-insert, roleplay, and scene interaction

## 6. Product Structure

The product should gradually evolve toward three top-level objects:

### 6.1 Work

A work should become the main container.

Each work page should show:

- title
- import status
- distillation progress
- character count
- relation graph status
- latest sessions
- quick actions

### 6.2 Character

A character should have a dedicated home, not only a review modal.

Each character page should show:

- key fields
- advanced fields
- evidence strength or completion hints
- relation summary
- speaking style summary
- export actions
- chat entry actions

### 6.3 Session

A session should become a first-class interactive object.

Each session should track:

- mode: `act` / `insert` / `observe`
- participants
- current scene state
- recent relationship shifts
- session memory
- shareable highlights

## 7. Next 4 Weeks

### Week 1: Product Skeleton

Goal:

- make the product legible at a glance

Priority deliverables:

1. Work overview page
2. Character overview page
3. Clearer pipeline status labels
4. Unified chat-mode entry wording

Expected result:

- a new user can understand what `zaomeng` does in less than 30 seconds

### Week 2: Asset Depth

Goal:

- make character assets feel reliable and reusable

Priority deliverables:

1. character version history
2. field change history
3. editable relationship metadata
4. exportable character package

Expected result:

- a character is no longer just generated output; it becomes an editable asset

### Week 3: Session Memory

Goal:

- make dialogue sessions feel alive instead of stateless

Priority deliverables:

1. session memory summary
2. world-state deltas after key turns
3. relationship drift tracking
4. scene recap block

Expected result:

- ongoing sessions hold tension, memory, and change more naturally

### Week 4: Sharing and Growth

Goal:

- make outputs easy to show and easy to explain

Priority deliverables:

1. shareable character card view
2. shareable relation graph snapshot
3. shareable session highlight card
4. polished onboarding copy and screenshots

Expected result:

- users can show the product through outputs, not just through explanation

## 8. Top 10 Product Priorities

1. Work overview page
2. Character page
3. Session memory summary
4. Character version history
5. Editable relation metadata
6. Shareable character card
7. Shareable relation graph
8. World-state hints during chat
9. Branch replay for key dialogue decisions
10. Exportable reusable character package

## 9. Product Metrics

Suggested early metrics:

- first successful work completion rate
- percentage of characters that receive manual review
- percentage of sessions started after distillation
- average number of sessions per work
- average number of saved self cards
- number of exported or shared assets
- suggestion success rate in `insert` and `observe` modes

North-star candidate:

**reusable character assets per completed work**

This metric fits the product better than raw message count.

## 10. What Not To Do Yet

Avoid these traps in the near term:

1. Do not turn `zaomeng` into a generic AI assistant.
2. Do not build a heavy public community layer too early.
3. Do not keep adding isolated small buttons without page-level structure.
4. Do not let chat novelty outrun asset quality.

## 11. Feature Filter

Before shipping a new feature, ask:

**Does this improve character stability, reusability, or shareability, or is it just another button?**

If it only adds surface complexity, it should probably wait.

## 12. Messaging Drafts

### External Positioning

`zaomeng` is a character-asset tool for Chinese fiction. It distills people, relationships, and speaking styles into reusable assets, then lets you review them, complete them, and bring them into live dialogue.

### Short Tagline

Not just chat with characters. Build them first.

### Chinese Tagline Candidate

不只是和角色聊天，而是先把角色真正整理出来。

## 13. Immediate Build Recommendation

If only three things should be built next, build these:

1. work overview page
2. character page
3. session memory summary

Together, these three items would most clearly shift `zaomeng` from a feature collection into a product.
