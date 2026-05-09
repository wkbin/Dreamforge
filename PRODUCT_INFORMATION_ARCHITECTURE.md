# zaomeng Product Information Architecture v1

## 1. Purpose

This document turns the product roadmap into a navigable structure.

Goal:

- clarify the main objects in the product
- define the page hierarchy
- reduce UI drift from feature-by-feature growth

## 2. Core Product Objects

The product should revolve around three first-class objects:

1. Work
2. Character
3. Session

Supporting objects:

4. Self Card
5. Relation Graph
6. Export Package

## 3. Top-Level Navigation

Recommended top-level navigation for the Web UI:

1. Library
2. Work
3. Character
4. Session
5. Settings

Interpretation:

- `Library` is the landing and browsing layer
- `Work` is the container layer
- `Character` is the asset layer
- `Session` is the interaction layer
- `Settings` stays secondary

## 4. Page Tree

### 4.1 Library Layer

Pages:

- Library Home
- Recent Works
- Recent Sessions
- Self Cards

Primary jobs:

- create a new work
- resume an existing work
- resume a recent session
- manage self cards

### 4.2 Work Layer

Pages:

- Work Overview
- Work Characters
- Work Relations
- Work Sessions
- Work Timeline

Primary jobs:

- track import and distill progress
- browse all characters in one work
- open the relation graph
- start or resume sessions tied to that work

### 4.3 Character Layer

Pages:

- Character Overview
- Character Fields
- Character Relations
- Character Sessions
- Character Versions

Primary jobs:

- inspect and refine a character asset
- understand the character's place in the work
- export the character package
- start a chat from that character

### 4.4 Session Layer

Pages:

- Session Overview
- Session Transcript
- Session Memory
- Session State
- Session Share Card

Primary jobs:

- continue a conversation
- inspect what changed in the scene
- see relationship drift
- share the session highlight

## 5. Object Relationships

Recommended relationship model:

- One Library contains many Works
- One Work contains many Characters
- One Work contains many Sessions
- One Character belongs to one Work
- One Session belongs to one Work
- One Session references multiple Characters
- One Self Card can be used by many Sessions
- One Session stores a snapshot of the Self Card at creation time

This matches the current design principle:

- deleting a Self Card should not break older sessions

## 6. Key User Flows

### 6.1 New User Flow

1. Enter Library Home
2. Create a new Work
3. Import novel text
4. Run distillation
5. Open a Character
6. Review key fields
7. Start a Session

### 6.2 Returning User Flow

1. Enter Library Home
2. Resume a Work or Session
3. Continue character refinement or dialogue

### 6.3 Power User Flow

1. Open a Character
2. Review versions and field changes
3. Edit relation metadata
4. Export package
5. Start a targeted Session

## 7. IA Priorities

These layers should be introduced in order:

### Phase A

- Library Home
- Work Overview
- Character Overview

### Phase B

- Work Relations
- Character Versions
- Session Memory

### Phase C

- Work Timeline
- Session State
- Share Card views

## 8. Cross-Page Actions

These actions should stay visible and consistent:

### Work-level actions

- continue distill
- open relation graph
- create session
- export work summary

### Character-level actions

- review fields
- AI complete field
- export character
- start act chat
- start insert chat with this cast

### Session-level actions

- send message
- generate suggestion
- switch mode only when safe
- view memory summary
- share highlight

## 9. UI Rules

To keep the IA coherent:

1. Avoid hiding important objects only inside modals.
2. Every Work should expose its Characters and Sessions directly.
3. Every Character should be reachable from both Work and Session contexts.
4. Every Session should show which Work and which Characters it belongs to.
5. Settings should not be the place where product objects live.

## 10. Empty-State Guidance

Recommended empty states:

### No works

- explain what a Work is
- provide a single strong CTA: create/import a novel

### No characters yet

- show distill progress
- explain that characters appear after distillation

### No sessions yet

- offer three clear entry points:
  - act as a character
  - enter as yourself
  - observe the cast

### No self cards yet

- explain what a Self Card is
- offer:
  - create manually
  - generate with AI

## 11. Naming Recommendation

Suggested stable user-facing names:

- Work: `作品`
- Character: `角色`
- Session: `会话`
- Self Card: `自设角色卡`
- Relation Graph: `关系图谱`
- Session Memory: `会话记忆`
- Work Timeline: `作品时间线`

## 12. Immediate Recommendation

If only one IA shift is made next:

**promote Character from a modal artifact into a dedicated page object**

That single move would make the whole product feel more intentional.
