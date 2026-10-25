# Failure modes

An adversarial review of the selected architecture: each row tries to make the design fail on a scenario that commonly breaks enterprise-agent systems. No scenario produced a contradiction with the [requirements](requirements.md); two pass only with an explicit implementation obligation, and the residual risks are listed below.

The operational failure matrix (default behaviour per failure class) is in [architecture.md §14](architecture.md#14-failure-handling-matrix).

## Attacks and outcomes

| Attack | Result | Why the design survives |
|---|---|---|
| SAP write commits, response times out | PASS | Effect becomes `UNKNOWN_EFFECT_STATE`; reconciliation reads target state before any retry. |
| Queue delivers the same work twice | PASS | Queue delivery is not business uniqueness; stable `Effect` identity/business key and persisted step state suppress duplicate semantic effects. |
| Human approves after 12 hours, PO changed | PASS | Approval is bound to source revisions/policy/proposal; execution revalidates and stale approval is rejected. |
| Supplier portal UI changes | PASS | Browser adapter failure is isolated from orchestration; bounded retries/escalation occur without blindly replaying irreversible actions. |
| Same supplier email could be sent twice | PASS | Outbound communication is modeled as an Effect with semantic idempotency/dedup and reconciliation where provider semantics are ambiguous. |
| Browser session loses authentication | PASS | Session/auth failure is an adapter failure; credentials remain server-side and run returns to retry/escalation rather than losing durable state. |
| Malicious text in email/document says “ignore policy and pay” | PASS | External content is untrusted evidence; model only proposes; typed capability + deterministic policy/authorization gate owns effects. |
| Model hallucinates authority | PASS | Model cannot authorize capabilities, approvals, financial thresholds, or terminal completion. |
| Approval is valid but target object changed | PASS | Revalidation/optimistic concurrency prevents stale write; connector uses target version semantics such as ETag/`If-Match` where supported. |
| Credit request was sent but credit never arrives | PASS | Submission is intermediate; run stays open/waits/escalates until configured business postcondition is observed. |
| Deploy/restart while waiting days | PASS | Waiting is persisted state + timer, not a blocked process; disposable worker resumes from durable checkpoint. |
| DB commit succeeds but dispatch publish fails | PASS | Transactional outbox makes dispatch recoverable. |
| Dispatch succeeds but worker crashes before ack | PASS | At-least-once redelivery is safe because work/effects are keyed and state transitions are durable. |
| Two runs race on same invoice | PASS with implementation obligation | Case/effect business keys plus optimistic/row-level concurrency prevent unaware duplicate resolution; production connector tests remain required. |
| Human approval becomes the bottleneck | PASS | Policy tiers allow pre-authorized low-risk actions; evidence-first approval UI and metrics expose approval load. |
| Customer asks for 90% touchless | PASS | Automation rate is optimized only inside policy/evidence boundaries; low-confidence/high-impact cases stay human-routed. |
| New customer has a different ERP | PASS | Durable execution semantics remain stable; connector/capability mapping and customer policy are replaced rather than the engine. |
| Need to prove why the agent acted | PASS | Audit links evidence lineage, typed proposal, policy version/decision, approval, effect receipt, verification and outcome. |
| Evidence cache drifts from source of truth | PASS | Cached facts retain source identity/version/freshness; source systems remain authoritative. |
| A workflow engine is added too early | PASS | Temporal remains a documented challenger with explicit adoption breakpoints, not a default dependency. |
| Custom state-machine complexity later explodes | PASS with migration path | Core domain contracts (`Case`, `Run`, `Effect`, `Approval`, `Verification`) are kept independent enough to move orchestration to Temporal when measured breakpoints are crossed. |
| Compliance language overclaims | PASS | Design says “supports SOX-governed controls”; it does not claim SOX certification or compliance. |

## Claims the design deliberately does not make

- No cross-system exactly-once guarantee.
- No financial/business state is made authoritative merely because it is cached by the workflow.
- No approval is treated as a generic reusable “continue” token.
- No model reasoning trace is required for audit; audit stores structured evidence/rationale/decisions rather than hidden chain-of-thought.
- The eight-component view stays conceptual, while the architecture document keeps implementation detail.

## Residual risks that remain real

1. Connector-specific idempotency/read-back quality varies by SAP endpoint, portal, email provider, and customer configuration.
2. Cross-run business-key design must be validated against each customer’s real identifiers and duplicate-invoice semantics.
3. Browser automation remains operationally brittle and should be treated as a higher-cost capability with strong postcondition checks.
4. The Postgres-native orchestrator should be replaced or augmented if replay/versioning/timer/saga complexity becomes a recurring engineering or incident burden.
5. Production assurance still requires sandbox/integration tests and failure injection against actual connectors; local deterministic verification is not a substitute.
