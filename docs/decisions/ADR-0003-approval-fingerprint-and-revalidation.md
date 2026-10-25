# ADR-0003: Approval bound to an exact proposal, revalidated before execution

- Status: Accepted
- Date: 2026-10-25
- Requirements: HC03, HC10 · Check: AC4

## Context

Reviewers may answer hours or days after a proposal is made. In that time the PO, invoice
or policy can change. A generic "approve / continue" button would authorize whatever the
agent does next, against data the reviewer never saw.

## Decision

An approval creates an immutable `ApprovalDecision` bound to an **approval fingerprint**:

- proposal hash;
- exact tool / capability and target system / object;
- intended mutation and amount;
- evidence and source revision set;
- policy version;
- reviewer authority context;
- expiry.

Before an approved effect executes:

1. re-read load-bearing source records or their version tokens;
2. compare with the `sourceRevisionSet` bound to the approval;
3. re-run policy if any relevant fact or the policy changed;
4. on material change, invalidate the approval and return to investigation / re-approval.

Where SAP exposes ETags, the write sends `If-Match`, turning a stale write into a
controlled concurrency conflict.

## Alternatives considered

- **Generic continue button** — rejected: approval no longer describes the executed action.
- **Re-approve on every wait** — rejected: approval fatigue; humans start rubber-stamping.
- **Trust the cached evidence** — rejected: violates source-of-record authority
  ([ADR-0007](ADR-0007-source-of-record-per-fact.md)).

## Consequences

- The approval UI must show the exact change, amount, evidence, source freshness, policy
  reason, outcome of approve/reject and expiry.
- Reviewer identity, authority scope and timestamp are recorded independently of the
  executing identity (maker/checker).
