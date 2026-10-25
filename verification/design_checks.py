#!/usr/bin/env python3
"""Executable model of the architecture's failure semantics.

Stdlib only. A durable SQLite database stands in for the PostgreSQL control plane and
for the external target system. The checks prove the *semantics* the design relies on
(restart, ambiguous effects, stale approvals, verified completion, policy gate, duplicate
delivery) and that the architecture documents contain the required controls. They do not
test real connectors.

Usage:
    python verification/design_checks.py            # print results, exit 1 on failure
    python verification/design_checks.py --json out.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "docs" / "architecture.md"
WALKTHROUGH = ROOT / "docs" / "walkthrough.md"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE runs(
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 0,
  postcondition_verified INTEGER NOT NULL DEFAULT 0,
  next_wake_at TEXT
);
CREATE TABLE steps(
  run_id TEXT NOT NULL,
  step_key TEXT NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY(run_id, step_key)
);
CREATE TABLE effects(
  effect_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  business_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0
);
-- Stand-in for the external system of record (SAP, portal, mailbox).
CREATE TABLE external_effects(
  business_key TEXT PRIMARY KEY,
  applied_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE approvals(
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  status TEXT NOT NULL
);
CREATE TABLE source_versions(
  object_id TEXT PRIMARY KEY,
  revision TEXT NOT NULL
);
CREATE TABLE policy(
  action TEXT PRIMARY KEY,
  approval_required INTEGER NOT NULL
);
"""


def digest(obj: object) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def open_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


# --- control-plane semantics -------------------------------------------------------


def advance_step(db: sqlite3.Connection, run_id: str, step_key: str) -> bool:
    """Commit a semantic step once; a redelivered step observes durable completion."""
    row = db.execute(
        "SELECT status FROM steps WHERE run_id=? AND step_key=?", (run_id, step_key)
    ).fetchone()
    if row and row["status"] == "DONE":
        return False
    db.execute(
        "INSERT OR REPLACE INTO steps(run_id, step_key, status) VALUES(?, ?, 'DONE')",
        (run_id, step_key),
    )
    db.execute("UPDATE runs SET version = version + 1 WHERE id=?", (run_id,))
    db.commit()
    return True


def record_intent(db: sqlite3.Connection, effect_id: str, run_id: str, key: str) -> None:
    """Persist the semantic effect before any call to the target."""
    db.execute(
        "INSERT OR IGNORE INTO effects(effect_id, run_id, business_key, status) "
        "VALUES(?, ?, ?, 'PENDING')",
        (effect_id, run_id, key),
    )
    db.execute(
        "UPDATE effects SET attempts = attempts + 1, status='IN_FLIGHT' WHERE effect_id=?",
        (effect_id,),
    )
    db.commit()


def call_target_then_lose_response(db: sqlite3.Connection, effect_id: str, key: str) -> None:
    """The target applies the effect, but the caller only sees a timeout."""
    db.execute(
        "INSERT OR IGNORE INTO external_effects(business_key, applied_count) VALUES(?, 0)",
        (key,),
    )
    db.execute(
        "UPDATE external_effects SET applied_count = applied_count + 1 WHERE business_key=?",
        (key,),
    )
    db.execute(
        "UPDATE effects SET status='UNKNOWN_EFFECT_STATE' WHERE effect_id=?", (effect_id,)
    )
    db.commit()


def time_out_before_target(db: sqlite3.Connection, effect_id: str) -> None:
    """The request never reached the target, but the caller cannot know that."""
    db.execute(
        "UPDATE effects SET status='UNKNOWN_EFFECT_STATE' WHERE effect_id=?", (effect_id,)
    )
    db.commit()


def reconcile(db: sqlite3.Connection, effect_id: str, *, target_readable: bool = True) -> str:
    """Resolve an ambiguous effect by reading the target, never by blind retry."""
    effect = db.execute("SELECT * FROM effects WHERE effect_id=?", (effect_id,)).fetchone()
    if effect["status"] == "CONFIRMED_APPLIED":
        return "CONFIRMED_APPLIED"
    if not target_readable:
        status = "NEEDS_RECONCILIATION"
    else:
        target = db.execute(
            "SELECT applied_count FROM external_effects WHERE business_key=?",
            (effect["business_key"],),
        ).fetchone()
        applied = bool(target and target["applied_count"] >= 1)
        status = "CONFIRMED_APPLIED" if applied else "CONFIRMED_NOT_APPLIED"
    db.execute("UPDATE effects SET status=? WHERE effect_id=?", (status, effect_id))
    db.commit()
    return status


def applied_count(db: sqlite3.Connection, key: str) -> int:
    row = db.execute(
        "SELECT applied_count FROM external_effects WHERE business_key=?", (key,)
    ).fetchone()
    return row["applied_count"] if row else 0


