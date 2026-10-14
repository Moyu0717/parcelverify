"""Isolated synthetic workspaces addressed by private recovery tokens."""
import hashlib
import os
import secrets
import shutil
import time
import threading
from pathlib import Path
from db import init_db
from seed import seed_demo
from release_info import DATASET_VERSION

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("PV_DATA_DIR", str(ROOT / "data" / "workspaces"))).resolve()
RETENTION_SECONDS = 24 * 3600
_TEMPLATE_LOCK = threading.Lock()

def _prepare_template():
    """Reuse only initial synthetic records; never copy a visitor's mutable data."""
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    template = DATA_ROOT / "demo-template-v5-versioned.db"
    with _TEMPLATE_LOCK:
        if not template.exists():
            temporary = DATA_ROOT / "demo-template-v5-versioned.build.db"
            init_db(str(temporary))
            seed_demo(str(temporary), seed=42)
            from services.workflow import initialize_reviews
            initialize_reviews(str(temporary), {"actor_id": "SYSTEM-DEMO", "role": "admin", "session_id": "synthetic-template"})
            from db import get_connection
            with get_connection(str(temporary)) as conn:
                conn.execute('CREATE TABLE IF NOT EXISTS demo_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                conn.execute('INSERT OR REPLACE INTO demo_metadata VALUES (?,?)', ('dataset_version', DATASET_VERSION))
            os.replace(temporary, template)
    return template

def open_workspace(token=None):
    token = token or secrets.token_hex(32)
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("Use the 64-character recovery token from your own workspace.")
    directory = DATA_ROOT / hashlib.sha256(token.encode()).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / ".activity"
    if marker.exists() and time.time() - marker.stat().st_mtime > RETENTION_SECONDS:
        raise ValueError("This workspace expired. Start a new demo.")
    marker.touch()
    path = str(directory / "parcelverify.db")
    if not Path(path).exists():
        template = _prepare_template()
        temporary = directory / "parcelverify.build.db"
        shutil.copyfile(template, temporary)
        os.replace(temporary, path)
    init_db(path)
    return token, path

def prune_expired_workspaces():
    if not DATA_ROOT.exists():
        return
    for directory in DATA_ROOT.iterdir():
        marker = directory / ".activity"
        if directory.is_dir() and not directory.is_symlink() and len(directory.name) == 64:
            if marker.exists() and time.time() - marker.stat().st_mtime > RETENTION_SECONDS:
                resolved = directory.resolve()
                if resolved.parent == DATA_ROOT:
                    shutil.rmtree(resolved)
