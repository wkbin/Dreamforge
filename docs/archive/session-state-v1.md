# Session State V1

## Goal

This branch treats dialogue session state as a first-class runtime model instead of a loose bag of side effects.

We intentionally optimize for a clean canonical schema rather than backward compatibility.

## Canonical State

Each dialogue session owns one canonical `state` object:

```json
{
  "version": 1,
  "scene": {
    "location": "",
    "time_hint": "",
    "atmosphere_summary": "",
    "progression_note": "",
    "updated_at": ""
  },
  "presence": {
    "present_participants": [],
    "offstage_participants": [],
    "updated_at": ""
  },
  "progression": {
    "should_offer_scene_shift": false,
    "scene_shift_reason": "",
    "turns_in_current_scene": 0,
    "beat_maturity": 0,
    "world_tension_summary": "",
    "updated_at": ""
  },
  "relations": {
    "matrix": {},
    "delta": {}
  },
  "characters": {
    "snapshots": {}
  },
  "signals": {
    "recent": [],
    "by_type": {},
    "updated_at": ""
  },
  "memory": {
    "summary": {}
  }
}
```

## Rules

1. `state` is the only source of truth for session runtime evolution.
2. API payloads may still project convenience views like `scene_progress` or `relation_delta`, but those are derived views, not primary storage.
3. Session payloads may expose derived helpers like `runtime_state_overview` for UI rendering, but these are read-only projections from canonical `state`.
4. `runtime_state_overview` should stay presentation-friendly: short labels, trimmed text, and stable ordering for characters / relations / events.
5. Scene flow is split into three concerns:
   - `scene`: where/when/what tone the current beat has
   - `presence`: who is currently onstage or offstage
   - `progression`: whether the beat is mature enough to shift scenes
6. Relationship updates are split into:
   - `relations.matrix`: baseline merged relation graph for session participants
   - `relations.delta`: session-local drift caused by this conversation
7. Character-local runtime drift belongs in `characters.snapshots`.
8. Small event cues, transitions, exits, and atmosphere shifts belong in `signals`.
9. Compression summaries belong in `memory.summary`.

## Implementation Checklist

### Slice 1: Canonical State Foundation

- [x] Define the canonical session-state schema
- [x] Centralize session-state creation and normalization
- [x] Project derived `scene_progress` from canonical state
- [x] Project derived `relation_delta`, `character_snapshots`, and `event_signals`
- [x] Move session-store readers to canonical state paths

### Slice 2: Progression Engine

- [x] Split time, location, atmosphere, and onstage/offstage decisions into dedicated state updaters
- [x] Track scene maturity explicitly in `progression.beat_maturity`
- [x] Let narration, exits, and returns update canonical presence state directly

### Slice 3: Session Snapshots

- [x] Expand character snapshots into stable per-character runtime cards
- [x] Expand relation deltas into stable per-pair interaction drift
- [x] Add explicit session-level world tension / atmosphere summary

### Slice 4: Prompt Integration

- [x] Feed canonical state into turn payloads
- [x] Feed canonical state into suggestion payloads
- [x] Feed canonical state into scene-progress generation prompts
- [x] Trim prompt payloads using canonical active-state priority

### Slice 5: UI Integration

- [x] Surface canonical presence/time/progression hints in the chat UI
- [x] Surface natural next-scene hints from `progression`
- [x] Surface per-character session drift from `characters.snapshots`

## Non-Goals

- Preserving every old session-state shape on disk
- Layering more compatibility shims for low-value legacy paths
- Keeping duplicated state across multiple top-level session fields
