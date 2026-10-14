-- ParcelVerify Schema v1.1
-- Owner: Main Agent
-- All times: UTC ISO 8601. Weight: grams (g). PRAGMA foreign_keys = ON on every connection.

PRAGMA foreign_keys = ON;

-- ============================================================
-- Partners
-- ============================================================
CREATE TABLE IF NOT EXISTS partners (
  partner_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  contract_end TEXT,
  service_area TEXT,
  approved_scope TEXT,
  vendor_evidence_id TEXT
);

-- ============================================================
-- Contract History (D-019) — time-accurate authorization
-- ============================================================
CREATE TABLE IF NOT EXISTS contract_history (
  history_id TEXT PRIMARY KEY,
  partner_id TEXT NOT NULL REFERENCES partners(partner_id),
  contract_snapshot_json TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_until TEXT,
  changed_by TEXT,
  changed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contract_history_partner_time
  ON contract_history(partner_id, effective_from, effective_until);

-- ============================================================
-- Shipments
-- ============================================================
CREATE TABLE IF NOT EXISTS shipments (
  shipment_id TEXT PRIMARY KEY,
  partner_id TEXT REFERENCES partners(partner_id),
  expected_count INTEGER,
  expected_weight_g REAL,
  expected_seal TEXT,
  destination_lat REAL,
  destination_lon REAL,
  status TEXT NOT NULL,
  reference_event_id TEXT
);

-- ============================================================
-- Assignments
-- ============================================================
CREATE TABLE IF NOT EXISTS assignments (
  assignment_id TEXT PRIMARY KEY,
  shipment_id TEXT REFERENCES shipments(shipment_id),
  partner_id TEXT REFERENCES partners(partner_id),
  actor_id TEXT NOT NULL,
  valid_from TEXT NOT NULL,
  valid_until TEXT,
  allowed_actions TEXT NOT NULL
);

-- ============================================================
-- Events — includes repackaging_approved (D-005)
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  shipment_id TEXT REFERENCES shipments(shipment_id),
  partner_id TEXT REFERENCES partners(partner_id),
  actor_id TEXT,
  event_type TEXT NOT NULL,
  occurred_at TEXT,
  received_at TEXT NOT NULL,
  source TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  is_synthetic INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_events_shipment ON events(shipment_id);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type, occurred_at);

-- Idempotency index for submit_event (D-016)
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup
  ON events(shipment_id, event_type, occurred_at, source);

