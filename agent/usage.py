"""Atomic, shared on-disk demo request guard; never a provider billing control."""
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from agent.configuration import bounded_setting

class UsageLimit(ValueError):pass

def reserve_request(estimated_tokens):
    root=Path(os.getenv('PV_DATA_DIR',str(Path(__file__).resolve().parents[1]/'data'/'workspaces')))
    root.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(str(root/'groq-usage.db'),timeout=5) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS requests (at REAL NOT NULL, estimated_tokens INTEGER NOT NULL)')
        conn.execute('BEGIN IMMEDIATE')
        now=time.time()
        conn.execute('DELETE FROM requests WHERE at < ?', (now-86400,))
        day=conn.execute('SELECT COUNT(*),COALESCE(SUM(estimated_tokens),0) FROM requests').fetchone()
        minute=conn.execute('SELECT COUNT(*),COALESCE(SUM(estimated_tokens),0) FROM requests WHERE at>=?',(now-60,)).fetchone()
        if day[0]>=bounded_setting('GROQ_GLOBAL_DAILY',30,100) or day[1]+estimated_tokens>60000:
            raise UsageLimit('The shared demo daily AI limit is reached. Continue manual review and try later.')
        if minute[0]>=10 or minute[1]+estimated_tokens>6000:
            raise UsageLimit('A temporary demo AI usage limit is reached. Continue manual review and try again later.')
        conn.execute('INSERT INTO requests VALUES (?,?)',(now,estimated_tokens))

def evidence_snapshot(conn, actor):
    """Conservative invalidation on any relevant evidence or permission change."""
    digest=hashlib.sha256(json.dumps(actor.model_dump(),sort_keys=True).encode())
    for table in ('events','photos','access_logs','assignments','contract_history','case_members','case_findings','finding_reviews','case_decisions'):
        for row in conn.execute('SELECT * FROM '+table+' ORDER BY rowid'):
            digest.update(json.dumps(list(row),sort_keys=True,default=str).encode())
    return digest.hexdigest()
