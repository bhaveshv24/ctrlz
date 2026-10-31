"""Prepare and run the local CtrlZ frontend and API."""
import hashlib
import os
import shutil
import signal
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def project_environment():
    environment = dict(os.environ)
    environment.pop("VIRTUAL_ENV", None)
    environment.pop("UV_PROJECT_ENVIRONMENT", None)
    return environment


def run(arguments):
    subprocess.run([str(argument) for argument in arguments], cwd=ROOT,
                   env=project_environment(), check=True)


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        run([sys.executable, ROOT / "scripts/dev.py", *sys.argv[1:]])
        return 0
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise SystemExit("Node.js and npm are required. Install Node.js 22 or newer.")
    docker = shutil.which("docker")
    if not docker:
        raise SystemExit("Docker is required for repository verification.")
    check = subprocess.run(
        [docker, "image", "inspect", "ctrlz-sandbox:local", "ctrlz-node-sandbox:local"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if check.returncode:
        raise SystemExit("Start Docker, then run docker compose up --build -d first.")
    run([sys.executable, ROOT / "scripts/setup_env.py"])
    uv = shutil.which("uv")
    if not uv:
        tools = ROOT / ".dev-tools"
        python = tools / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.exists():
            venv.EnvBuilder(with_pip=True).create(tools)
        executable = tools / ("Scripts/uv.exe" if os.name == "nt" else "bin/uv")
        if not executable.exists():
            print("Installing the local Python dependency manager...", flush=True)
            run([python, "-m", "pip", "install", "uv"])
        uv = str(executable)
    print("Checking Python 3.12 and backend dependencies...", flush=True)
    run([uv, "sync", "--project", "backend", "--frozen", "--extra", "test", "--python", "3.12"])
    lock = ROOT / "frontend/package-lock.json"
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    marker = ROOT / "frontend/node_modules/.ctrlz-lock"
    if not marker.is_file() or marker.read_text().strip() != digest:
        print("Installing frontend dependencies...", flush=True)
        run([npm, "--prefix", "frontend", "ci"])
        marker.write_text(digest + "\n")
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    process = subprocess.Popen(
        [uv, "run", "--project", "backend", "--frozen", "--extra", "test",
         "python", "scripts/dev.py", *sys.argv[1:]], cwd=ROOT, env=project_environment(),
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    try:
        return process.wait()
    except KeyboardInterrupt:
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            return process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            return process.wait(timeout=15)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Startup step failed (exit {exc.returncode}). Fix the error above and rerun python dev.py.")
    except KeyboardInterrupt:
        raise SystemExit(130)
