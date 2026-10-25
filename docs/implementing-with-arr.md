# Implementing with Agent Reliability Runtime (ARR)

[Agent Reliability Runtime](https://github.com/yasuss/agent-reliability-runtime) is a
local-first Python runtime that implements and tests the reliability semantics this
architecture depends on: trusted policy, exact approval, idempotent effect receipts,
postcondition verification, durable restart, audit and deterministic evaluation.
ARR v2 exposes them through a framework-neutral `core/` and structural ports
([`core/ports.py`](https://github.com/yasuss/agent-reliability-runtime/blob/v2.0.0/src/agent_reliability_runtime/core/ports.py),
[extension points](https://github.com/yasuss/agent-reliability-runtime/blob/v2.0.0/docs/extension-points.md)).

This repository has **no runtime dependency on ARR**. The architecture can be built on the
TypeScript reference stack directly. ARR is the second path: a Python implementation that
reuses semantics already proven by ARR's tests and proof index, instead of re-deriving them.

## How the two relate

- This repository defines **what** a long-running, multi-system enterprise workflow needs.
- ARR v2 provides **tested building blocks** for a subset of it, and defines the rest as
  planned interface-only ports. Those four planned ports — `Reconciler`, `TimerStore`,
  `SourceRevisionReader`, `CapabilityRegistry` — were derived from this architecture's
  requirements.

## Component mapping

| Component (this architecture) | ARR v2 | Status in ARR | What remains to build |
| --- | --- | --- | --- |
| Investigation Agent | `ModelProvider`, `Retriever`; LangGraph orchestration in `adapters.langgraph` | Implemented | AP-specific tools and prompts; typed `ProposedResolution` |
| Evidence + Connectors | `Retriever` (hybrid retrieval with citations) | Implemented | ERP / WMS / portal / email connectors |
| ↳ source versions for each fact | `SourceRevisionReader`, `SourceRef`, `SourceRevision` | **Planned** — interface only | Implementation per source system (ETag, version, hash) |
| ↳ capability metadata | `CapabilityRegistry`, `CapabilityDefinition` | **Planned** — interface only | Registry with idempotency / read-after-write / risk metadata |
| Policy | `PolicyEngine` (`risk_for`, `validate_model_args`, `propose`, `validate`) | Implemented | AP policy tiers: amount thresholds, evidence completeness, SoD |
| Human approval | `Approver`; `core.approval.Approval` — digest of run, tool, normalized arguments and policy version; expiry; one-time `CONSUMED` | Implemented | Bind the source revision set into the fingerprint ([ADR-0003](decisions/ADR-0003-approval-fingerprint-and-revalidation.md)); reviewer authority context |
| Effect Executor | `EffectStore` (`receipt_for`); exactly-once receipts in `adapters.postgres.execution` | Implemented, narrow port | Connector executors; widening the port to record intent and receipt |
| ↳ ambiguous outcomes | `Reconciler`; `core.effects.ReconciliationStatus` (`CONFIRMED_APPLIED`, `CONFIRMED_NOT_APPLIED`, `UNKNOWN_EFFECT_STATE`) | **Planned** — interface and value types | Read-back / search per target ([ADR-0002](decisions/ADR-0002-effect-ledger-and-reconciliation.md)) |
| Verification | `Verifier`, `core.verification.RuleVerifier`, `VerificationStatus` (`PASS` / `FAIL` / `PARTIAL`) | Implemented (rule verifier emits PASS/FAIL) | AP postconditions: credit observed + ERP reconciled; partial recovery ([ADR-0005](decisions/ADR-0005-verified-business-completion.md)) |
| Durable Control Plane | `CheckpointStore` (LangGraph PostgreSQL checkpoints) | Implemented — restart durability | Multi-day case lifecycle |
| ↳ timers and parked runs | `TimerStore`, `TimerSpec` | **Planned** — interface only | Timer table + scanner ([ADR-0006](decisions/ADR-0006-persisted-timers-and-outbox.md)) |
| ↳ outbox and dispatch | — | Not in ARR | Transactional outbox and publisher |
| Operator UI + Audit | Audit and OTel adapters (`adapters.postgres.audit`, `adapters.otel`) | Implemented (not a port) | Operator UI; SIEM export |
| Multi-tenancy | — | Not in ARR | Tenant scoping, per-tenant credentials and policy ([architecture §16](architecture.md#16-multi-tenancy-and-scaling)) |

## Suggested order on the ARR path

1. **Shadow mode** — Investigation Agent on `ModelProvider` + `Retriever` with read-only
   connectors; proposals reviewed by humans; no writes.
2. **Source revisions** — implement `SourceRevisionReader`; add the revision set to the
   approval fingerprint; revalidate before execution.
3. **Effects** — connector executors behind `EffectStore`; implement `Reconciler` for each
   target that can be read back; route the rest to `NEEDS_RECONCILIATION`.
4. **Long waits** — implement `TimerStore` and an outbox; park runs in `WAITING_EXTERNAL`.
5. **Verification** — AP postcondition rules on `Verifier`, including `PARTIAL`.
6. **Policy tiers** — pre-authorized low-risk actions once shadow and approval-required
   stages show stable quality ([rollout-and-migration.md](rollout-and-migration.md)).

## Limits

ARR is a reference runtime with a fictional demo domain, single-agent LangGraph
orchestration and no multi-tenancy. It does not include enterprise connectors. Its
guarantees apply to the adapters it ships; a new adapter must reproduce the same
semantics — for example, a custom `EffectStore` does not inherit duplicate protection
automatically.
