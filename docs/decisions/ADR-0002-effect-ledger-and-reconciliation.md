# ADR-0002: Semantic effect ledger with reconciliation

- Status: Accepted
- Date: 2026-10-25
- Requirements: HC06, HC08 · Checks: AC2, AC3, AC7

## Context

Effects go to SAP, supplier portals, email and spreadsheets. Some targets support
idempotency keys or ETags; browser portals and many email paths do not. Queues
(Cloud Tasks) and workflow engines deliver work at least once. A write can commit on the
target while the caller sees a timeout.

## Decision

Every external mutation is an **`Effect`** — one intended business change with a stable
`effect_id` and a semantic business key (`tenant + action_type + source_object +
proposal_version`). Transport tries are **`EffectAttempt`** rows.

1. Persist the intent (`EffectAttempt(INTENT_RECORDED)`) **before** calling the target.
2. Use the target's idempotency key / repeatability headers / `If-Match` when available.
3. Otherwise read-before-write when it can prove the effect is absent.
4. On clear success: store the receipt, then verify.
5. On clear failure before any side effect: bounded retry.
6. On timeout or connection loss after dispatch: **`UNKNOWN_EFFECT_STATE`**.
7. Reconcile by business key / read-back / search:
   applied → `CONFIRMED_APPLIED`; provably absent → retry allowed;
   cannot prove → `NEEDS_RECONCILIATION` and a human.

**A timeout is not evidence of failure.**

## Alternatives considered

- **Rely on queue or engine retries** — rejected: at-least-once delivery plus a
  non-idempotent target produces duplicate business effects.
- **Claim cross-system exactly-once** — rejected: not achievable across SAP, email and
  browsers; the honest guarantee is exactly one semantic intent in our ledger.
- **Never retry, always escalate** — rejected: wastes human attention on effects that
  reconciliation can prove absent.

## Consequences

- Duplicate-effect rate is an alerting metric with a target of zero.
- Every capability declares `supports_idempotency_key`, `supports_read_after_write`,
  `supports_version_precondition` and a verification strategy.
- Browser adapters must record enough pre/post state to tell "no submit attempted",
  "submit confirmed" and "submit possibly happened"; only the first is auto-retryable.
- This ledger is required **regardless of orchestrator**, including after any move to Temporal.
