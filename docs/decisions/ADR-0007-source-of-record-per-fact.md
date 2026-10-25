# ADR-0007: Source of record per fact; workflow DB owns automation state only

- Status: Accepted
- Date: 2026-10-25
- Requirements: HC02 · Check: AC9

## Context

The agent reads from SAP, WMS, contract repositories, spreadsheets, portals and email and
caches what it sees. If cached values silently become truth, approvals and verification
can rest on stale or wrong data.

## Decision

Authority is **per fact, not per vendor**: SAP/ERP for PO, invoice, payment block and
postings; WMS for goods receipt; the customer-defined contract source for rates; the
supplier portal for claim status; email as communication evidence only.

PostgreSQL is authoritative only for automation state: run lifecycle, checkpoints,
timers, policy decisions, approvals, evidence references and snapshots, proposed effects,
attempts and receipts, verification results and audit.

Every cached fact carries
`tenant_id, source_system, source_object_type, source_object_id, observed_at,
source_version/etag/hash, payload_hash, evidence_id`.
No cached value silently supersedes the source system.

## Alternatives considered

- **Workflow DB as a synchronized copy of business truth** — rejected: two sources of
  truth, drift, and approvals bound to stale data.

## Consequences

- Revalidation before execution ([ADR-0003](ADR-0003-approval-fingerprint-and-revalidation.md))
  and verification ([ADR-0005](ADR-0005-verified-business-completion.md)) always read the
  source of record.
- Data minimization: keep normalized facts, hashes and provenance; raw artifacts only as needed.
