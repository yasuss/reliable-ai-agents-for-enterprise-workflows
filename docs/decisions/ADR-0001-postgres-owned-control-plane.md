# ADR-0001: PostgreSQL-owned durable control plane

- Status: Accepted
- Date: 2026-10-25
- Requirements: HC05, HC11, HC12, QG1, QG4

## Context

Runs last days or weeks, wait for humans and suppliers, and must survive deploys and
crashes. The same system also needs rich, queryable domain state — cases, evidence,
approvals, effects, verification, audit — for operators, policy and verification.
The product team works in TypeScript on PostgreSQL and GCP and optimizes for delivery
speed.

The central problem is not "how does an LLM call SAP" but how to complete a business
outcome safely when reasoning is probabilistic, external systems are unreliable, writes
may be non-idempotent, and a human may answer hours later after the source has changed.

## Decision

Build the first production slice as a **PostgreSQL-owned durable control plane** in the
existing TypeScript / Fastify / PostgreSQL / GCP stack:

- a durable `Case` / `Run` state machine in PostgreSQL with optimistic versioning;
- every transition in one transaction: check version, validate transition, append audit,
  write state, write outbox row ([ADR-0006](ADR-0006-persisted-timers-and-outbox.md));
- short-lived Cloud Run workers dispatched by Cloud Tasks;
- bounded LLM investigation inside an explicit capability envelope
  ([ADR-0004](ADR-0004-deterministic-policy-outside-the-llm.md)).

Workers are disposable; the state is not.

## Alternatives considered

| Option | Verdict | Reason |
| --- | --- | --- |
| Temporal + activities + PostgreSQL projections | Serious alternative | Excellent for durable timers, signals, replay and many topologies. But it adds a runtime and programming model (determinism, versioning), PostgreSQL is still needed for domain state, and external activities still need an effect ledger. |
| Managed cloud orchestrator (GCP Workflows-style) | Not selected | The valuable state is domain state in PostgreSQL; a dynamic evidence-driven loop fits a DSL poorly; splitting state across two systems adds a consistency boundary; no help with cross-system effects. |
| Free-form durable agent loop | Ineligible | Lifecycle, authority, retries and completion would become model-dependent; audit could not prove why a mutation was authorized. Useful *inside* investigation only. |
| DBOS, Restate, Durable Task, Conductor/Orkes, Trigger.dev, Cloudflare Workflows | Reviewed | Validate the design space; no requirement-level reason to adopt before the first slice. DBOS is worth revisiting as a PostgreSQL-native library. |

Details: [alternatives.md](../alternatives.md).

## Revisit when (measured, not assumed)

- timer / resume / replay / versioning code becomes a frequent incident source;
- the team maintains many workflow topologies, child workflows, sagas or compensation graphs;
- workflow-runtime code becomes a material share of feature delivery effort;
- several teams or languages need a common workflow runtime and independent worker fleets;
- built-in history, replay and visibility would reduce operational risk more than the
  migration and platform cost.

Run duration alone is **not** a reason to switch — persisted state and timers already
handle it.

## Consequences

- Correctness properties live in ordinary deterministic code and SQL constraints that the
  team already operates.
- Risk: the control plane slowly grows into a general workflow engine. Mitigation: keep
  runtime primitives small, keep domain rules in workflow code/config, track
  orchestration-specific effort.
- Migration path stays open: Case/Run IDs, evidence, capability, approval fingerprint,
  effect identity, verification and audit contracts are orchestrator-independent, so a
  move to Temporal maps Run → Workflow, steps → Activities, callbacks → Signals/Updates,
  timers → durable timers, while the effect ledger remains the side-effect boundary
  ([rollout-and-migration.md](../rollout-and-migration.md)).
