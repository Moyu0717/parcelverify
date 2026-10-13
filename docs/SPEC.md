# ParcelVerify — Technical Specification

**Version:** 1.1 (revised 2026-10-12 — 8 contract fixes)  
**Status:** Phase 0 — interfaces frozen, ready for development

## 1. Product Summary

ParcelVerify is an outsourced partner risk monitoring and investigation system for logistics companies. It links data access monitoring (Gate 1) with transport evidence verification (Gate 2), uses a single local investigation agent with read-only tools, and requires human approval for any business action.

## 2. Tech Stack (Fixed)

| Component | Technology | Version Constraint |
|---|---|---|
| Language | Python | 3.11 |
| UI | Streamlit | latest stable |
| Database | SQLite (sqlite3 stdlib) | built-in |
| AI | Ollama + Qwen3:4b | local only, no paid API |
| Image | Pillow + ImageHash | latest stable |
| Validation | Pydantic | v2 |
| Testing | pytest | latest stable |

## 3. Data Model

### 3.1 Tables (schema.sql)

All times stored as UTC ISO 8601 strings. UI converts to Asia/Kuala_Lumpur for display. Weight unit: grams (g). Every connection executes `PRAGMA foreign_keys = ON`.

**Partners**
- `partner_id` TEXT PK, `name` TEXT, `status` TEXT, `contract_end` TEXT, `service_area` TEXT, `approved_scope` TEXT, `vendor_evidence_id` TEXT

**Shipments**
- `shipment_id` TEXT PK, `partner_id` TEXT FK→partners, `expected_count` INT, `expected_weight_g` REAL, `expected_seal` TEXT, `destination_lat` REAL, `destination_lon` REAL, `status` TEXT, `reference_event_id` TEXT

**Assignments**
- `assignment_id` TEXT PK, `shipment_id` TEXT FK→shipments, `partner_id` TEXT FK→partners, `actor_id` TEXT, `valid_from` TEXT, `valid_until` TEXT, `allowed_actions` TEXT (JSON array)

**Events**
- `event_id` TEXT PK, `shipment_id` TEXT FK→shipments, `partner_id` TEXT FK→partners, `actor_id` TEXT, `event_type` TEXT, `occurred_at` TEXT, `received_at` TEXT, `source` TEXT, `payload_json` TEXT, `is_synthetic` INT DEFAULT 1

**Access Logs**
- `log_id` TEXT PK, `partner_id` TEXT FK, `actor_id` TEXT, `credential_id` TEXT, `shipment_id` TEXT, `occurred_at` TEXT, `action` TEXT, `outcome` TEXT, `returned_fields` TEXT, `batch_job_id` TEXT

**Photos**
- `photo_id` TEXT PK, `event_id` TEXT FK→events, `local_path` TEXT, `sha256` TEXT, `phash` TEXT, `uploaded_at` TEXT, `claimed_capture_at` TEXT, `capture_method` TEXT, `manual_observation` TEXT

**Case Records**
- `case_id` TEXT PK, `partner_id` TEXT FK, `shipment_id` TEXT FK, `status` TEXT, `priority_score` INT, `rule_version` TEXT, `findings_json` TEXT, `report_json` TEXT, `created_at` TEXT

**Action Requests**
- `action_id` TEXT PK, `case_id` TEXT FK→case_records, `action_type` TEXT, `target_id` TEXT, `status` TEXT, `requested_by` TEXT, `approved_by` TEXT, `approved_at` TEXT, `executed_at` TEXT, `expires_at` TEXT, `reason` TEXT, `before_json` TEXT, `after_json` TEXT

**Audit Log**
- `audit_id` TEXT PK, `occurred_at` TEXT, `actor_id` TEXT, `case_id` TEXT, `operation` TEXT, `details_json` TEXT

**Report Versions** (added by Main Agent — not in original manual)
- `report_id` TEXT PK, `case_id` TEXT FK→case_records, `version` INT, `report_json` TEXT, `model_name` TEXT, `rule_version` TEXT, `created_at` TEXT, `status` TEXT

**Tool Executions** (added by Main Agent)
- `tool_exec_id` TEXT PK, `case_id` TEXT FK, `report_id` TEXT FK, `tool_name` TEXT, `parameters_json` TEXT, `result_summary` TEXT, `evidence_ids_json` TEXT, `source` TEXT, `duration_ms` INT, `created_at` TEXT

