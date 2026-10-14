"""Explicit live-model acceptance; no mock or canned report substitutions."""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.runner import investigate_case
from db import get_connection, init_db
from seed import seed_demo
from services.workflow import initialize_reviews, submit_handoff
from services.handoff import create_or_update_case

def main():
    os.environ.setdefault("PV_AI_PROVIDER", "gemini")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="qa/artifacts/real-ai.json")
    args = parser.parse_args()
    actor = {"actor_id": "ADMIN-ACCEPTANCE", "role": "admin", "session_id": "real-ai-acceptance"}
    with tempfile.TemporaryDirectory(prefix="pv-real-") as directory:
        path = str(Path(directory) / "test.db")
        init_db(path)
        seed_demo(path)
        initialize_reviews(path, actor)
        with get_connection(path) as conn:
            main_case = conn.execute("SELECT case_id FROM case_records WHERE shipment_id='PV-DEMO-001'").fetchone()[0]
            explained_case = conn.execute("SELECT case_id FROM case_records WHERE shipment_id='PV-SHIP-011'").fetchone()[0]
            incomplete_case = conn.execute("SELECT case_id FROM case_records WHERE shipment_id='PV-SHIP-021'").fetchone()[0]
        results = []
        for label, case_id in [("main_exception", main_case), ("supported_repackaging", explained_case), ("insufficient_evidence", incomplete_case)]:
            result = investigate_case(path, case_id, actor)
            results.append({"scenario": label, **result})
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(results, indent=2), encoding="utf-8")
        passed = all(r["status"] == "completed" and r["tool_calls"] and r["report"] for r in results)
        print(json.dumps({"passed": passed, "statuses": [r["status"] for r in results], "artifact": str(destination.resolve())}))
        return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
