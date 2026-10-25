# Risks, rollout and migration

Related: [ADR-0001](decisions/ADR-0001-postgres-owned-control-plane.md) (when to adopt Temporal) · [failure-modes.md](failure-modes.md) · [architecture.md §19](architecture.md#19-evolution-path).

## Top risks

### 1. Custom control plane grows into a workflow engine

**Risk:** every new process adds special timer/retry/branch logic until the runtime becomes expensive to maintain.

**Mitigation:** keep the runtime primitives deliberately small; domain rules live in workflow code/config. Track orchestration-specific incidents and engineering effort. Re-evaluate Temporal/DBOS/Restate using observed burden, not architecture fashion.

### 2. Ambiguous browser/API writes

**Risk:** the remote system applied the mutation but the worker lost the response; blind retry duplicates a claim, email or posting.

**Mitigation:** semantic `Effect` identity, request fingerprints, target-native idempotency where available, read-before/read-after checks, explicit `UNKNOWN_EFFECT_STATE`, reconciliation-first policy.

### 3. Stale approval / time-of-check-time-of-use

**Risk:** a reviewer approved one PO/invoice state, but the source changed while the run waited.

**Mitigation:** approval fingerprint binds source revision set; mandatory pre-execution revalidation; ETag/If-Match when supported; reapproval on material change.

### 4. Approval overload

**Risk:** humans become the bottleneck and learn to rubber-stamp.

**Mitigation:** policy tiers, pre-authorized low-risk actions, only interrupt on material/ambiguous/out-of-policy cases, show concise evidence and exact diff, measure approval/override rates.

### 5. Prompt injection from supplier-controlled content

**Risk:** email/document/portal text attempts to manipulate the agent into an unauthorized action.

**Mitigation:** untrusted-content boundary, typed tools, least-privilege credentials, deterministic policy gate at effect boundary, explicit approval for high-impact actions, no secrets in prompt/context.

### 6. Evidence/audit data explosion

**Risk:** retaining raw HTML, screenshots, emails and documents creates storage/privacy burden.

**Mitigation:** normalized facts + hashes/references by default; preserve raw artifacts only when necessary; lifecycle/retention policy; archive/cold storage; tenant-specific contractual retention.

### 7. Cross-run races

**Risk:** two cases or retries act on the same invoice simultaneously.

**Mitigation:** case business keys, active resource claims, effect uniqueness, optimistic source concurrency controls, final read-back verification.

---

## Rollout

### Stage 0 — shadow/read-only

- ingest representative AP exceptions;
- build evidence bundle and proposed resolution;
- compare with human decisions;
- no external writes;
- measure false positives, missing evidence, operator trust and time saved.

**Exit:** evidence/proposal quality is good enough that a reviewer can make decisions faster without losing traceability.

### Stage 1 — approval-required effects

- every consequential write requires human approval;
- enable effect ledger, idempotency/reconciliation and postcondition verification;
- run failure drills before widening scope.

**Exit:** zero unexplained duplicate effects and reliable recovery from ambiguous writes in the scoped connectors.

### Stage 2 — low-risk policy autonomy

- process owner pre-authorizes reversible/low-risk actions under clear thresholds;
- financial/high-risk/low-confidence cases still gate;
- measure intervention rate and operator corrections.

**Exit:** automation reduces touch time without increasing correction/exception risk.

### Stage 3 — more workflows/connectors

- add freight recovery as first adjacent case;
- only then extract repeated domain/runtime patterns;
- evaluate whether orchestration burden justifies a dedicated durable engine.

---

## Rollback / kill switch

Tenant/process owner can:

- pause new runs;
- revoke write-capable credentials;
- force all effects into approval-only mode;
- disable a connector/capability version;
- stop/cancel a run before unexecuted effects;
- route unresolved cases to manual operation.

Already-applied external effects are not “rolled back” generically. Compensation is domain-specific and must be explicitly modeled as another authorized effect.

---

## Migration to Temporal later

Preserve stable domain contracts so orchestration can move without redesigning safety semantics:

- Case/Run IDs and public state vocabulary;
- Evidence/provenance model;
- Capability contract;
- Policy/approval fingerprint;
- Effect/effect-attempt identity;
- verification/postcondition contract;
- audit event schema.

Then map:

- Run lifecycle → Temporal Workflow;
- short steps / connectors → Activities;
- human/external callbacks → Signals/Updates;
- timers → durable timers;
- existing effect ledger remains the external-side-effect safety boundary.

Migrate workflow families incrementally rather than rewriting all active runs at once.