**Contract History** (added by Main Agent — D-019)
- `history_id` TEXT PK, `partner_id` TEXT FK→partners, `contract_snapshot_json` TEXT, `effective_from` TEXT, `effective_until` TEXT, `changed_by` TEXT, `changed_at` TEXT

**Evidence Tasks** (added by Main Agent — D-016)
- `task_id` TEXT PK, `case_id` TEXT FK→case_records, `task_type` TEXT, `description` TEXT, `status` TEXT DEFAULT 'open', `created_by` TEXT, `created_at` TEXT, `closed_at` TEXT, `resolution_json` TEXT
- Unique partial index on `(case_id, task_type)` WHERE `status='open'` — enforces one active task per type per case

### 3.2 Enums (string-based, validated by code)

**Event Types:**
`vendor_document`, `dispatch_confirmed`, `handoff_submitted`, `pod_submitted`, `recipient_authorization`, `message_reported`, `official_notice`, `approved_batch_job`, `scale_calibration`, `route_exception`, `repackaging_approved`

**Case Status:**
`pending_review`, `under_investigation`, `review_completed`, `action_proposed`, `action_approved`, `action_rejected`, `action_executed`, `action_failed`, `closed`

**Report Verdict:**
`consistent`, `needs_review`, `insufficient_evidence`

**Action Status:**
`proposed` → `approved` | `rejected` (terminal) → `executed` | `failed` (retry → `executed`). `rejected` is a terminal state — cannot transition to `executed` or back to `approved`.

**Action Types:**
`request_reweigh`, `request_rephoto`, `request_rescan`, `hold_handoff`, `hold_pod`, `enhance_inspection`, `pause_high_value_assignment`, `restrict_account`, `submit_to_contract_ops`

## 4. Function Signatures (Frozen v1)

```python
# db.py
def init_db(db_path: str = "data/parcelverify.db") -> None:
    """Create/migrate database; does not overwrite existing data."""

def get_connection(db_path: str = "data/parcelverify.db") -> sqlite3.Connection:
    """Return connection with PRAGMA foreign_keys = ON."""

# seed.py
def seed_demo(db_path: str = "data/parcelverify.db", seed: int = 42, reset: bool = False) -> dict:
    """Generate reproducible synthetic data. reset=True drops and recreates tables."""

# --- D-016: Submission chain (Role A: db.py) ---

def submit_event(db_path: str, actor_context: dict, shipment_id: str, event_type: str,
                 payload: dict, source: str, occurred_at: str) -> dict:
    """Create event with server-assigned event_id and received_at.
    Idempotent: same shipment_id + event_type + occurred_at + source returns existing event.
    Authorization: actor must have a valid assignment for the shipment."""

def upload_photo(db_path: str, actor_context: dict, event_id: str, file_bytes: bytes,
                 claimed_capture_at: str | None = None, capture_method: str = "upload",
                 manual_observation: str = "") -> dict:
    """Store photo, compute SHA-256 and pHash.
    Idempotent: same SHA-256 for same event_id returns existing photo_id.
    Authorization: actor must be authorized for the event's shipment."""

# services/access.py
def query_shipment(db_path: str, actor_context: dict, shipment_id: str, at_time: str | None = None) -> dict:
    """Check authorization first; return allowed fields or deny. Logs access.
    Uses contract_history for at_time-accurate authorization."""

def check_access_scope(db_path: str, case_id: str, actor_context: dict) -> dict:
    """Compare access logs against assignments and permissions."""

# services/handoff.py
def evaluate_handoff(db_path: str, shipment_id: str, event_id: str) -> dict:
    """Return rule results, contradictions, missing evidence, evidence IDs."""

def compare_handoff(db_path: str, shipment_id: str) -> dict:
    """Compare count/weight/seal/recipient across handoff events."""

def create_or_update_case(db_path: str, shipment_id: str, triggering_event_id: str,
                          findings: list[dict], rule_version: str) -> dict:
    """Create case if not exists for shipment+triggering event; update findings if exists.
    Idempotent key: (shipment_id, triggering_event_id). Streamlit refresh does NOT duplicate."""

# services/photos.py
def inspect_photo(db_path: str, photo_id: str, actor_context: dict) -> dict:
    """Return same-file / similar candidates and authorized evidence.
    Authorization enforced: only reveals metadata the actor is authorized to see."""

def find_photo_reuse(db_path: str, photo_id: str, actor_context: dict) -> dict:
    """SHA-256 exact match + pHash similar candidates across shipments.
    actor_context is server-provided (from session), never model-specified.
    Cross-shipment matches mask unauthorized fields."""

# services/risk.py
def calculate_priority(db_path: str, findings: list[dict]) -> dict:
    """Return total score and per-item scores; deduplicate by category.
    review_queue = (total_score >= 30) OR (len(blocking_issues) > 0)."""

def get_partner_metrics(db_path: str, partner_id: str) -> dict:
    """Normalized volume, anomaly rate, sample size, open cases.
    Uses meets_display_threshold (not has_reliable_sample)."""

# services/actions.py
def propose_action(db_path: str, case_id: str, action_type: str, actor_context: dict, **kwargs) -> dict:
    """Create a pending approval request. Does not execute."""

def review_action(db_path: str, action_id: str, decision: str, actor_context: dict, reason: str = "") -> dict:
    """Validate approval authority; record decision.
    rejected is terminal — cannot be revived."""

def execute_action(db_path: str, action_id: str, actor_context: dict) -> dict:
    """Pre-checks: status=approved, not expired, approver authority, case state.
    Idempotent: same action_id executes only once.
    Transactional: business state change + audit in same transaction.
    Rollback on failure → status=failed, no partial state."""

def create_evidence_task(db_path: str, case_id: str, task_type: str, actor_context: dict, description: str) -> dict:
    """Create supplementary evidence request (reweigh, rephoto, rescan).
    Idempotent: one open task per (case_id, task_type)."""

# services/audit.py
def append_audit(db_path: str, actor_id: str, case_id: str | None, operation: str, details: dict,
                 tx: sqlite3.Connection | None = None) -> bool:
    """Append audit event. If tx provided, writes within that transaction (rollback on failure).
    If no tx, raises AuditError on failure. Business state change + audit = same transaction."""

def export_audit(db_path: str, case_id: str | None = None, actor_context: dict | None = None) -> dict:
    """Export audit trail as JSON. Authorization enforced on case_id."""

# agent/runner.py
def investigate_case(db_path: str, case_id: str, actor_context: dict) -> dict:
    """Run investigation loop: max 4 tool rounds, then structured report.
    actor_context from session; model cannot specify identity."""

# agent/tools.py
TOOL_WHITELIST = [
    "get_vendor_context", "get_shipment_timeline", "compare_handoff",
    "find_photo_reuse", "check_access_scope", "get_context_events",
    "get_partner_metrics"
]
def dispatch_tool(db_path: str, tool_name: str, params: dict, case_context: dict, actor_context: dict) -> dict:
    """Validate tool name, params, case scope, and actor permissions.
    actor_context is always server-provided, never from model."""
```

