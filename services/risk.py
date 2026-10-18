"""
ParcelVerify — Risk Service
Owner: Role B (Evidence Agent)

Provides:
- calculate_priority(): Return total score and per-item scores; deduplicate by category
- get_partner_metrics(): Normalized volume, anomaly rate, sample size, open cases
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from contracts import (
    SCORING_MAP,
    MAX_SCORE,
    REVIEW_QUEUE_THRESHOLD,
    PRIORITY_THRESHOLD,
    DISPLAY_THRESHOLD_SHIPMENTS,
)
from db import get_connection


def calculate_priority(
    db_path: str = "data/parcelverify.db",
    findings: list[dict] | None = None,
) -> dict:
    """Return total score and per-item scores; deduplicate by category.

    Scoring map (D-002 through D-008):
    - seal_mismatch / id_conflict: 25 pts (one category, max 25)
    - weight_diff: 20 pts
    - photo_reuse: 25 pts (SHA or pHash, one category)
    - location_conflict: 10 pts
    - time_conflict: 10 pts
    - access_anomaly: 10 pts

    review_queue = (total_score >= 30) OR (len(blocking_issues) > 0)  — D-013
    """
    findings = findings or []

    # Collect blocking issues
    blocking_issues = [
        f["description"] for f in findings
        if f.get("severity") == "blocking"
    ]

    # Deduplicate by category — one score per category per case
    seen_categories: set[str] = set()
    items: list[dict] = []
    total_score = 0

    for finding in findings:
        category = finding.get("category", "")

        # Map category to scoring key
        score_key = None
        if category in ("seal_mismatch", "id_conflict"):
            score_key = "seal_mismatch"
        elif category == "weight_diff":
            score_key = "weight_diff"
        elif category == "photo_reuse":
            score_key = "photo_reuse"
        elif category == "location_conflict":
            score_key = "location_conflict"
        elif category == "time_conflict":
            score_key = "time_conflict"
        elif category == "access_anomaly":
            score_key = "access_anomaly"

        if score_key is None:
            # Categories without scoring (e.g., count_discrepancy) don't add score
            items.append({
                "category": category,
                "score": 0,
                "deduplicated": False,
            })
            continue

        if score_key in seen_categories:
            items.append({
                "category": category,
                "score": SCORING_MAP.get(score_key, 0),
                "deduplicated": True,
            })
            continue

        seen_categories.add(score_key)
        score = SCORING_MAP.get(score_key, 0)
        total_score += score
        items.append({
            "category": category,
            "score": score,
            "deduplicated": False,
        })

    # Cap at 100
    total_score = min(total_score, MAX_SCORE)

    review_queue = (total_score >= REVIEW_QUEUE_THRESHOLD) or (len(blocking_issues) > 0)
    priority = total_score >= PRIORITY_THRESHOLD

    return {
        "total_score": total_score,
        "items": items,
        "review_queue": review_queue,
        "priority": priority,
        "blocking_issues": blocking_issues,
    }


def get_partner_metrics(db_path: str = "data/parcelverify.db", partner_id: str = "", period_start: str | None = None, period_end: str | None = None) -> dict:
    """Use one shipment cohort for every metric; all recorded history by default."""
    conn = get_connection(db_path)
    try:
        population = conn.execute("""SELECT s.shipment_id FROM shipments s WHERE s.partner_id = ?
            AND (? IS NULL AND ? IS NULL OR EXISTS (SELECT 1 FROM events e WHERE e.shipment_id = s.shipment_id
            AND (? IS NULL OR julianday(e.occurred_at) >= julianday(?))
            AND (? IS NULL OR julianday(e.occurred_at) < julianday(?))))""",
            (partner_id, period_start, period_end, period_start, period_start, period_end, period_end)).fetchall()
        ids = {row[0] for row in population}
        affected, complete = set(), set()
        open_cases = 0
        for shipment_id in ids:
            cases = conn.execute("SELECT status, findings_json, created_at, EXISTS(SELECT 1 FROM evidence_tasks t WHERE t.case_id=c.case_id AND t.status='open') FROM case_records c WHERE shipment_id = ?", (shipment_id,)).fetchall()
            for status, findings, created, has_open_task in cases:
                if not _in_period(created, period_start, period_end):
                    continue
                if json.loads(findings or "[]"):
                    affected.add(shipment_id)
                if status not in ("closed", "review_completed") or has_open_task:
                    open_cases += 1
            logs = conn.execute("SELECT occurred_at FROM access_logs WHERE shipment_id = ? AND outcome = 'denied'", (shipment_id,)).fetchall()
            if any(_in_period(row[0], period_start, period_end) for row in logs):
                affected.add(shipment_id)
            event_types = {row[0] for row in conn.execute("SELECT event_type, occurred_at FROM events WHERE shipment_id = ?", (shipment_id,)).fetchall() if _in_period(row[1], period_start, period_end)}
            if {"handoff_submitted", "pod_submitted"} <= event_types:
                complete.add(shipment_id)
        total = len(ids)
        return {"partner_id": partner_id, "total_shipments": total, "anomaly_count": len(affected),
                "anomaly_rate_per_1000": round(len(affected) / total * 1000, 1) if total else 0.0,
                "evidence_completeness_rate": round(len(complete) / total, 2) if total else 0.0,
                "open_cases": open_cases, "sample_size": total,
                "meets_display_threshold": total >= DISPLAY_THRESHOLD_SHIPMENTS,
                "period_start": period_start, "period_end": period_end}
    finally:
        conn.close()


def _in_period(value: str | None, start: str | None, end: str | None) -> bool:
    from services.access import _parse_time
    if not start and not end:
        return True
    if not value:
        return False
    when = _parse_time(value)
    return (not start or when >= _parse_time(start)) and (not end or when < _parse_time(end))


def summarize_permitted_shipments(db_path: str, shipment_ids) -> dict:
    """All-history review context for an already permission-filtered cohort.

    Category recurrence counts distinct shipments, not repeated case records.
    A supported finding is a human-recorded outcome, never a fraud verdict.
    """
    from services.handoff import compare_handoff
    ids = sorted(set(shipment_ids))
    categories, affected = {}, set()
    open_findings = supported = resolved = 0
    with get_connection(db_path) as conn:
        for sid in ids:
            for category, state in conn.execute(
                "SELECT f.category,r.outcome FROM case_findings f "
                "JOIN case_records c ON c.case_id=f.case_id "
                "LEFT JOIN finding_reviews r ON r.finding_id=f.finding_id "
                "WHERE c.shipment_id=?", (sid,)
            ):
                if category == 'authorized_export':
                    continue
                affected.add(sid)
                categories.setdefault(category, set()).add(sid)
                open_findings += state in (None, 'unresolved')
                supported += state == 'supported'
                resolved += state == 'resolved'
    missing = sum(bool(compare_handoff(db_path, sid)['unknowns']) for sid in ids)
    return dict(total_shipments=len(ids), affected_shipments=len(affected),
                recurring_categories={key: len(value) for key, value in sorted(categories.items())},
                open_findings=open_findings, supported_findings=supported, resolved_findings=resolved,
                complete_shipments=len(ids)-missing, missing_evidence_shipments=missing,
                small_sample=len(ids) < DISPLAY_THRESHOLD_SHIPMENTS)
