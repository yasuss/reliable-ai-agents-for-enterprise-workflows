# ADR-0006: Persisted timers and a transactional outbox; queues are wake-up hints

- Status: Accepted
- Date: 2026-10-25
- Requirements: HC05 · Checks: AC1, AC7

## Context

Cloud Tasks delivers at least once, deduplicates task names for at most 24 hours and
schedules at most 30 days ahead. Cloud Run requests time out after 60 minutes. Cases can
wait longer than all of these. Publishing to a queue after a DB commit can fail
independently of the commit.

## Decision

- Every state transition writes an **outbox row in the same transaction**. A publisher
  sends committed rows to Cloud Tasks and retries until acknowledged. Duplicate dispatch
  is harmless because workers check durable step/effect state before acting.
- Timers are rows: `next_wake_at`, `deadline_at`, `timer_kind`, `run_id`. A periodic
  scanner (Cloud Scheduler) claims due rows with `FOR UPDATE SKIP LOCKED` and dispatches
  short-lived work.
- Runnable units carry leases (`status, lease_owner, lease_until, attempt_no`); a dead
  worker's lease expires and another worker continues.

The queue message is a **wake-up hint, not the source of truth**.

## Alternatives considered

- **Cloud Tasks scheduled weeks ahead** — rejected: 30-day limit, 24-hour dedup window.
- **Kafka / Pub/Sub as canonical state** — rejected: the problem is transactional state
  and queries, not stream throughput.
- **Long-running worker per run** — rejected: Cloud Run limits; parked runs would consume
  compute.

## Consequences

- Parked runs cost storage, not worker slots; the population of waiting runs can be large.
- `next_wake_at` must be indexed; scanner throughput is a scaling lever.