def approval_fingerprint(
    action: str, params: dict, source_revisions: dict, policy_version: str
) -> str:
    return digest(
        {
            "action": action,
            "params": params,
            "source_revisions": source_revisions,
            "policy_version": policy_version,
        }
    )


def approval_still_valid(
    db: sqlite3.Connection,
    approval_id: str,
    action: str,
    params: dict,
    object_ids: list[str],
    policy_version: str,
) -> bool:
    """Re-read current source revisions and compare with what was approved."""
    approval = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    current = {
        oid: db.execute(
            "SELECT revision FROM source_versions WHERE object_id=?", (oid,)
        ).fetchone()["revision"]
        for oid in object_ids
    }
    expected = approval_fingerprint(action, params, current, policy_version)
    return approval["status"] == "APPROVED" and approval["fingerprint"] == expected


def policy_allows(db: sqlite3.Connection, action: str, approved: bool) -> bool:
    rule = db.execute("SELECT approval_required FROM policy WHERE action=?", (action,)).fetchone()
    if rule is None:
        return False  # unknown capability: deny by default
    return (not rule["approval_required"]) or approved


def complete_run(db: sqlite3.Connection, run_id: str) -> bool:
    run = db.execute("SELECT postcondition_verified FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run["postcondition_verified"]:
        return False
    db.execute(
        "UPDATE runs SET state='COMPLETED', version = version + 1 WHERE id=?", (run_id,)
    )
    db.commit()
    return True


# --- checks ------------------------------------------------------------------------


def contains_all(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return all(n.lower() in lowered for n in needles)


def semantic_checks(workdir: Path) -> dict[str, dict]:
    results: dict[str, dict] = {}
    path = workdir / "state.db"
    db = open_db(path)
    db.executescript(SCHEMA)
    db.execute("INSERT INTO runs(id, state) VALUES('r1', 'INVESTIGATING')")
    db.commit()

    # AC1: restart resumes from the last committed transition without repeating work.
    first = advance_step(db, "r1", "collect_invoice")
    db.close()
    db = open_db(path)  # simulated process restart
    second = advance_step(db, "r1", "collect_invoice")
    version = db.execute("SELECT version FROM runs WHERE id='r1'").fetchone()["version"]
    results["AC1"] = {
        "pass": first and not second and version == 1,
        "first_execution": first,
        "re_executed_after_restart": second,
        "run_version": version,
    }

    # AC2: timeout after a real side effect is reconciled, not retried.
    key = "tenant:invoice-123:request-credit:v1"
    record_intent(db, "fx1", "r1", key)
    call_target_then_lose_response(db, "fx1", key)
    before = applied_count(db, key)
    status = reconcile(db, "fx1")
    after = applied_count(db, key)
    results["AC2"] = {
        "pass": (before, after, status) == (1, 1, "CONFIRMED_APPLIED"),
        "target_effects_before_reconcile": before,
        "target_effects_after_reconcile": after,
        "reconciled_status": status,
    }

    # AC3: proven absence allows retry; an unreadable target goes to a human.
    record_intent(db, "fx2", "r1", "tenant:invoice-456:request-credit:v1")
    time_out_before_target(db, "fx2")
    absent = reconcile(db, "fx2")
    record_intent(db, "fx3", "r1", "tenant:invoice-789:request-credit:v1")
    time_out_before_target(db, "fx3")
    unreadable = reconcile(db, "fx3", target_readable=False)
    results["AC3"] = {
        "pass": absent == "CONFIRMED_NOT_APPLIED" and unreadable == "NEEDS_RECONCILIATION",
        "absent_effect": absent,
        "unreadable_target": unreadable,
    }

    # AC4: an approval bound to stale source revisions cannot authorize execution.
    db.execute("INSERT INTO source_versions(object_id, revision) VALUES('po42', 'v1')")
    params = {"amount": 1000}
    fingerprint = approval_fingerprint("POST_CREDIT", params, {"po42": "v1"}, "policy-v7")
    db.execute(
        "INSERT INTO approvals(id, run_id, fingerprint, status) VALUES('a1', 'r1', ?, 'APPROVED')",
        (fingerprint,),
    )
    db.commit()
    valid_before = approval_still_valid(db, "a1", "POST_CREDIT", params, ["po42"], "policy-v7")
    db.execute("UPDATE source_versions SET revision='v2' WHERE object_id='po42'")
    db.commit()
    valid_after = approval_still_valid(db, "a1", "POST_CREDIT", params, ["po42"], "policy-v7")
    results["AC4"] = {
        "pass": valid_before and not valid_after,
        "valid_before_source_change": valid_before,
        "valid_after_source_change": valid_after,
    }

    # AC5: COMPLETED is unreachable before the business postcondition is verified.
    db.execute("INSERT INTO runs(id, state) VALUES('r2', 'VERIFYING')")
    db.commit()
    premature = complete_run(db, "r2")
    db.execute("UPDATE runs SET postcondition_verified=1 WHERE id='r2'")
    db.commit()
    verified = complete_run(db, "r2")
    state = db.execute("SELECT state FROM runs WHERE id='r2'").fetchone()["state"]
    results["AC5"] = {
        "pass": not premature and verified and state == "COMPLETED",
        "premature_completion_allowed": premature,
        "completed_after_verification": verified,
        "terminal_state": state,
    }

    # AC6: the policy gate blocks a consequential effect without approval.
    db.execute("INSERT INTO policy(action, approval_required) VALUES('POST_FINANCIAL_CORRECTION', 1)")
    db.commit()
    blocked = not policy_allows(db, "POST_FINANCIAL_CORRECTION", approved=False)
    allowed = policy_allows(db, "POST_FINANCIAL_CORRECTION", approved=True)
    unknown_denied = not policy_allows(db, "UNREGISTERED_ACTION", approved=True)
    results["AC6"] = {
        "pass": blocked and allowed and unknown_denied,
        "blocked_without_approval": blocked,
        "allowed_with_approval": allowed,
        "unknown_capability_denied": unknown_denied,
    }

    # AC7: a duplicate delivery of the same effect does not touch the target again.
    redelivered = reconcile(db, "fx1")
    count = applied_count(db, key)
    results["AC7"] = {
        "pass": redelivered == "CONFIRMED_APPLIED" and count == 1,
        "redelivery_resolution": redelivered,
        "target_effect_count": count,
    }
    db.close()
    return results


def document_checks() -> dict[str, dict]:
    results: dict[str, dict] = {}
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    walkthrough = WALKTHROUGH.read_text(encoding="utf-8")

    # AC8: required enterprise security controls are designed in.
    controls = {
        "tenant isolation": ["tenant isolation"],
        "scoped credentials": ["scoped credentials", "tenant-scoped credentials"],
        "separation of duties": ["separation of duties"],
        "tamper-evident audit": ["tamper evidence", "tamper-evident"],
        "prompt-injection / tool boundary": ["prompt-injection", "typed tool", "tool boundary"],
        "retention / data minimization": ["retention", "data minimization"],
    }
    found = {
        name: any(v.lower() in architecture.lower() for v in variants)
        for name, variants in controls.items()
    }
    results["AC8"] = {"pass": all(found.values()), "controls_found": found}

    # AC9: evidence keeps provenance and source authority is separated from cache.
    provenance = [
        "source_system",
        "source_object_id",
        "observed_at",
        "source_version/etag/hash",
        "payload_hash",
        "evidence_id",
    ]
    authority = [
        "Business systems of record",
        "Workflow database",
        "No cached value silently supersedes the source system",
    ]
    results["AC9"] = {
        "pass": contains_all(architecture, provenance + authority),
        "provenance_fields": {t: t.lower() in architecture.lower() for t in provenance},
        "authority_boundary": contains_all(architecture, authority),
    }

    # AC10: walkthrough shows the eight components, one AP path and the trade-offs.
    diagram = ""
    if "```mermaid" in walkthrough:
        diagram = walkthrough.split("```mermaid", 1)[1].split("```", 1)[0]
    components = [
        "Intake / Case API",
        "Durable Control Plane",
        "Investigation Agent",
        "Evidence + Connectors",
        "Policy + Approval",
        "Effect Executor",
        "Verification / Reconciliation",
        "Operator UI + Audit",
    ]
    components_ok = all(c in diagram for c in components)
    ap_path_ok = contains_all(
        walkthrough,
        ["AP supplier-invoice mismatch", "invoice", "PO", "goods receipt", "contract", "approval", "reconcile"],
    )
    tradeoffs_ok = contains_all(walkthrough, ["exactly-once", "Why not Temporal", "policy", "human"])
    results["AC10"] = {
        "pass": components_ok and ap_path_ok and tradeoffs_ok,
        "eight_components": components_ok,
        "ap_path": ap_path_ok,
        "tradeoffs": tradeoffs_ok,
    }
    return results


def run_checks() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        results = semantic_checks(Path(tmp))
    results.update(document_checks())
    ordered = dict(sorted(results.items(), key=lambda item: int(item[0][2:])))
    return {
        "status": "PASS" if all(r["pass"] for r in ordered.values()) else "FAIL",
        "checks": ordered,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="also write the result to this file")
    args = parser.parse_args()
    report = run_checks()
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    for check_id, result in report["checks"].items():
        print(f"{check_id:>5}  {'PASS' if result['pass'] else 'FAIL'}")
    print(f"\n{report['status']}")
    if report["status"] != "PASS":
        print(text, file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