## 5. File Ownership

| Role | Owns | Cannot Touch |
|---|---|---|
| Main Agent | `app.py`, `schema.sql`, `contracts.py`, `requirements.txt`, `start.ps1`, `docs/`, `README.md` | Role-specific directories |
| A: Data | `db.py` (incl. `submit_event`, `upload_photo`), `seed.py`, `fixtures/`, `tests/test_data.py` | `services/`, `agent/`, `ui/` |
| B: Evidence | `services/access.py`, `services/handoff.py` (incl. `create_or_update_case`), `services/photos.py`, `services/risk.py`, `tests/test_rules.py` | `db.py`, `agent/`, `ui/` |
| C: Investigation | `agent/`, `tests/test_agent.py` | `services/`, `db.py`, `ui/` |
| D: Application | `ui/`, `services/actions.py` (incl. `create_evidence_task`), `services/audit.py`, `tests/test_actions.py` | `db.py`, `agent/`, `services/access.py` |
| E: QA | `tests/integration/`, `tests/acceptance/`, `evaluation/`, `qa/` | All source code (can suggest fixes) |

## 6. Test Requirements

- All service functions accept `db_path: str` as first parameter (default `"data/parcelverify.db"`)
- Every role creates tests using `tempfile.mkdtemp()` for an isolated database; tests call `init_db(temp_path)` and `seed_demo(temp_path)` on their own copy
- Tests must NEVER reference `"data/parcelverify.db"` — the demo database is only for runtime and seed
- QA writes integration and acceptance tests against separate test data
- Test answers must not be in the agent's context
- Scoring: `seal_mismatch=25, weight_diff=20, photo_reuse=25, location_conflict=10, time_conflict=10, access_anomaly=10` — max one per category per case, cap 100
- `review_queue = (total_score >= 30) OR (len(blocking_issues) > 0)`; maps to case status `pending_review`
- Score ≥60 → priority processing order; blocking issues enter review independently of score
