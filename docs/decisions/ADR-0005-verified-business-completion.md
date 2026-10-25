# ADR-0005: Completion means a verified business postcondition

- Status: Accepted
- Date: 2026-10-25
- Requirements: HC04 · Check: AC5

## Context

In AP recovery the valuable outcome is recovered money and a reconciled ledger, not an
action taken. SAP returning 200, an email being sent or a claim being submitted are all
intermediate. Suppliers may never answer, or credit only part of the amount.

## Decision

The completion contract belongs to the workflow definition. For AP recovery:

`POTENTIAL_EXCEPTION → VALIDATED_EXCEPTION → ACTION_DECIDED → ACTION_APPROVED →
ACTION_SUBMITTED → WAITING_EXTERNAL → CORRECTION_OBSERVED → ERP_RECONCILED →
OUTCOME_VERIFIED → COMPLETED`

A `Verification` record stores the expected postcondition, authoritative sources checked,
source versions and time, observed values, **pass / fail / partial**, evidence references
and verifier version. `COMPLETED` is reachable only after a passing verification.

**Partial recovery stays open** with the remaining balance instead of being flattened into
success.

## Alternatives considered

- **"Agent says done"** — rejected: completion drifts from reality.
- **Transport success as completion** — rejected: hides missing credits and unreconciled ERP state.

## Consequences

- Runs can wait in `WAITING_EXTERNAL` for long periods with reminders and escalation
  ([ADR-0006](ADR-0006-persisted-timers-and-outbox.md)).
- The headline metric is *verified* completion rate, not number of automated actions.
