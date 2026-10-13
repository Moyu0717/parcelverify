"""
ParcelVerify — Photo Service
Owner: Role B (Evidence Agent)

Provides:
- inspect_photo(): Return same-file / similar candidates and authorized evidence
- find_photo_reuse(): SHA-256 exact match + pHash similar candidates across shipments
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from contracts import (
    ActorContext,
    AuthorizationError,
    PHASH_DISTANCE_THRESHOLD,
)
from db import get_connection


def _validate_actor(actor_context: dict) -> ActorContext:
    return ActorContext(**actor_context)


def _hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hex perceptual hashes."""
    try:
        h1 = int(hash1, 16)
        h2 = int(hash2, 16)
        return bin(h1 ^ h2).count("1")
    except (ValueError, TypeError):
        return 64  # max distance


def _is_authorized_for_shipment(
    conn: sqlite3.Connection,
    actor: ActorContext,
    shipment_id: str,
) -> bool:
    """Check if actor is authorized to see data for a shipment."""
    from services.access import _is_authorized, _utc_now_iso
    return _is_authorized(conn, actor, shipment_id, _utc_now_iso())[0]


def inspect_photo(
    db_path: str = "data/parcelverify.db",
    photo_id: str = "",
    actor_context: dict | None = None,
) -> dict:
    """Return same-file / similar candidates and authorized evidence.

    Authorization enforced: only reveals metadata the actor is
    authorized to see (D-014).
    """
    actor = _validate_actor(actor_context or {})
    conn = get_connection(db_path)
    try:
        photo = conn.execute(
            "SELECT photo_id, event_id, local_path, sha256, phash, "
            "uploaded_at, claimed_capture_at, capture_method, "
            "manual_observation FROM photos WHERE photo_id = ?",
            (photo_id,),
        ).fetchone()

        if not photo:
            return {
                "photo_id": photo_id,
                "sha256": None,
                "phash": None,
                "exact_matches": [],
                "similar_candidates": [],
                "evidence_ids": [],
            }

        p_id, event_id, local_path, sha256, phash, uploaded_at, \
            claimed_capture_at, capture_method, manual_obs = photo

        # Get the shipment for this photo's event
        event_row = conn.execute(
            "SELECT shipment_id FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        shipment_id = event_row[0] if event_row else None

        # Authorization check
        if not _is_authorized_for_shipment(conn, actor, shipment_id or ""):
            raise AuthorizationError(
                f"Actor {actor.actor_id} is not authorized for "
                f"shipment {shipment_id}"
            )

        # Find exact SHA-256 matches (cross-shipment)
        exact_rows = conn.execute(
            """SELECT p.photo_id, e.shipment_id, e.event_id
               FROM photos p
               JOIN events e ON p.event_id = e.event_id
               WHERE p.sha256 = ? AND p.photo_id != ?""",
            (sha256, photo_id),
        ).fetchall()

        exact_matches = []
        for row in exact_rows:
            match_photo_id, match_shipment, match_event = row
            # Mask unauthorized fields
            if _is_authorized_for_shipment(conn, actor, match_shipment):
                exact_matches.append({
                    "photo_id": match_photo_id,
                    "event_id": match_event,
                    "shipment_id": match_shipment,
                })
            else:
                # Mask: only show photo_id, hide shipment details
                exact_matches.append({
                    "photo_id": "[masked]",
                    "event_id": "[masked]",
                    "shipment_id": "[masked]",
                })

        # Find similar pHash candidates
        similar_candidates = []
        if phash:
            all_photos = conn.execute(
                """SELECT p.photo_id, p.phash, e.shipment_id, e.event_id
                   FROM photos p
                   JOIN events e ON p.event_id = e.event_id
                   WHERE p.photo_id != ? AND p.phash IS NOT NULL""",
                (photo_id,),
            ).fetchall()

            for row in all_photos:
                other_photo_id, other_phash, other_shipment, other_event = row
                distance = _hamming_distance(phash, other_phash)
                if distance <= PHASH_DISTANCE_THRESHOLD:
                    if _is_authorized_for_shipment(conn, actor, other_shipment):
                        similar_candidates.append({
                            "photo_id": other_photo_id,
                            "event_id": other_event,
                            "shipment_id": other_shipment,
                            "hamming_distance": distance,
                        })
                    else:
                        similar_candidates.append({
                            "photo_id": "[masked]",
                            "event_id": "[masked]",
                            "shipment_id": "[masked]",
                            "hamming_distance": distance,
                        })

        # Sort by hamming distance
        similar_candidates.sort(key=lambda x: x["hamming_distance"])

        return {
            "photo_id": p_id,
            "sha256": sha256,
            "phash": phash,
            "exact_matches": exact_matches,
            "similar_candidates": similar_candidates,
            "evidence_ids": [p_id] + [m["photo_id"] for m in exact_matches],
        }
    finally:
        conn.close()


def find_photo_reuse(
    db_path: str = "data/parcelverify.db",
    photo_id: str = "",
    actor_context: dict | None = None,
) -> dict:
    """SHA-256 exact match + pHash similar candidates across shipments.

    ``actor_context`` is always server-provided (from session), never
    model-specified (D-014).

    Cross-shipment matches mask unauthorized fields.
    """
    # find_photo_reuse uses the same logic as inspect_photo
    # but is explicitly for cross-shipment search
    return inspect_photo(db_path, photo_id, actor_context)
