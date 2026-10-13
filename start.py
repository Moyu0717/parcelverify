"""Portable Streamlit entry point for local or container hosting."""
import os
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    port = str(int(os.environ.get("PORT", "8501")))
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(root / "app.py"),
        "--server.address=0.0.0.0", "--server.port=" + port, "--server.headless=true"], cwd=root))
