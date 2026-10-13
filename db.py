"""
ParcelVerify - Database Layer
Owner: Role A (Data Agent)

Provides:
- init_db(): Create/migrate database from schema.sql (idempotent)
- get_connection(): Connection with PRAGMA foreign_keys = ON
- submit_event(): Create events with idempotency (D-016)
- upload_photo(): Store photos with SHA-256, pHash, and idempotency (D-016)
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from contracts import ActorContext, AuthorizationError

# Path to schema.sql (same directory as this file)
_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

# Validation limits
_MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_MEGAPIXELS = 20  # 20 MP
_ALLOWED_FORMATS = {"JPEG", "PNG"}


class ManagedConnection(sqlite3.Connection):
    """Commit or roll back a context transaction and then release its file handle."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _validate_actor_context(actor_context: dict) -> ActorContext:
    """Validate dict and return ActorContext."""
    return ActorContext(**actor_context)


def _get_photos_dir(db_path: str) -> str:
    """Derive photos directory from db_path's parent directory."""
    parent = os.path.dirname(db_path)
    if parent:
        return os.path.join(parent, "photos")
    return "photos"


def init_db(db_path: str = "data/parcelverify.db") -> None:
    """Create/migrate database; does not overwrite existing data.

    Executes schema.sql against the database. Idempotent - safe to call
    multiple times. All statements use IF NOT EXISTS.
    """
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(db_path, factory=ManagedConnection)
    try:
        conn.executescript(schema_sql)
        columns = {r[1] for r in conn.execute("PRAGMA table_info(tool_executions)")}
        if "run_id" not in columns:
            conn.execute("ALTER TABLE tool_executions ADD COLUMN run_id TEXT REFERENCES investigation_runs(run_id)")
        columns = {r[1] for r in conn.execute("PRAGMA table_info(report_versions)")}
        if "run_id" not in columns:
            conn.execute("ALTER TABLE report_versions ADD COLUMN run_id TEXT REFERENCES investigation_runs(run_id)")
        conn.commit()
    finally:
        conn.close()


def get_connection(db_path: str = "data/parcelverify.db") -> sqlite3.Connection:
    """Return connection with PRAGMA foreign_keys = ON.

    Caller is responsible for closing (use context manager).
    """
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    conn = sqlite3.connect(db_path, factory=ManagedConnection)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _check_authorization(conn: sqlite3.Connection, actor: ActorContext,
                        shipment_id: str, at_time: str) -> bool:
    """Check if actor has a valid assignment for the shipment at the given time.

    Admins and investigators bypass assignment checks (internal staff).
    Partner users must have an assignment row covering at_time.
    """
    if actor.role in ("admin", "investigator"):
        return True

    # Check by actor_id
    row = conn.execute(
        """
        SELECT 1 FROM assignments
        WHERE shipment_id = ?
          AND actor_id = ?
          AND valid_from <= ?
          AND (valid_until IS NULL OR valid_until > ?)
        LIMIT 1
        """,
        (shipment_id, actor.actor_id, at_time, at_time),
    ).fetchone()
    if row:
        return True

    # Check by partner_id
    if actor.partner_id:
        row = conn.execute(
            """
            SELECT 1 FROM assignments
            WHERE shipment_id = ?
              AND partner_id = ?
              AND valid_from <= ?
              AND (valid_until IS NULL OR valid_until > ?)
            LIMIT 1
            """,
            (shipment_id, actor.partner_id, at_time, at_time),
        ).fetchone()
        if row:
            return True

    return False


