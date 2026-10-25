# Requirements

This document fixes what the architecture must satisfy *before* any component is
chosen. Every design decision in [architecture.md](architecture.md) and
[decisions/](decisions/) traces back to an item here.

## Problem statement

Resolve an enterprise operational exception end to end across ERP, supplier portal,
email and spreadsheets. The primary vertical slice is an **accounts-payable supplier
invoice exception**:

`invoice → PO → goods receipt → contract/rate evidence → discrepancy → resolution
proposal → policy / human approval → supplier correction or credit → ERP/AP
reconciliation → verified completion`

The first adjacent workflow is **freight recovery** (carrier invoice, rate card,
shipment and reweigh evidence). It must reuse the same run, approval, effect and
verification semantics with a different evidence model and domain policy.

## Hard constraints

| ID | Constraint | Acceptance test |
| --- | --- | --- |
| HC01 | Primary slice is the AP supplier-invoice exception, from evidence to verified reconciliation. | One end-to-end sequence covers invoice, PO, receipt/contract evidence, discrepancy, approval, supplier correction/credit and ERP reconciliation. |
| HC02 | Business authority stays in source-specific systems of record; the workflow database owns orchestration state only. | The architecture distinguishes source business facts from cached evidence with provenance, version and freshness. |
| HC03 | Policy-driven autonomy: deterministic policy and permissions authorize effects; the LLM cannot grant itself authority. | Every consequential effect passes deterministic authorization; high-risk, low-confidence or material actions can require a human. |
| HC04 | Completion means a verified business postcondition, not request submission. | `COMPLETED` is reachable only after independent verification against authoritative source state. |
| HC05 | Runs live days or weeks and survive deploys and restarts without holding compute. | Durable wait/timer states and resumable checkpoints are modelled. |
| HC06 | Integrations are heterogeneous and some writes have no idempotency support. | Effect execution supports API, browser, email and sheets, with explicit reconciliation of ambiguous outcomes. |
| HC07 | Multi-tenant enterprise SaaS. | Every durable object and control is tenant-scoped; any volume figure is labelled as an assumption. |
| HC08 | Correctness dominates automation rate; unauthorized or duplicate irreversible effects are the highest harm. | An unknown write result fails closed into reconciliation, never a blind retry. |
| HC09 | Hybrid control: a deterministic durable control plane plus dynamic LLM planning inside bounded capability envelopes. | Lifecycle, policy, effects and completion stay outside LLM control; the agent chooses its investigation path among allowed capabilities. |
| HC10 | Enterprise security controls and support for SOX-governed financial controls, without claiming certification. | Scoped credentials, RBAC/SSO, separation of duties, audit, data minimization, prompt-injection controls and a secure browser boundary are designed in. |
| HC11 | Build one slice first; generalize only stable execution primitives. | Reusable runtime primitives are identified; AP-specific rules and configuration live outside the engine. |
| HC12 | Prefer the existing product stack (TypeScript, Fastify, PostgreSQL, GCP); compare a workflow engine seriously but do not add it by default. | Temporal is evaluated with explicit adoption breakpoints. |

## Quality goals

| ID | Goal |
| --- | --- |
| QG1 | Minimal platform complexity and fast product iteration. |
| QG2 | Legible operator UX: current state, who or what the run waits for, evidence, deadline, next transition. |
| QG3 | Reusable for freight and payables variants without an over-designed universal DSL. |
| QG4 | Trade-offs and migration breakpoints are explicit and defensible. |

## Acceptance criteria

Each criterion has an executable check in [`verification/design_checks.py`](../verification/design_checks.py).

| ID | Observable behaviour |
| --- | --- |
| AC1 | A persisted run resumes after a simulated process restart from the last committed transition without repeating completed work. |
| AC2 | A timeout after a real side effect does not cause a second effect; the ambiguous result is reconciled to `CONFIRMED_APPLIED`. |
| AC3 | If reconciliation proves the effect absent, retry is allowed; if the target cannot be read, the effect goes to `NEEDS_RECONCILIATION`. |
| AC4 | An approval bound to stale source revisions cannot authorize an effect after the PO/invoice changes. |
| AC5 | `COMPLETED` cannot be reached until the business postcondition is verified. |
| AC6 | The policy gate blocks a consequential effect that lacks required approval. |
| AC7 | A duplicate queue delivery produces no duplicate business effect. |
| AC8 | The architecture contains tenant isolation, scoped credentials, separation of duties, tamper-evident audit, prompt-injection/tool-boundary controls and retention/data-minimization controls. |
| AC9 | Evidence records separate source authority from workflow cache and keep provenance, version and freshness metadata. |
| AC10 | The walkthrough presents the eight-component view, one AP happy/failure path and explicit trade-offs. |

## Traceability

| Requirement | Where it is designed | Decision | Check |
| --- | --- | --- | --- |
| HC01 | architecture §11–§12, walkthrough | — | AC10 |
| HC02 | architecture §3 | ADR-0007 | AC9 |
| HC03 | architecture §7, §9 | ADR-0004 | AC6 |
| HC04 | architecture §11 | ADR-0005 | AC5 |
| HC05 | architecture §5–§6 | ADR-0001, ADR-0006 | AC1 |
| HC06 | architecture §8, §10 | ADR-0002 | AC2, AC3 |
| HC07 | architecture §16 | — | AC8 |
| HC08 | architecture §10, §14 | ADR-0002 | AC2, AC3, AC7 |
| HC09 | architecture §7 | ADR-0004 | AC6 |
| HC10 | architecture §15 | — | AC8 |
| HC11 | architecture §19 | ADR-0001 | — |
| HC12 | architecture §18 | ADR-0001 | — |
| — (approval freshness) | architecture §9 | ADR-0003 | AC4 |

## Assumptions

- Volume, for sizing only: 10³–10⁵ cases/day across tenants. The load profile matters
  more than the number: many parked runs, fewer active reasoning runs, far fewer
  high-risk writes and browser sessions.
- Connector capabilities (ETag support, idempotent endpoints, read-after-write) vary
  per customer and are declared per capability. See [open-questions.md](open-questions.md).
