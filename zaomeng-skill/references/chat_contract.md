# Dialogue Handoff Contract

## Purpose

This document defines how the host should enter `act`, `insert`, and `observe` after the structured workflow completes.

The goal is simple:

- the skill prepares persona bundles and relationship artifacts
- the host uses those artifacts directly to run dialogue
- the packaged skill does not require a separate `chat CLI` entrypoint

## Supported Modes

- `act`
  the user speaks as one existing character
- `insert`
  the user enters the scene as themselves
- `observe`
  the user stays outside the scene and watches the cast continue

## Required Inputs

Before the host starts dialogue, it should already have:

- the novel id or novel path for the current run
- the requested cast
- one persona bundle directory per distilled character
- relationship markdown or graph artifacts when available
- `run_manifest.json` from the current run

Minimum persona inputs per active character:

- `PROFILE.md`
- `MEMORY.md`

Recommended additional persona inputs when present:

- `SOUL.md`
- `GOALS.md`
- `STYLE.md`
- `TRAUMA.md`
- `IDENTITY.md`
- `BACKGROUND.md`
- `CAPABILITY.md`
- `BONDS.md`
- `CONFLICTS.md`
- `ROLE.md`

## Host Responsibilities

### 1. Mode Selection

The host decides whether the request is:

- `act`
- `insert`
- `observe`

### 2. Active Cast Selection

The host determines which characters are active for the current turn or scene.

Recommended inputs:

- explicitly requested characters
- relation graph context
- current scene focus

### 3. Self-Insert Card

For `insert`, the host should create or refresh a lightweight self-insert card, for example:

- user display name
- current in-scene identity
- how they entered the scene
- what the cast should currently know about them

If the host wants packaged helpers instead of hand-writing this layer, use:

- `tools/manage_self_card.py --mode blank`
- `tools/manage_self_card.py --mode save`
- `tools/manage_self_card.py --mode build-random-payload`
- `tools/manage_self_card.py --mode parse-random-response`

This lets the host support both manual role-card editing and AI-random role-card generation through the packaged skill helpers.

### 4. Dialogue Rendering

The host performs the actual generation. It should use the persona bundle and constraints to keep the output:

- in character
- mode-consistent
- relation-aware
- scene-aware

If the host wants a packaged one-line reply suggestion flow, call:

- `tools/build_dialogue_suggestion_payload.py --context-file <context.json>`

The tool returns:

- full messages
- retry messages
- compact fallback payload/messages

For persona review autofill, call:

- `tools/build_persona_autofill_payload.py --persona-dir <角色目录> --field <字段名> --strategy auto`

The tool returns:

- model-knowledge-first step
- optional web-fallback step
- retry messages
- parser contract for model output

## Recommended Artifact Read Order

1. `run_manifest.json`
2. relation markdown and graph artifacts
3. `PROFILE.md`
4. split persona files
5. `MEMORY.md`

## Output Expectations

The exact dialogue output format is host-defined.

At minimum, the host should keep enough structured state to know:

- current mode
- active cast
- controlled character for `act`
- self-insert identity for `insert`
- latest scene summary
- latest turn outputs

## Host UI Guidance

After the structured workflow completes, the host should surface:

- character directories
- relationship graph HTML / SVG
- workflow summary from `run_manifest.json`
- a clear prompt that the user can now enter `act`, `insert`, or `observe`
