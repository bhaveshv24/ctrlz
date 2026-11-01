"""Read-only runtime checks. No user-supplied commands or recovery actions."""
import importlib.metadata
import shutil
import subprocess

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def installed(distribution):
    try:
        return {"state": "available", "version": importlib.metadata.version(distribution)}
    except importlib.metadata.PackageNotFoundError:
        return {"state": "unavailable", "detail": "Package is not installed"}


def command_status(arguments):
    if not shutil.which(arguments[0]):
        return {"state": "unavailable", "detail": "Executable is not installed"}
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=6)
        if result.returncode:
            return {"state": "unavailable", "detail": "Command failed or daemon is not reachable"}
        return {"state": "available", "detail": result.stdout.strip()[:160]}
    except (OSError, subprocess.TimeoutExpired):
        return {"state": "unavailable", "detail": "Command did not complete within its budget"}


def inspect_runtime(settings, store, runbooks, reasoner):
    components = [
        {"name": name, **installed(package)}
        for name, package in [
            ("FastAPI", "fastapi"), ("CrewAI and Flows", "crewai"),
            ("Pydantic Settings", "pydantic-settings"), ("SQLAlchemy", "sqlalchemy"),
            ("ChromaDB", "chromadb"), ("HTTPX", "httpx"),
        ]
    ]
    try:
        with store.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        components.append({"name": "Workspace database", "state": "available", "detail": "Read query completed"})
    except SQLAlchemyError:
        components.append({"name": "Workspace database", "state": "unavailable", "detail": "Read query failed"})
    collection = getattr(runbooks, "collection", None)
    try:
        count = collection.count() if collection is not None else None
        components.append({
            "name": "Indexed runbooks",
            "state": "available" if count else "unavailable",
            "detail": f"{count} documents indexed" if count is not None else "Collection is not available",
        })
    except Exception:
        components.append({"name": "Indexed runbooks", "state": "unavailable", "detail": "Collection could not be read"})
    components.append({"name": "Git", **command_status(["git", "--version"])})
    if settings.CTRLZ_CODE_EXECUTION_ENABLED:
        docker = command_status(["docker", "version", "--format", "{{.Server.Version}}"])
        components.append({"name": "Docker daemon", **docker})
        if docker["state"] == "available":
            from .repository import PROFILES
            for profile in PROFILES.values():
                components.append({
                    "name": profile["label"] + " sandbox",
                    **command_status(["docker", "image", "inspect", profile["image"], "--format", "{{.Id}}"]),
                })
    else:
        components.append({"name": "Docker execution", "state": "disabled", "detail": "Disabled by host configuration"})
    components.extend([
        {"name": "NVIDIA NIM", "state": "configured" if settings.NVIDIA_API_KEY.get_secret_value() else "unconfigured",
         "detail": getattr(reasoner, "selected_model", None) or "No model selected", "verified": False},
    ])
    return {"components": components}


def execution_readiness(enabled):
    """Probe the actual isolation boundary, not only the configured feature flag."""
    if not enabled:
        return {'available': False, 'reason': 'Repository execution is disabled on this host. Static inspection remains available.'}
    daemon = command_status(['docker', 'version', '--format', '{{.Server.Version}}'])
    if daemon['state'] != 'available':
        return {'available': False, 'reason': 'This backend cannot reach a Docker sandbox runner. Hosted inspection works, but tests, repair and completion require a Docker-capable backend.'}
    return {'available': True, 'reason': 'Docker daemon is reachable. The selected profile image and dependency setup are checked during inspection.'}
