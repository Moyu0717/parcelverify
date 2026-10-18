"""
ParcelVerify — Shared Contracts, Schemas, and Configuration
Owner: Main Agent
Version: 1.1 (2026-10-12)

This module defines all shared types, enums, Pydantic models, and the database
configuration mechanism. Sub-agents import from here but must not modify this file.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# Database Configuration (D-017)
# ============================================================

@dataclass
class DBConfig:
    """Centralized database configuration. All services accept db_path as first param."""
    default_path: str = "data/parcelverify.db"

    @staticmethod
    def temp_db() -> tuple[str, str]:
        """
        Create a temp directory and return (dir_path, db_path).
        Tests MUST use this to ensure isolation from the demo database.
        """
        d = tempfile.mkdtemp(prefix="pvtest_")
        return (d, os.path.join(d, "test.db"))


# ============================================================
# Enums (string-based, validated by code)
# ============================================================

class EventType(str, Enum):
    VENDOR_DOCUMENT = "vendor_document"
    DISPATCH_CONFIRMED = "dispatch_confirmed"
    HANDOFF_SUBMITTED = "handoff_submitted"
    POD_SUBMITTED = "pod_submitted"
    RECIPIENT_AUTHORIZATION = "recipient_authorization"
    MESSAGE_REPORTED = "message_reported"
    OFFICIAL_NOTICE = "official_notice"
    APPROVED_BATCH_JOB = "approved_batch_job"
    SCALE_CALIBRATION = "scale_calibration"
    ROUTE_EXCEPTION = "route_exception"
    REPACKAGING_APPROVED = "repackaging_approved"  # D-005


class CaseStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    UNDER_INVESTIGATION = "under_investigation"
    REVIEW_COMPLETED = "review_completed"
    ACTION_PROPOSED = "action_proposed"
    ACTION_APPROVED = "action_approved"
    ACTION_REJECTED = "action_rejected"
    ACTION_EXECUTED = "action_executed"
    ACTION_FAILED = "action_failed"
    CLOSED = "closed"


class ReportVerdict(str, Enum):
    CONSISTENT = "consistent"
    NEEDS_REVIEW = "requires_review"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"          # terminal (D-019)
    EXECUTED = "executed"          # terminal (D-019)
    FAILED = "failed"             # retryable


class ActionType(str, Enum):
    REQUEST_REWEIGH = "request_reweigh"
    REQUEST_REPHOTO = "request_rephoto"
    REQUEST_RESCAN = "request_rescan"
    HOLD_HANDOFF = "hold_handoff"
    HOLD_POD = "hold_pod"
    ENHANCE_INSPECTION = "enhance_inspection"
    PAUSE_HIGH_VALUE_ASSIGNMENT = "pause_high_value_assignment"
    RESTRICT_ACCOUNT = "restrict_account"
    SUBMIT_TO_CONTRACT_OPS = "submit_to_contract_ops"


class EvidenceTaskType(str, Enum):
    REWEIGH = "reweigh"
    REPHOTO = "rephoto"
    RESCAN = "rescan"
    SUPPLEMENTARY_STATEMENT = "supplementary_statement"


# ============================================================
# Actor Context (always server-provided, never from model — D-014)
# ============================================================

class ActorContext(BaseModel):
    """Identity context from the session. Never trust model-supplied identity."""
    model_config = ConfigDict(extra="forbid")
    actor_id: str
    partner_id: str | None = None
    role: Literal["investigator", "approver", "admin", "partner_user"] = "partner_user"
    session_id: str
    is_simulated: bool = True  # always True in prototype


# ============================================================
# Submission Chain Models (D-016)
# ============================================================

class EventSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shipment_id: str
    event_type: str
    payload: dict[str, Any]
    source: str
    occurred_at: str  # ISO 8601 UTC


class PhotoUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    claimed_capture_at: str | None = None
    capture_method: str = "upload"
    manual_observation: str = ""


# ============================================================
# Handoff / Evidence Models
# ============================================================

class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    description: str
    severity: Literal["info", "warning", "blocking"] = "warning"
    evidence_ids: list[str] = Field(default_factory=list)


class HandoffEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shipment_id: str
    event_id: str
    result: ReportVerdict
    findings: list[Finding] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)


class HandoffComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shipment_id: str
    count: dict[str, Any]  # expected, actual, match
    weight_g: dict[str, Any]  # expected, actual, diff, match
    seal: dict[str, Any]  # expected, actual, match
    recipient: dict[str, Any]  # expected, actual, authorized
    unknowns: list[str] = Field(default_factory=list)


# ============================================================
# Risk / Priority Models (D-013, D-018)
# ============================================================

class PriorityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_score: int = Field(ge=0, le=100)
    items: list[dict[str, Any]] = Field(default_factory=list)
    review_queue: bool  # (total_score >= 30) OR (len(blocking_issues) > 0)  — D-013
    priority: bool  # total_score >= 60
    blocking_issues: list[str] = Field(default_factory=list)


class PartnerMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partner_id: str
    total_shipments: int
    anomaly_count: int
    anomaly_rate_per_1000: float
    evidence_completeness_rate: float
    open_cases: int
    sample_size: int
    meets_display_threshold: bool  # >= 20 — display only, NOT statistical reliability (D-018)


# ============================================================
# Action Models (D-019)
# ============================================================

class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    action_type: ActionType
    reason: str = ""
    target_id: str = ""
    expires_at: str | None = None


class ActionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str
    decision: Literal["approve", "reject"]
    reason: str = ""


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str
    status: Literal["executed", "failed", "already_executed", "not_approved", "expired"]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    error: str | None = None


# ============================================================
# Investigation Report Models
# ============================================================

class ReportFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    """Final structured report from the investigation agent."""
    model_config = ConfigDict(extra="forbid")
    case_id: str
    verdict: ReportVerdict
    summary: str
    facts: list[ReportFact] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    requires_approval: bool = True
    limitations: str = ""

    @field_validator("verdict", mode="before")
    @classmethod
    def normalize_legacy_verdict(cls, value):
        return "requires_review" if value in ("needs_review", "requires review") else "insufficient_evidence" if value == "insufficient evidence" else value


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    params: dict[str, Any]
    result_summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class InvestigationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    status: Literal["completed", "timeout", "error", "ai_not_running"]
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    report: InvestigationReport | None = None
    model_name: str | None = None
    rule_version: str
    report_version: int | None = None
    total_duration_ms: int = 0


# ============================================================
# Tool Whitelist (D-014 — actor_context always from session)
# ============================================================

from agent.tool_registry import TOOL_REGISTRY
TOOL_WHITELIST: list[str] = list(TOOL_REGISTRY)

# Scoring map — max one per category per case, cap 100
SCORING_MAP: dict[str, int] = {
    "seal_mismatch": 25,       # includes id_conflict, number mismatch (D-002)
    "weight_diff": 20,
    "photo_reuse": 25,         # SHA or pHash, one category (D-008)
    "location_conflict": 10,
    "time_conflict": 10,
    "access_anomaly": 10,
}

MAX_SCORE: int = 100
REVIEW_QUEUE_THRESHOLD: int = 30
PRIORITY_THRESHOLD: int = 60

# Weight difference threshold: max(100g, base_weight * 5%) — D-006
WEIGHT_DIFF_MIN_G: float = 100.0
WEIGHT_DIFF_PCT: float = 0.05

# pHash similarity threshold
PHASH_DISTANCE_THRESHOLD: int = 6

# Display threshold for partner metrics (D-018)
DISPLAY_THRESHOLD_SHIPMENTS: int = 20

# Investigation constraints
MAX_TOOL_ROUNDS: int = 4
TOTAL_TIME_BUDGET_S: int = 120

# Rule version
RULE_VERSION: str = "1.1.0"


# ============================================================
# AuditError (D-015)
# ============================================================

class AuditError(Exception):
    """Raised when audit write fails outside a business transaction."""
    pass


class AuthorizationError(Exception):
    """Raised when an actor attempts an unauthorized action."""
    pass


class IdempotencyError(Exception):
    """Raised when an idempotent operation detects a conflicting state."""
    pass
