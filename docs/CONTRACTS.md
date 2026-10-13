# ParcelVerify — Interface Contracts

## Current handoff amendments — 13 October 2026

The following accepted changes supersede older conflicting text below. Live access and evidence writes check server-time permissions before returning existing idempotent records; claimed historical event time cannot bypass live access. `evaluate_handoff` accepts optional trusted `actor_context` for the UI path and `compare_handoff` accepts an optional selected `event_id`. Missing authorization, GPS and measurements stay unknown. Repackaging requires linked baseline/actual weight measurements.

`services.workflow.submit_handoff` owns submit → upload → scoped evaluation → case upsert → pending evidence-task creation. Source events survive downstream failures for retry. UI state only selects the workspace; business records persist in its own database. Each service continues to receive explicit `db_path`.

`investigation_runs` persists run status/diagnostics before final reports exist. Report versions and tool executions carry `run_id`. Real model selection uses bounded read-only tools and a distinct schema-constrained report request; failures have no report fallback. Gemini Developer API is the selected hosted provider, model configurable, secret name `GEMINI_API_KEY`; Ollama/compatible providers remain options. Real attempts are serialized per process and limited to three per workspace per hour.

The supported deployment demonstration uses isolated synthetic token-addressed workspaces with 24-hour inactivity expiry. Community Cloud local storage is intentionally disposable. Production identity, durable host rebuild storage and independent approval-role revocation are outside the prototype.

**Version:** 1.1 (revised 2026-10-12 — 8 contract fixes)  
**Owner:** Main Agent  
**Rule:** Any change requires Main Agent approval. Updated CONTRACTS must propagate to all sub-agents before code changes.

## 0. Database Injection Convention (D-017)

All service functions accept `db_path: str` as the **first parameter** (default `"data/parcelverify.db"`). This applies to every function in every module. The `DBConfig` dataclass in `contracts.py` centralizes defaults and provides test utilities:

```python
@dataclass
class DBConfig:
    default_path: str = "data/parcelverify.db"

    @staticmethod
    def temp_db() -> tuple[str, str]:
        """Create a temp directory and return (dir_path, db_path). Tests MUST use this."""
        import tempfile, os
        d = tempfile.mkdtemp(prefix="pvtest_")
        return (d, os.path.join(d, "test.db"))
```

**Rules:**
- Tests must use `DBConfig.temp_db()`, then `init_db(temp_path)` and `seed_demo(temp_path)`
- Tests must NEVER write to `"data/parcelverify.db"`
- The demo database is only written by `seed.py` and application runtime
- `contracts.py` (owned by Main Agent) defines `DBConfig`, all Pydantic schemas, enums, and shared types

## 1. Database Layer (Role A → all callers)

### `init_db(db_path: str = "data/parcelverify.db") -> None`
- Creates all tables (see schema.sql) if not exist; never drops data
- Idempotent: safe to call multiple times

### `get_connection(db_path: str = "data/parcelverify.db") -> sqlite3.Connection`
- Always sets `PRAGMA foreign_keys = ON`
- Caller responsible for closing (use context manager)
- Used as transaction handle for audit + business writes

### `seed_demo(db_path: str = "data/parcelverify.db", seed: int = 42, reset: bool = False) -> dict`
- `reset=False`: inserts if not present, skips existing
- `reset=True`: drops and recreates all tables, then seeds
- Returns `{"partners": int, "shipments": int, "events": int, "photos": int, "access_logs": int, "contract_history": int}`

### `submit_event(db_path, actor_context, shipment_id, event_type, payload, source, occurred_at) -> dict` (D-016, Role A)
- Authorization: actor must have a valid assignment for the shipment at `occurred_at`
- Idempotent: same `(shipment_id, event_type, occurred_at, source)` returns existing event
- Server assigns `event_id`, `received_at` (current UTC)
```python
{
    "event_id": str,
    "shipment_id": str,
    "event_type": str,
    "occurred_at": str,
    "received_at": str,        # server-assigned
    "source": str,
    "is_new": bool,            # False if duplicate
}
```

### `upload_photo(db_path, actor_context, event_id, file_bytes, claimed_capture_at=None, capture_method="upload", manual_observation="") -> dict` (D-016, Role A)
- Authorization: actor must be authorized for the event's shipment
- Computes SHA-256 from raw bytes, pHash via Pillow+ImageHash
- Idempotent: same SHA-256 for same event_id returns existing photo_id
- Validates: JPEG/PNG, ≤10MB, ≤20MP; generates internal random filename
```python
{
    "photo_id": str,
    "sha256": str,
    "phash": str | None,
    "local_path": str,
    "is_new": bool,
}
```

## 2. Access Service (Role B)

### `query_shipment(db_path, actor_context, shipment_id, at_time=None) -> dict`
- Checks authorization using `contract_history` for time-accurate scope (D-019)
- Logs access attempt regardless of outcome
```python
{
    "authorized": bool,
    "denied_reason": str | None,
    "fields": dict | None,       # shipment data if authorized; masked/sensitive fields stripped
    "log_id": str,
}
```

