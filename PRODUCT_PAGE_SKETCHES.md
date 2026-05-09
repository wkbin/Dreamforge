# zaomeng Product Page Sketches v1

## 1. Purpose

This document describes the first two product-defining pages:

1. Work Overview
2. Character Overview

The goal is not pixel-perfect UI.

The goal is to define:

- section order
- content hierarchy
- action priority
- what should feel primary versus secondary

## 2. Work Overview Page

### 2.1 Page Goal

Answer these questions instantly:

- what is this work
- how complete is the pipeline
- which characters are ready
- can I start interacting yet

### 2.2 Above-the-Fold Layout

Recommended structure:

1. Work header
2. Progress strip
3. Main action row
4. Three-column content area

### 2.3 Work Header

Must show:

- work title
- source file name
- import time
- total character count
- overall status badge

Suggested actions:

- continue distill
- open relation graph
- start new session

Tone:

- serious, project-like
- less “chat app”, more “story workspace”

### 2.4 Progress Strip

Use a horizontal block showing:

- text imported
- characters distilled
- fields needing review
- relation graph status
- latest update

This should be glanceable, not verbose.

### 2.5 Main Action Row

Recommended three primary CTAs:

1. Continue Distill
2. Review Characters
3. Start Session

Recommended two secondary CTAs:

1. Open Relation Graph
2. Export Summary

### 2.6 Main Content Area

Recommended three columns:

#### Left Column: Character List

Show:

- character avatar placeholder or initial
- name
- readiness status
- missing key-field count
- quick open action

Sort priority:

1. needs review
2. recently updated
3. alphabetic or narrative order

#### Center Column: Work Summary

Show:

- one-paragraph work summary
- pipeline summary
- current bottlenecks
- recent activity log

This is the page's “narrator block”.

#### Right Column: Session and Relation Quick Access

Show:

- latest sessions
- relation graph preview card
- quick mode entry:
  - act
  - insert
  - observe

### 2.7 Lower Sections

Recommended order:

1. Characters needing review
2. Recent sessions
3. Relation graph preview
4. Export area

### 2.8 Empty States

If distillation not started:

- center the import and distill CTA
- avoid showing empty dense panels

If relation graph failed:

- show a soft warning card
- explicitly say chatting is still available

This is important because graph failure is non-blocking.

## 3. Character Overview Page

### 3.1 Page Goal

Answer these questions instantly:

- who is this character
- how stable is the asset
- what still needs correction
- what can I do with this character now

### 3.2 Above-the-Fold Layout

Recommended structure:

1. Character header
2. Key fields block
3. Action row
4. Relation and voice summary

### 3.3 Character Header

Must show:

- character name
- work name
- role or story position
- stability / completeness badge
- last updated time

Primary actions:

- review fields
- start act session
- export character

Secondary actions:

- view versions
- open relation view

### 3.4 Key Fields Block

This block should be the heart of the page.

Show only the key fields first:

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

Display rules:

- compact card layout
- clear labels
- empty or weak fields visually marked
- AI completion entry visible on weak fields too, not only empty ones

### 3.5 Secondary Fields

Do not crowd the main page with all fields.

Use a secondary expandable area:

- inner layers
- dialogue details
- emotion details

This matches the product principle:

- key identity first
- fine tuning second

### 3.6 Voice Summary Section

Show:

- one-line speaking summary
- typical lines
- signature phrases
- sentence opener and ending habits

This section helps bridge asset review and dialogue trust.

### 3.7 Relation Summary Section

Show:

- top related characters
- bond type or tension
- quick relation graph entry

This section should stay summary-first, not graph-first.

### 3.8 Character Health Section

This section should make trust visible.

Show:

- completeness score
- fields missing
- fields AI-completed
- fields manually edited
- latest incremental distill time

If the character was incrementally updated, say so clearly.

### 3.9 Bottom Action Area

Recommended actions:

1. continue incremental distill
2. review all fields
3. export character package
4. chat as this character
5. start insert session with this cast

## 4. Session Entry Module

Both Work and Character pages should reuse one unified session-entry module.

It should present exactly three choices:

1. `act` 代入角色
2. `insert` 你进入场景
3. `observe` 旁观推进

This module should explain:

- who speaks as “you”
- who the participants are
- what kind of replies will be generated

## 5. Visual Direction Notes

Guidelines:

1. Work page should feel like a workspace.
2. Character page should feel like a dossier.
3. Session page should feel like a live stage.

That means the three page types should not look identical.

## 6. Build Order Recommendation

Recommended implementation order:

1. Work Overview
2. Character Overview
3. Shared Session Entry Module
4. Character Health block
5. Session Memory block

This order gives the biggest product-feel improvement fastest.

## 7. Immediate Next Step

If design and engineering time are limited:

**build the Work Overview and Character Overview first, even if they start as simple read-only pages**

That alone will make `zaomeng` feel much more like a real product and much less like a growing tool panel.
