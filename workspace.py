"""Isolated synthetic workspaces addressed by private recovery tokens."""
import hashlib
import os
import secrets
import shutil
import time
from pathlib import Path
from db import init_db
from seed import seed_demo

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("PV_DATA_DIR", str(ROOT / "data" / "workspaces"))).resolve()
RETENTION_SECONDS = 24 * 3600

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
    init_db(path)
    seed_demo(path, seed=42)
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