### `check_access_scope(db_path, case_id, actor_context) -> dict`
```python
{
    "case_id": str,
    "access_logs": [{"log_id": str, "actor_id": str, "shipment_id": str, "action": str, "outcome": str, "occurred_at": str}],
    "violations": [{"type": str, "detail": str, "evidence_ids": list[str]}],
    "authorized": bool,
}
```

## 3. Handoff Service (Role B)

### `evaluate_handoff(db_path, shipment_id, event_id) -> dict`
```python
{
    "shipment_id": str,
    "event_id": str,
    "result": "consistent" | "needs_review" | "insufficient_evidence",
    "findings": [
        {"category": str, "description": str, "severity": str, "evidence_ids": list[str]}
    ],
    "missing_evidence": [str],
    "evidence_refs": list[str],
    "blocking_issues": list[str],   # contradictions that block handoff acceptance
}
```

### `compare_handoff(db_path, shipment_id) -> dict`
```python
{
    "shipment_id": str,
    "count": {"expected": int | None, "actual": int | None, "match": bool | None},
    "weight_g": {"expected": float | None, "actual": float | None, "diff": float | None, "match": bool | None},
    "seal": {"expected": str | None, "actual": str | None, "match": bool | None},
    "recipient": {"expected": str | None, "actual": str | None, "authorized": bool | None},
    "unknowns": list[str],
}
```

### `create_or_update_case(db_path, shipment_id, triggering_event_id, findings, rule_version) -> dict` (D-016, Role B)
- Idempotent key: `(shipment_id, triggering_event_id)`
- If case exists for this key: updates `findings_json`, `rule_version`, keeps `case_id`
- If not: creates new case with `status='pending_review'` when `review_queue` is True
- Streamlit refresh does NOT create duplicate cases
```python
{
    "case_id": str,
    "status": str,             # "pending_review" if review_queue, else "review_completed" if no findings
    "is_new": bool,
    "priority_score": int,
    "review_queue": bool,
}
```

## 4. Photo Service (Role B)

### `inspect_photo(db_path, photo_id, actor_context) -> dict` (D-014)
- Authorization enforced: only reveals metadata the actor is authorized to see
- `actor_context` always server-provided (from session)
```python
{
    "photo_id": str,
    "sha256": str,
    "phash": str | None,
    "exact_matches": [{"photo_id": str, "event_id": str, "shipment_id": str}],  # authorized fields only
    "similar_candidates": [{"photo_id": str, "event_id": str, "shipment_id": str, "hamming_distance": int}],
    "evidence_ids": list[str],
}
```

### `find_photo_reuse(db_path, photo_id, actor_context) -> dict` (D-014)
- **actor_context is required** — always server-provided, never model-specified
- Cross-shipment search; unauthorized fields are masked
- Same return structure as `inspect_photo`
- Authorization enforced in: UI calls, Agent tool dispatch, export/report generation

## 5. Risk Service (Role B)

### `calculate_priority(db_path, findings) -> dict` (D-013)
```python
{
    "total_score": int,           # capped at 100
    "items": [{"category": str, "score": int, "deduplicated": bool}],
    "review_queue": bool,         # (total_score >= 30) OR (len(blocking_issues) > 0)
    "priority": bool,             # total_score >= 60
    "blocking_issues": list[str],
}
```

Scoring map:
| Category | Score | Dedup Key |
|---|---|---|
| seal_mismatch / id_conflict | 25 | one category, max 25 |
| weight_diff | 20 | per case |
| photo_reuse (SHA or pHash) | 25 | one category, max 25 |
| location_conflict | 10 | per case |
| time_conflict | 10 | per case |
| access_anomaly | 10 | per case |

### `get_partner_metrics(db_path, partner_id) -> dict` (D-018)
```python
{
    "partner_id": str,
    "total_shipments": int,
    "anomaly_count": int,
    "anomaly_rate_per_1000": float,
    "evidence_completeness_rate": float,
    "open_cases": int,
    "sample_size": int,
    "meets_display_threshold": bool,  # >= 20 shipments — display only, NOT statistical reliability
}
```

## 6. Agent Layer (Role C)

### `investigate_case(db_path, case_id, actor_context) -> dict`
- `actor_context` from session; model cannot specify identity (D-014)
```python
{
    "case_id": str,
    "status": "completed" | "timeout" | "error" | "ai_not_running",
    "tool_calls": [{"tool": str, "params": dict, "result_summary": str, "evidence_ids": list[str], "duration_ms": int}],
    "report": {
        "case_id": str,
        "verdict": "consistent" | "needs_review" | "insufficient_evidence",
        "summary": str,
        "facts": [{"text": str, "evidence_ids": list[str]}],
        "alternative_explanations": list[str],
        "missing_evidence": list[str],
        "recommended_action": str,
        "requires_approval": bool,
        "limitations": str,
    } | None,
    "model_name": str | None,
    "rule_version": str,
    "report_version": int | None,
    "total_duration_ms": int,
}
```

