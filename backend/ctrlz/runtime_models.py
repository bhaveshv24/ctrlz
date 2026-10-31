"""Explicit repository/deployment contracts; telemetry never grants execution."""
import re
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .github import normalize_github

ID = r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$"
SHA = r"^[0-9a-f]{40}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class TelemetrySource(Strict):
    id: str = Field(pattern=ID)
    connector: Literal["generic-events", "vercel-drain"] = "generic-events"


class Deployment(Strict):
    id: str = Field(pattern=ID)
    platform: Literal["local", "vps", "docker", "vercel", "aws"]
    service_id: str = Field(min_length=1, max_length=100, pattern=ID)
    environment: str = Field(pattern=ID)
    application_url: str | None = Field(default=None, max_length=500)
    deployment_ref: str | None = Field(default=None, pattern=ID)
    commit_sha: str | None = Field(default=None, pattern=SHA)
    sources: list[TelemetrySource] = Field(min_length=1, max_length=5)
    vercel_team_id: str | None = Field(default=None, pattern=ID)
    source_paths: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("source_paths")
    @classmethod
    def source_hints(cls, values):
        for value in values:
            StackFrame.safe_path(value)
        return values

    @field_validator("application_url")
    @classmethod
    def display_url(cls, value):
        if value:
            u = urlsplit(value)
            if u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password or u.query or u.fragment:
                raise ValueError("Use an application URL without credentials or query; CtrlZ will not fetch it")
        return value

    @model_validator(mode="after")
    def source_contract(self):
        if len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("Source IDs must be unique per deployment")
        if any(s.connector == "vercel-drain" for s in self.sources) and self.platform != "vercel":
            raise ValueError("Vercel drains require a Vercel deployment")
        return self


class RepositoryMonitoring(Strict):
    github_url: str = Field(max_length=500)
    preferred_ref: str | None = Field(default=None, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,99}$")
    deployments: list[Deployment] = Field(min_length=1, max_length=12)

    @field_validator("github_url")
    @classmethod
    def github(cls, value):
        return normalize_github(value)["url"]

    @model_validator(mode="after")
    def unique_deployments(self):
        if len({d.id for d in self.deployments}) != len(self.deployments):
            raise ValueError("Deployment IDs must be unique")
        return self


class StackFrame(Strict):
    path: str = Field(min_length=1, max_length=300)
    line: int = Field(ge=1, le=100000)
    function: str | None = Field(default=None, max_length=120)

    @field_validator("path")
    @classmethod
    def safe_path(cls, value):
        from pathlib import PurePosixPath
        p = PurePosixPath(value)
        if p.is_absolute() or "\\" in value or any(part in {"..", ".git"} or ":" in part for part in p.parts) or any(ord(c) < 32 for c in value):
            raise ValueError("Stack paths must be repository-relative")
        if p.name.startswith(".env") or p.suffix in {".pem", ".key", ".db"}:
            raise ValueError("Sensitive source path")
        return value


class RuntimeEvent(Strict):
    event_id: str = Field(pattern=ID)
    timestamp: float = Field(ge=0, allow_inf_nan=False)
    timestamp_kind: Literal["occurred", "observed"] = "occurred"
    severity: Literal["debug", "info", "warning", "error", "fatal"]
    error_type: str | None = Field(default=None, max_length=120)
    message: str = Field(max_length=8000)
    stack: str | None = Field(default=None, max_length=16000)
    frames: list[StackFrame] = Field(default_factory=list, max_length=12)
    http_status: int | None = Field(default=None, ge=100, le=599)
    route: str | None = Field(default=None, max_length=300)
    request_id: str | None = Field(default=None, max_length=128, pattern=ID)
    trace_id: str | None = Field(default=None, max_length=128, pattern=ID)
    user_id: str | None = Field(default=None, max_length=200)
    session_id: str | None = Field(default=None, max_length=200)
    deployment_ref: str | None = Field(default=None, pattern=ID)
    commit_sha: str | None = Field(default=None, pattern=SHA)
    evidence_ref: str | None = Field(default=None, max_length=300)
    workflow: 'WorkflowSignal | None' = None


class EventBatch(Strict):
    events: list[RuntimeEvent] = Field(min_length=1, max_length=50)


class Recommendation(Strict):
    id: str = Field(pattern=ID)
    category: Literal["code_patch", "rollback", "service_recovery", "configuration", "dependency_investigation", "escalation"]
    summary: str = Field(min_length=1, max_length=2000)
    rationale: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    risks: list[str] = Field(default_factory=list, max_length=8)
    proposed_change: str | None = Field(default=None, max_length=5000)
    verification_plan: list[str] = Field(min_length=1, max_length=10)


class RuntimeAssessment(Strict):
    diagnosis: str = Field(min_length=1, max_length=10000)
    uncertainties: list[str] = Field(min_length=1, max_length=10)
    recommendations: list[Recommendation] = Field(min_length=1, max_length=6)


# Imported after the common Strict/ID definitions to keep the additive schema acyclic.
from .workflow_models import WorkflowSignal
RuntimeEvent.model_rebuild()
