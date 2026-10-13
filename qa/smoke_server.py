"""Check the portable application launcher over actual local HTTP."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    environment = dict(os.environ, PORT="18501")
    directory = ROOT / "qa" / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "server-smoke.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "start.py"], cwd=ROOT, env=environment,
            stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(40):
                if process.poll() is not None:
                    raise RuntimeError("Application launcher exited; see qa/artifacts/server-smoke.log")
                try:
                    with urllib.request.urlopen("http://127.0.0.1:18501/_stcore/health", timeout=1) as response:
                        if response.status == 200 and response.read() == b"ok":
                            print("PASS: portable launcher serves Streamlit HTTP health on port 18501")
                            return 0
                except OSError:
                    time.sleep(0.5)
            raise RuntimeError("Local HTTP health did not become ready")
        finally:
            # Stop only the process started here and its Streamlit child.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            else:
                process.terminate()
            process.wait(timeout=10)

if __name__ == "__main__":
    raise SystemExit(main())
