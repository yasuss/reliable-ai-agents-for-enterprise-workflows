# ADR-0004: Deterministic policy outside the LLM

- Status: Accepted
- Date: 2026-10-25
- Requirements: HC03, HC09, HC10 · Check: AC6

## Context

The investigation benefits from model flexibility: which source to read next, which
hypothesis to test. Authority does not: whether an action is allowed, who must approve,
retry semantics and terminal completion must be predictable and auditable. Supplier
emails, PDFs and portal text are untrusted and may contain prompt injection.

## Decision

- **Inside `INVESTIGATING`** the LLM may choose allowed read-only capabilities, extract and
  compare records, form hypotheses, ask for missing evidence, replan after read failures
  and propose a resolution.
- The agent exits with a **typed `ProposedResolution`** (validated with Zod), never an
  imperative command.
- A **deterministic policy engine** evaluates it and returns
  `AUTO_AUTHORIZE | REQUIRE_HUMAN_APPROVAL | NEED_MORE_EVIDENCE | DENY`, using capability
  risk class, amount, evidence completeness, customer rules, source freshness, reviewer
  requirements and reversibility. Confidence is used only where policy explicitly says so.
- The LLM never owns capability authorization, approval requirements, reviewer authority,
  retry semantics of consequential effects, completion, tenant or credential scope, audit
  retention or budget/deadline invariants.

## Alternatives considered

- **Model decides when approval is needed** — rejected: authority becomes probabilistic
  and manipulable (OWASP LLM06 "excessive agency").
- **Fully deterministic workflow without an agent** — rejected: cannot handle varied
  evidence across ERPs, documents and portals without hand-coding every path.

## Consequences

- Higher automation comes from explicit pre-authorized low-risk policy tiers, not from
  loosening the boundary.
- Model output is untrusted until schema and policy validation; external content cannot
  redefine tools or policy.
