# Open questions

No open question blocks the first-slice architecture. The facts below are deliberately
**not assumed**; each has an explicit branch in the design and a way to resolve it.

## Q1 — Customer-specific SAP semantics

SAP deployments and endpoints differ in:

- ETag / version-precondition support;
- repeatable (idempotent) request support;
- write APIs versus browser-only flows;
- available business keys and read-after-write queries.

**Branch:** capability metadata declares these properties per connector
([architecture.md §8](architecture.md#8-capability-and-connection-boundary)). Use native
concurrency and idempotency when available; otherwise business-key reconciliation.

**Resolved by:** connector contract tests against each customer's sandbox.

## Q2 — Throughput and hot-tenant distribution

No production volume is assumed as fact. The sizing assumption is 10³–10⁵ cases/day
across tenants.

**Branch:** scale by measured active reasoning, effect and browser concurrency — not by
raw case count. Waiting runs are cheap persisted state.

**Resolved by:** pilot-customer volumes and per-capability concurrency metrics.

## Q3 — Workflow-engine adoption breakpoint

Whether owned orchestration stays small cannot be known before production.

**Branch:** start PostgreSQL-native; adopt Temporal (or DBOS / Restate) when the
breakpoints in [ADR-0001](decisions/ADR-0001-postgres-owned-control-plane.md) are crossed.

**Resolved by:** tracking incidents and engineering effort caused specifically by timers,
replay/resume, workflow versioning, fan-out/fan-in and compensation.

## Q4 — Legal and compliance approval rules per customer

The architecture supports policy-driven thresholds and separation of duties, but the
legally or contractually required approval boundaries are customer- and process-specific.

**Branch:** the customer's process owner and compliance function define policy; the model
never infers legal authority.

## Q5 — Connector behaviour under failure

The [design checks](../verification/README.md) model failure semantics; they do not prove
SAP, portal, email-provider or browser behaviour.

**Resolved by:** connector contract tests, sandbox integration tests and production-like
failure injection during implementation.
