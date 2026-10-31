"""Start both independent applications from their own environments. Ctrl-C stops all four."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ctrlz = Path(__file__).resolve().parents[1]
campus = ctrlz.parent / "campuspass"
parser = argparse.ArgumentParser()
parser.add_argument("--campuspass", action="store_true")
args = parser.parse_args()
services = [(ctrlz, "ctrlz", "8000")]
if args.campuspass:
    services.insert(0,(campus,"campuspass","8001"))
if not all((root / ".env").exists() for root, _, _ in services):
    raise SystemExit("Run scripts/setup_env.py first (add --campuspass only for the optional companion).")
processes = []
try:
    for root, package, port in services:
        python = root / "backend" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        processes.append(subprocess.Popen([str(python), "-m", "uvicorn", package+".main:create_app", "--factory", "--host", "127.0.0.1", "--port", port, "--env-file", "../.env"], cwd=root / "backend"))
        processes.append(subprocess.Popen(["npm.cmd" if os.name == "nt" else "npm", "run", "dev"], cwd=root / "frontend"))
    print("CtrlZ: http://localhost:5173" + (" | Optional CampusPass: http://localhost:5174" if args.campuspass else ""), flush=True)
    while True:
        for process in processes:
            if process.poll() is not None:
                raise SystemExit(f"A development service exited ({process.returncode}); stopping the others.")
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
