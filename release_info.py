"""Source-derived build identity and non-secret configuration diagnostics."""
import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATASET_VERSION = 'linked-cases-v5'
RELEASE = 'groq-repair-20261018.1'

def build_information():
    digest = hashlib.sha256()
    paths = [ROOT / name for name in ('app.py', 'workspace.py', 'release_info.py', 'schema.sql', 'seed.py', 'demo_fixtures.py', 'contracts.py', 'db.py')]
    for folder in ('agent', 'services', 'ui'):
        paths.extend((ROOT / folder).glob('*.py'))
        paths.extend((ROOT / folder).glob('*.css'))
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes().replace(b'\r\n', b'\n').rstrip(b'\n') + b'\n')
    commit = 'Unavailable'
    if (ROOT / '.git').exists():
        try:
            clean = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, capture_output=True, text=True, timeout=3, check=True)
            if not clean.stdout.strip():
                commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, timeout=3, check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return {'Release': RELEASE, 'Source build': digest.hexdigest()[:16], 'Checked-out commit': commit,
            'Python runtime':sys.version.split()[0], 'Entry point':'app.py'}

def dataset_version(db_path):
    with sqlite3.connect(db_path) as conn:
        try:
            row = conn.execute("SELECT value FROM demo_metadata WHERE key='dataset_version'").fetchone()
            return row[0] if row else 'Legacy / unversioned'
        except sqlite3.OperationalError:
            return 'Legacy / unversioned'

def ai_configuration():
    from agent.configuration import provider_settings
    settings = provider_settings()
    return {'Provider': settings['provider'], 'Model': settings['model'], 'Endpoint': 'Official Groq API',
            'Credentials': 'Configured (not validated)' if settings['configured'] else 'Missing GROQ_API_KEY',
            'Execution': 'Enabled; explicit action required' if settings['enabled'] else 'Disabled; manual review available'}