def submit_event(
    db_path: str,
    actor_context: dict,
    shipment_id: str,
    event_type: str,
    payload: dict,
    source: str,
    occurred_at: str,
) -> dict:
    """Create event with server-assigned event_id and received_at.

    Idempotent: same (shipment_id, event_type, occurred_at, source) returns
    the existing event with is_new=False.

    Authorization: actor must have a valid assignment for the shipment
    at occurred_at.

    Returns:
        dict: event_id, shipment_id, event_type, occurred_at,
              received_at, source, is_new
    """
    actor = _validate_actor_context(actor_context)
    conn = get_connection(db_path)
    try:
        from services.access import _is_authorized
        allowed, reason = _is_authorized(conn, actor, shipment_id, _utc_now_iso())
        if not allowed or actor.role == "approver":
            raise AuthorizationError(reason or "Approvers cannot submit evidence")
        conn.execute("BEGIN IMMEDIATE")
        # Idempotency check
        existing = conn.execute(
            """
            SELECT event_id, received_at FROM events
            WHERE shipment_id = ? AND event_type = ?
              AND occurred_at = ? AND source = ?
            """,
            (shipment_id, event_type, occurred_at, source),
        ).fetchone()

        if existing:
            return {
                "event_id": existing[0],
                "shipment_id": shipment_id,
                "event_type": event_type,
                "occurred_at": occurred_at,
                "received_at": existing[1],
                "source": source,
                "is_new": False,
            }

        # Authorization check
        if not _check_authorization(conn, actor, shipment_id, occurred_at):
            raise AuthorizationError(
                f"Actor {actor.actor_id} is not authorized for shipment "
                f"{shipment_id} at {occurred_at}"
            )

        # Look up partner_id from shipment
        shipment_row = conn.execute(
            "SELECT partner_id FROM shipments WHERE shipment_id = ?",
            (shipment_id,),
        ).fetchone()
        if not shipment_row:
            raise ValueError(f"Shipment {shipment_id} not found")
        partner_id = shipment_row[0]

        # Create event
        event_id = str(uuid.uuid4())
        received_at = _utc_now_iso()
        payload_json = json.dumps(payload)

        conn.execute(
            """
            INSERT INTO events (event_id, shipment_id, partner_id, actor_id,
                              event_type, occurred_at, received_at, source,
                              payload_json, is_synthetic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (event_id, shipment_id, partner_id, actor.actor_id,
             event_type, occurred_at, received_at, source, payload_json),
        )
        conn.commit()

        return {
            "event_id": event_id,
            "shipment_id": shipment_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "received_at": received_at,
            "source": source,
            "is_new": True,
        }
    finally:
        conn.close()


def _compute_phash(file_bytes: bytes) -> str | None:
    """Compute perceptual hash using Pillow + ImageHash."""
    try:
        from PIL import Image
        import imagehash

        img = Image.open(BytesIO(file_bytes))
        return str(imagehash.phash(img))
    except Exception:
        return None


def _validate_image(file_bytes: bytes) -> str:
    """Validate image format and dimensions. Returns the format string."""
    from PIL import Image

    try:
        img = Image.open(BytesIO(file_bytes))
        fmt = img.format
        if fmt not in _ALLOWED_FORMATS:
            raise ValueError(
                f"Unsupported image format: {fmt}. Only JPEG and PNG allowed."
            )
        width, height = img.size
        megapixels = (width * height) / 1_000_000
        if megapixels > _MAX_MEGAPIXELS:
            raise ValueError(
                f"Photo exceeds 20MP limit ({megapixels:.1f}MP)"
            )
        return fmt
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid image file: {e}")


def upload_photo(
    db_path: str,
    actor_context: dict,
    event_id: str,
    file_bytes: bytes,
    claimed_capture_at: str | None = None,
    capture_method: str = "upload",
    manual_observation: str = "",
) -> dict:
    """Store photo, compute SHA-256 and pHash.

    Idempotent: same SHA-256 for same event_id returns existing photo_id.

    Authorization: actor must be authorized for the event's shipment.

    Validates: JPEG/PNG, <=10MB, <=20MP.
    Generates internal random filename and saves to <db_dir>/photos/.

    Returns:
        dict: photo_id, sha256, phash, local_path, is_new
    """
    actor = _validate_actor_context(actor_context)

    # Validate file size
    if len(file_bytes) > _MAX_PHOTO_BYTES:
        raise ValueError(
            f"Photo exceeds 10MB limit ({len(file_bytes)} bytes)"
        )

    # Validate image format and dimensions
    fmt = _validate_image(file_bytes)

    # Compute SHA-256
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    conn = get_connection(db_path)
    try:
        from services.access import _is_authorized
        event = conn.execute("SELECT shipment_id FROM events WHERE event_id = ?", (event_id,)).fetchone()
        if not event:
            raise ValueError("Event not found")
        allowed, reason = _is_authorized(conn, actor, event[0], _utc_now_iso())
        if not allowed or actor.role == "approver":
            raise AuthorizationError(reason or "Approvers cannot upload evidence")
        conn.execute("BEGIN IMMEDIATE")
        # Idempotency check
        existing = conn.execute(
            "SELECT photo_id, local_path, phash FROM photos "
            "WHERE event_id = ? AND sha256 = ?",
            (event_id, sha256),
        ).fetchone()

        if existing:
            return {
                "photo_id": existing[0],
                "sha256": sha256,
                "phash": existing[2],
                "local_path": existing[1],
                "is_new": False,
            }

        # Get event's shipment for authorization check
        event_row = conn.execute(
            "SELECT shipment_id, occurred_at FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()

        if not event_row:
            raise ValueError(f"Event {event_id} not found")

        shipment_id, occurred_at = event_row
        at_time = occurred_at if occurred_at else _utc_now_iso()

        # Authorization check
        if not _check_authorization(conn, actor, shipment_id, at_time):
            raise AuthorizationError(
                f"Actor {actor.actor_id} is not authorized for shipment "
                f"{shipment_id} (event {event_id})"
            )

        # Compute pHash
        phash = _compute_phash(file_bytes)

        # Save file to disk
        photos_dir = _get_photos_dir(db_path)
        os.makedirs(photos_dir, exist_ok=True)
        stored = [entry for entry in os.scandir(photos_dir) if entry.is_file()]
        if len(stored) >= 25 or sum(entry.stat().st_size for entry in stored) + len(file_bytes) > 50 * 1024 * 1024:
            raise ValueError("Workspace upload limit reached (25 files or 50 MB). Start a new demo.")
        photo_id = str(uuid.uuid4())
        ext = ".jpg" if fmt == "JPEG" else ".png"
        filename = f"{photo_id}{ext}"
        local_path = os.path.join(photos_dir, filename)

        with open(local_path, "wb") as f:
            f.write(file_bytes)

        uploaded_at = _utc_now_iso()

        conn.execute(
            """
            INSERT INTO photos (photo_id, event_id, local_path, sha256,
                              phash, uploaded_at, claimed_capture_at,
                              capture_method, manual_observation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (photo_id, event_id, local_path, sha256,
             phash, uploaded_at, claimed_capture_at,
             capture_method, manual_observation),
        )
        conn.commit()

        return {
            "photo_id": photo_id,
            "sha256": sha256,
            "phash": phash,
            "local_path": local_path,
            "is_new": True,
        }
    finally:
        conn.close()
