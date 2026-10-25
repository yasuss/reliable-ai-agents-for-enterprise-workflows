# Alternatives

Four architecture families were evaluated against the [requirements](requirements.md). The selected design and its revisit conditions are recorded in [ADR-0001](decisions/ADR-0001-postgres-owned-control-plane.md).

| Option | Status |
| --- | --- |
| A — PostgreSQL-native durable control plane + GCP dispatch | **Selected** |
| B — Temporal + activities + PostgreSQL domain projections | Serious alternative, documented migration path |
| C — Managed cloud orchestrator (GCP Workflows-style) | Not selected |
| D — Free-form durable agent loop | Ineligible (fails hard constraints) |

## Option A — PostgreSQL-native durable control plane + GCP dispatch

**Status: SELECTED**

Mechanism:

- PostgreSQL owns run/effect/approval/timer state;
- transactional outbox makes runnable work durable;
- short-lived Cloud Tasks/Cloud Run workers execute steps;
- LLM reasoning is bounded by deterministic lifecycle/policy/effect contracts.

Why it wins now:

- strongest fit to the existing TypeScript/Fastify/PostgreSQL/GCP product stack;
- the domain already requires PostgreSQL entities for cases, approvals, effects and verification even if a workflow engine is added;
- keeps the first AP slice small enough to ship and learn;
- does not pretend Cloud Tasks supplies exactly-once business effects;
- makes ambiguous external effects explicit rather than hiding them behind framework retry semantics.

Main risk: the team may gradually rebuild a general workflow engine. The design therefore defines explicit adoption breakpoints for buying that runtime later.

---

## Option B — Temporal + activities + PostgreSQL domain projections

**Status: SERIOUS ALTERNATIVE**

Temporal is an excellent match for:

- long-running workflow state;
- durable timers/signals;
- worker crash recovery through event history;
- HITL waiting;
- many workflow topologies and worker fleets.

It does **not** eliminate the core business-effect problem. External activities can still be observed more than once around failures/retries, so SAP/email/browser mutations still need an effect identity, idempotency or reconciliation.

### Why not choose it for the first slice

- adds a new runtime/service and programming model to a product team optimized for delivery speed;
- workflow code must respect replay/determinism/versioning constraints;
- operational/debugging expertise and migration become part of the product-engineering surface;
- PostgreSQL is still needed for domain/queryable case state, evidence, policy, audit and business projections.

### What would change the decision

Choose Temporal when observed production data shows that custom timer/resume/version/replay semantics, nested workflows or orchestration incidents are a recurring cost greater than running/adopting the engine.

---

## Option C — managed cloud orchestrator (GCP Workflows-style)

**Status: NOT SELECTED**

Strengths:

- managed durability;
- callbacks/waits/retries;
- reduced scheduler infrastructure;
- native cloud operations.

Why it loses for this case:

- the most valuable control state is rich product/domain state queried by operators, policies and verification, so PostgreSQL remains central;
- a dynamic evidence-driven agent loop is less naturally expressed in an orchestration DSL than ordinary TypeScript domain code;
- splitting orchestration semantics between managed workflow state and application state creates an additional consistency/debugging boundary;
- it still does not solve cross-system exactly-once effects.

This option could be attractive for narrower, static integration flows with fewer product-specific states.

---

## Option D — free-form durable agent loop

**Status: INELIGIBLE**

Mechanism: serialize agent state and let the model decide the sequence, tools, approval requests and completion.

Why it fails hard requirements:

- lifecycle and authority become model-dependent;
- approval boundaries are less deterministic;
- retry/effect semantics are too easy to conflate with tool-call retries;
- “agent says done” can drift from verified business completion;
- audit/replay cannot reliably prove why a consequential mutation was authorized.

A durable agent loop is useful **inside** the investigation stage, not as the system's final authority boundary.

---

## Challenge reviews

The selected design was deliberately attacked from four directions.

### Main disagreement

**Main disagreement:** Postgres-native runtime vs Temporal.

Nearest observable discriminator: measure actual engineering/incident burden of custom timer/resume/versioning logic over the first real workflows. No current evidence shows that burden is already large enough to outweigh adopting a new runtime, so the simpler current-stack design wins provisionally for the first slice.

### Challenging the shared assumption

Shared wrong assumption attacked: “durable engine means exactly-once effects.”

Result: rejected. GCP queues, Temporal-style activities and distributed workers can all produce retry/redelivery ambiguity around external side effects. The effect ledger + reconciliation contract remains mandatory regardless of orchestrator.

### Other durable-execution families

Additional families checked: DBOS, Restate, Microsoft Durable Task, Conductor/Orkes, Trigger.dev and Cloudflare Workflows.

Result: these validate the durable-execution/HITL design space but do not provide a requirement-level reason to introduce a new runtime before the AP vertical slice. DBOS is particularly worth revisiting if a Postgres-native library becomes preferable to owned orchestration code.

### Simplicity review

Removed as unnecessary for V1:

- universal workflow DSL;
- event-sourcing every business entity;
- Kafka/Pub/Sub as canonical state;
- multi-agent architecture for work one investigation agent can do;
- global exactly-once claims;
- always-on human approval for every external write;
- Temporal by default.

Protections retained:

- durable state;
- explicit approvals;
- effect identity;
- reconciliation;
- verified completion;
- audit/provenance;
- tenant/security boundaries.

---

## Falsification scenarios applied to the selected design

Full adversarial review: [failure-modes.md](failure-modes.md).

1. **SAP write succeeds but response times out** → `UNKNOWN_EFFECT_STATE`; reconcile before retry.
2. **Supplier portal UI changes** → browser adapter detects drift/failure; capture evidence; do not let the model bypass policy/tool contract.
3. **Human approves after 12 hours and PO changed** → source revision revalidation fails; approval invalidated and case returns to investigation/reapproval.
4. **Same supplier email job delivered twice** → stable effect ID/business key and receipt suppress second send; ambiguous first send reconciles before retry.
5. **Browser authentication expires** → connection becomes unhealthy; run parks for re-auth rather than weakening permissions.
6. **Customer asks why the agent acted** → audit graph links evidence → proposal → policy → reviewer (if any) → effect → receipt → verification.
7. **Want 90% automation** → reduce approvals through explicit pre-authorized low-risk policy tiers, not by allowing the model to self-authorize.
8. **New customer uses different ERP** → new connection/capability adapter and mappings; durable control/effect/approval semantics remain unchanged.
