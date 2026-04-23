# Safety Policy

## Execution Boundaries

- Local-first by default.
- No mandatory network fetch in runtime instructions.
- No arbitrary shell execution requirement.

## Data Safety

- Do not request or store credentials.
- Avoid personal/sensitive data in examples and outputs.
- Keep outputs constrained to provided text evidence.

## Integrity Checks

- If evidence is sparse, emit low-confidence result.
- If schema check fails, return `needs_revision`.
- If user requests unsafe action, refuse and suggest safe alternative.