### Tool Whitelist
| Tool | Params | Returns |
|---|---|---|
| `get_vendor_context(partner_id)` | `{"partner_id": str}` | contract (from contract_history if at_time), scope, qualifications, evidence_ids |
| `get_shipment_timeline(shipment_id)` | `{"shipment_id": str}` | ordered events with sources |
| `compare_handoff(shipment_id)` | `{"shipment_id": str}` | count/weight/seal/recipient diffs |
| `find_photo_reuse(photo_id)` | `{"photo_id": str}` | exact + similar matches (actor_context from session) |
| `check_access_scope(case_id)` | `{"case_id": str}` | access logs vs permissions |
| `get_context_events(case_id)` | `{"case_id": str}` | calibration, repackaging_approved, weather, etc. |
| `get_partner_metrics(partner_id)` | `{"partner_id": str}` | normalized metrics + sample size |

**Constraints:**
- Max 4 tool rounds
- Total budget: 120s (configurable)
- All tool params validated: case scope, actor permissions
- `actor_context` always from session, never from model
- Evidence IDs must exist in retrieved results
- No SQL, file paths, commands, URLs, or approval actions from model

## 7. Actions Service (Role D)

### `propose_action(db_path, case_id, action_type, actor_context, **kwargs) -> dict`
```python
{"action_id": str, "status": "proposed"}
```

### `review_action(db_path, action_id, decision, actor_context, reason="") -> dict`
- `decision`: `"approve"` | `"reject"`
- Validates: approver has authority; action is in `proposed` status
- `rejected` is **terminal** — cannot transition to `executed` or back to `approved` (D-019)
```python
{"action_id": str, "status": "approved" | "rejected", "approved_by": str, "approved_at": str}
```

### `execute_action(db_path, action_id, actor_context) -> dict` (D-019)
**Pre-execution checks (in order):**
1. Action status must be `approved` (not `rejected`, `proposed`, or already `executed`)
2. Action must not be expired (`expires_at` is null or in the future)
3. Approver must still have authority at execution time
4. Case must still be in a state that allows this action
5. Idempotency: if status is already `executed`, return `already_executed`

**Transactional:** business state change + audit record in the same SQLite transaction. On failure: rollback, status=`failed`, no partial state.
```python
{
    "action_id": str,
    "status": "executed" | "failed" | "already_executed" | "not_approved" | "expired",
    "before": dict | None,
    "after": dict | None,
    "error": str | None,
}
```

### `create_evidence_task(db_path, case_id, task_type, actor_context, description) -> dict` (D-016, Role D)
- Idempotent: one open task per `(case_id, task_type)` — duplicate returns existing
- `task_type`: `"reweigh"` | `"rephoto"` | `"rescan"` | `"supplementary_statement"`
```python
{"task_id": str, "case_id": str, "task_type": str, "status": "open", "is_new": bool}
```

## 8. Audit Service (Role D) (D-015)

### `append_audit(db_path, actor_id, case_id, operation, details, tx=None) -> bool`
- If `tx` (a `sqlite3.Connection`) is provided: writes within that transaction
  - If the audit write fails, the transaction rolls back — the business state change does NOT persist
  - Returns `True` on success
- If no `tx`: opens its own connection, raises `AuditError` on failure
- Business state changes and their corresponding audit records are written in the same transaction
- Audit failure = operation failure; UI must NOT show "success" if audit failed

### `export_audit(db_path, case_id=None, actor_context=None) -> dict`
- `case_id=None`: export all (requires admin actor_context); otherwise filter to authorized cases
- Returns `{"events": [...], "format": "json"}`
- Authorization enforced on case_id — cannot export audit for unauthorized cases

## 9. Action State Machine (D-019)

```
proposed ──approve──→ approved ──execute──→ executed
proposed ──reject───→ rejected (TERMINAL)
approved ──execute──→ failed ──retry/execute──→ executed
```

**Terminal states:** `rejected`, `executed`  
**Non-terminal (retryable):** `failed`  
**Forbidden transitions:**
- `rejected → executed` (rejected is terminal)
- `rejected → approved` (cannot revive)
- `executed → anything` (already done)
- `proposed → executed` (must be approved first)

## 10. Contract History (D-019)

### `get_contract_at_time(db_path, partner_id, at_time) -> dict`
- Returns the contract snapshot that was active at `at_time`
- Uses `contract_history` table: finds row where `effective_from <= at_time < effective_until` (or `effective_until IS NULL`)
- Authorization checks for past events use this function, not current partner record
```python
{
    "partner_id": str,
    "contract_snapshot": dict,    # {name, status, contract_end, service_area, approved_scope, ...}
    "effective_from": str,
    "effective_until": str | None,
    "source": "contract_history",
}
```
- Role: B (services/access.py) owns the query; Role A (db.py) owns the table schema
