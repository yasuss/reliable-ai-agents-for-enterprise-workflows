# References

Primary sources behind load-bearing decisions. Each entry states what it supports and
where it is used. Retrieved 2026-10-25.

| # | Source | What it supports | Used in |
| --- | --- | --- | --- |
| R1 | [Google Cloud — Understand Cloud Tasks](https://docs.cloud.google.com/tasks/docs/dual-overview) | Delivery is at-least-once; duplicate execution can occur, handlers must be idempotent. | ADR-0002, ADR-0006 |
| R2 | [Google Cloud — Cloud Tasks quotas and limits](https://docs.cloud.google.com/tasks/docs/quotas) | Task-name dedup window ≤ 24 h, max schedule time 30 days, 31-day retention — Cloud Tasks cannot be the timer or dedup ledger for multi-week cases. | ADR-0006 |
| R3 | [Google Cloud — Cloud Run request timeout](https://docs.cloud.google.com/run/docs/configuring/request-timeout) | Max request timeout 60 minutes — multi-day waits cannot live in a request worker. | ADR-0006 |
| R4 | [PostgreSQL — SELECT … SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html) | Suitable for multiple consumers of queue-like tables — lease/claim of due work. | ADR-0006, architecture §6 |
| R5 | [Google Cloud — Cloud SQL high availability](https://docs.cloud.google.com/sql/docs/postgres/high-availability) | Synchronous cross-zone replication; failover closes connections — transactions and leases must tolerate failover. | architecture §6, §14 |
| R6 | [SAP Help — ETag handling](https://help.sap.com/docs/PRODUCT_ID/03c04db2a7434731b7fe21dca77440da/c09676370b0146ba976081e3da23a692.html?locale=en-US&state=PRODUCTION&version=LATEST) | `If-Match` optimistic concurrency rejects updates to changed entities. | ADR-0003 |
| R7 | [SAP Help — Settings for idempotent services](https://help.sap.com/saphelp_em92/helpdata/en/09/f82651c294256ee10000000a445394/content.htm) | Side-effecting HTTP retries are ambiguous; RequestID / RepeatabilityCreation for configured repeatable requests. | ADR-0002 |
| R8 | [Temporal — Durable AI](https://docs.temporal.io/ai) | Durable execution for long-running agents with multi-day human approvals — the strongest alternative. | ADR-0001, alternatives |
| R9 | [OWASP — LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) | Excessive functionality, permissions and autonomy as agent risks; least privilege and human approval for high-impact actions. | ADR-0004, architecture §15 |
| R10 | [NIST NCCoE — Software and AI agent identity and authorization (concept paper, 2026)](https://www.nccoe.nist.gov/sites/default/files/2026-02/accelerating-the-adoption-of-software-and-ai-agent-identity-and-authorization-concept-paper.pdf) | Least privilege, delegation of authority, binding agent and human identities for HITL, tamper-proof audit. | ADR-0003, architecture §15 |

Other durable-execution families reviewed for the alternatives analysis: DBOS, Restate,
Microsoft Durable Task, Conductor/Orkes, Trigger.dev, Cloudflare Workflows. They confirm
the same control principle — persist orchestration state, isolate non-deterministic model
and tool work, make human pause/resume durable — without giving a requirement-level reason
to add a new runtime before the first vertical slice.