-- ============================================================
-- Access Logs (Gate 1)
-- ============================================================
CREATE TABLE IF NOT EXISTS access_logs (
  log_id TEXT PRIMARY KEY,
  partner_id TEXT REFERENCES partners(partner_id),
  actor_id TEXT,
  credential_id TEXT,
  shipment_id TEXT,
  occurred_at TEXT NOT NULL,
  action TEXT NOT NULL,
  outcome TEXT NOT NULL,
  returned_fields TEXT,
  batch_job_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_access_logs_partner ON access_logs(partner_id, occurred_at);

-- ============================================================
-- Photos
-- ============================================================
CREATE TABLE IF NOT EXISTS photos (
  photo_id TEXT PRIMARY KEY,
  event_id TEXT REFERENCES events(event_id),
  local_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  phash TEXT,
  uploaded_at TEXT NOT NULL,
  claimed_capture_at TEXT,
  capture_method TEXT,
  manual_observation TEXT
);
CREATE INDEX IF NOT EXISTS idx_photos_sha256 ON photos(sha256);
CREATE INDEX IF NOT EXISTS idx_photos_phash ON photos(phash);
CREATE INDEX IF NOT EXISTS idx_photos_event ON photos(event_id);

-- Idempotency index for upload_photo (D-016)
CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_dedup
  ON photos(event_id, sha256);

-- ============================================================
-- Case Records — triggering_event_id for idempotency (D-016)
-- ============================================================
CREATE TABLE IF NOT EXISTS case_records (
  case_id TEXT PRIMARY KEY,
  partner_id TEXT REFERENCES partners(partner_id),
  shipment_id TEXT REFERENCES shipments(shipment_id),
  triggering_event_id TEXT,
  status TEXT NOT NULL,
  priority_score INTEGER,
  rule_version TEXT,
  findings_json TEXT,
  report_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_cases_shipment ON case_records(shipment_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON case_records(status);

-- Idempotency: one case per (shipment_id, triggering_event_id) — D-016
CREATE UNIQUE INDEX IF NOT EXISTS idx_cases_dedup
  ON case_records(shipment_id, triggering_event_id)
  WHERE triggering_event_id IS NOT NULL;

-- ============================================================
-- Evidence Tasks (D-016) — supplementary evidence requests
-- ============================================================
CREATE TABLE IF NOT EXISTS evidence_tasks (
  task_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES case_records(case_id),
  task_type TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_by TEXT,
  created_at TEXT NOT NULL,
  closed_at TEXT,
  resolution_json TEXT
);

-- Idempotency: one open task per (case_id, task_type) — D-016
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_tasks_open
  ON evidence_tasks(case_id, task_type)
  WHERE status = 'open';

-- ============================================================
-- Action Requests — strict state machine (D-019)
-- ============================================================
CREATE TABLE IF NOT EXISTS action_requests (
  action_id TEXT PRIMARY KEY,
  case_id TEXT REFERENCES case_records(case_id),
  action_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  status TEXT NOT NULL,
  requested_by TEXT,
  approved_by TEXT,
  approved_at TEXT,
  executed_at TEXT,
  expires_at TEXT,
  reason TEXT,
  before_json TEXT,
  after_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_actions_case ON action_requests(case_id);
CREATE INDEX IF NOT EXISTS idx_actions_status ON action_requests(status);

-- ============================================================
-- Audit Log — transactional (D-015)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id TEXT PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  case_id TEXT,
  operation TEXT NOT NULL,
  details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id, occurred_at);

-- ============================================================
-- Report Versions (D-011)
-- ============================================================
CREATE TABLE IF NOT EXISTS report_versions (
  report_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES case_records(case_id),
  run_id TEXT REFERENCES investigation_runs(run_id),
  version INTEGER NOT NULL,
  report_json TEXT NOT NULL,
  model_name TEXT,
  rule_version TEXT,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_case ON report_versions(case_id, version);

-- ============================================================
-- Tool Executions (D-011) — agent investigation audit trail
-- ============================================================
CREATE TABLE IF NOT EXISTS investigation_runs (
  run_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES case_records(case_id),
  actor_id TEXT NOT NULL,
  status TEXT NOT NULL,
  model_name TEXT,
  error TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS tool_executions (
  tool_exec_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES case_records(case_id),
  report_id TEXT REFERENCES report_versions(report_id),
  run_id TEXT REFERENCES investigation_runs(run_id),
  tool_name TEXT NOT NULL,
  parameters_json TEXT NOT NULL,
  result_summary TEXT,
  evidence_ids_json TEXT,
  source TEXT NOT NULL,
  duration_ms INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tool_exec_case ON tool_executions(case_id, created_at);

-- Additive investigation grouping. Original event-scoped cases remain intact.
CREATE TABLE IF NOT EXISTS case_members (
 parent_case_id TEXT NOT NULL REFERENCES case_records(case_id),
 member_case_id TEXT PRIMARY KEY REFERENCES case_records(case_id),
 linkage_reason TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_findings (
 finding_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL REFERENCES case_records(case_id),
 category TEXT NOT NULL,
 description TEXT NOT NULL,
 evidence_ids_json TEXT NOT NULL,
 required INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS finding_reviews (
 finding_id TEXT PRIMARY KEY REFERENCES case_findings(finding_id),
 outcome TEXT NOT NULL,
 reason TEXT NOT NULL,
 evidence_ids_json TEXT NOT NULL,
 reviewed_by TEXT NOT NULL,
 reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_decisions (
 decision_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL REFERENCES case_records(case_id),
 outcome TEXT NOT NULL,
 reason TEXT NOT NULL,
 evidence_ids_json TEXT NOT NULL,
 unresolved_json TEXT NOT NULL,
 actor_id TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_submissions (
 submission_id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL REFERENCES evidence_tasks(task_id),
 submission_key TEXT NOT NULL UNIQUE,
 intent_hash TEXT NOT NULL,
 event_id TEXT NOT NULL REFERENCES events(event_id),
 photo_id TEXT REFERENCES photos(photo_id),
 actor_id TEXT NOT NULL,
 created_at TEXT NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'pending',
 review_reason TEXT,
 reviewed_by TEXT,
 reviewed_at TEXT
);

-- Persistent idempotency for explicit AI submissions, separate from records.
CREATE TABLE IF NOT EXISTS investigation_submissions (
 actor_id TEXT NOT NULL,
 request_id TEXT NOT NULL,
 snapshot TEXT NOT NULL,
 run_id TEXT NOT NULL REFERENCES investigation_runs(run_id),
 PRIMARY KEY(actor_id,request_id)
);
