"""Run CtrlZ locally and shut down all launched services together."""
import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def stop_services(processes):
    for process in processes:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 10
    for process in processes:
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campuspass", action="store_true")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=5173)
    args = parser.parse_args()
    ctrlz = Path(__file__).resolve().parents[1]
    services = [(ctrlz, "ctrlz", args.api_port, args.web_port)]
    if args.campuspass:
        services.append((ctrlz.parent / "campuspass", "campuspass", 8001, 5174))
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        parser.error("Install Node.js and npm first.")
    ports = set()
    for root, package, api_port, web_port in services:
        if not (root / ".env").is_file():
            parser.error(f"Missing {root / '.env'}. Run scripts/setup_env.py first.")
        if not (root / "frontend/node_modules/vite").is_dir():
            parser.error(f"Run npm --prefix {root / 'frontend'} ci first.")
        for port in (api_port, web_port):
            if not 1 <= port <= 65535 or port in ports:
                parser.error(f"Invalid or duplicate port {port}.")
            ports.add(port)
            try:
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", port))
            except OSError:
                parser.error(
                    f"Port {port} is already in use. Stop its service or choose "
                    "--api-port and --web-port."
                )
    processes = []
    previous_term = signal.getsignal(signal.SIGTERM)

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        for root, package, api_port, web_port in services:
            python = sys.executable
            if root != ctrlz:
                python = str(root / "backend/.venv" / (
                    "Scripts/python.exe" if os.name == "nt" else "bin/python"
                ))
            commands = [
                ([python, "-m", "uvicorn", package + ".main:create_app",
                  "--factory", "--host", "127.0.0.1", "--port", str(api_port),
                  "--env-file", "../.env"], root / "backend"),
                ([npm, "run", "dev", "--", "--port", str(web_port),
                  "--strictPort"], root / "frontend"),
            ]
            environment = {**os.environ, "CTRLZ_PROXY_TARGET": f"http://127.0.0.1:{api_port}"}
            for command, directory in commands:
                processes.append(subprocess.Popen(
                    command,
                    cwd=directory,
                    env=environment,
                    start_new_session=os.name != "nt",
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                ))
            print(
                f"Starting {package}: http://localhost:{web_port} "
                f"| API: http://127.0.0.1:{api_port}/docs",
                flush=True,
            )
        print("Ctrl+C stops all launched services.", flush=True)
        while True:
            for process in processes:
                result = process.poll()
                if result is not None:
                    raise SystemExit(f"A development service exited ({result}); stopping the others.")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping local services...", flush=True)
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        stop_services(processes)
        signal.signal(signal.SIGTERM, previous_term)


if __name__ == "__main__":
    main()
