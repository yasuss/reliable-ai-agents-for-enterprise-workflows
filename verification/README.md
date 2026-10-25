# Design checks

`design_checks.py` is an executable model of the architecture's failure semantics.
It uses only the Python standard library; a durable SQLite file stands in for the
PostgreSQL control plane and for the external system of record.

```bash
python verification/design_checks.py
python verification/design_checks.py --json result.json   # machine-readable output
```

CI runs it on every push and pull request
([workflow](../.github/workflows/design-checks.yml)).

## What is checked

| ID | Check | Kind |
| --- | --- | --- |
| AC1 | A run resumes after a simulated restart without repeating a committed step. | Semantic |
| AC2 | A write that committed on the target but timed out is reconciled to `CONFIRMED_APPLIED`; the target sees exactly one effect. | Semantic |
| AC3 | A provably absent effect reconciles to `CONFIRMED_NOT_APPLIED` (retry allowed); an unreadable target goes to `NEEDS_RECONCILIATION`. | Semantic |
| AC4 | An approval fingerprint bound to source revision `v1` is rejected after the PO moves to `v2`. | Semantic |
| AC5 | `COMPLETED` is rejected until the postcondition is verified. | Semantic |
| AC6 | The policy gate blocks an unapproved financial correction and denies unknown capabilities. | Semantic |
| AC7 | A duplicate delivery of the same effect resolves from the ledger without touching the target. | Semantic |
| AC8 | The architecture contains tenant isolation, scoped credentials, separation of duties, tamper-evident audit, prompt-injection/tool-boundary and retention controls. | Document |
| AC9 | Evidence provenance fields and the source-of-record boundary are specified. | Document |
| AC10 | The walkthrough contains the eight-component view, an AP path and the trade-offs. | Document |

Acceptance criteria and their traceability to requirements and decisions:
[docs/requirements.md](../docs/requirements.md).

## What is not checked

The model proves semantics, not connectors. SAP endpoints, supplier portals, email
providers and browser automation need connector contract tests, sandbox integration
tests and production-like failure injection during implementation
([open questions](../docs/open-questions.md)).
