"""Explicit live-model acceptance; no mock or canned report substitutions."""
import argparse
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.runner import investigate_case
from db import get_connection, init_db
from seed import seed_demo
from services.workflow import initialize_reviews
from agent.configuration import provider_settings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="qa/artifacts/real-ai.json")
    parser.add_argument('--confirm-free-plan', action='store_true', help='Confirm the privately configured Groq account is on Free Plan.')
    args = parser.parse_args()
    settings = provider_settings()
    if not args.confirm_free_plan or not settings['configured'] or not settings['enabled']:
        parser.error('One live smoke test requires --confirm-free-plan, AI_PROVIDER=groq and a privately supplied GROQ_API_KEY. No model requests were made.')
    actor = {"actor_id": "ADMIN-ACCEPTANCE", "role": "admin", "session_id": "real-ai-acceptance"}
    with tempfile.TemporaryDirectory(prefix="pv-real-") as directory:
        path = str(Path(directory) / "test.db")
        init_db(path)
        seed_demo(path)
        initialize_reviews(path, actor)
        with get_connection(path) as conn:
            main_case = conn.execute("SELECT case_id FROM case_records WHERE shipment_id='PV-DEMO-001'").fetchone()[0]
        result = investigate_case(path, main_case, actor, request_id=str(uuid.uuid4()))
        results = [{"scenario": "main_exception", **result}]
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(results, indent=2), encoding="utf-8")
        passed = all(r["status"] == "completed" and r["tool_calls"] and r["report"] for r in results)
        print(json.dumps({"passed": passed, "statuses": [r["status"] for r in results], "artifact": str(destination.resolve())}))
        return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
