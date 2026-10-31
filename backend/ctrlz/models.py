from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .integration_models import HTTPIntegration


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Contract(Strict):
    allowed: list[str] = Field(default_factory=list)
    approval_required: list[str] = Field(default_factory=list)
    max_actions: int = Field(default=3, ge=1, le=5)
    invariants: list[Literal["no_duplicate_entitlements", "no_destructive_operations", "idempotent_mutations"]] = Field(default_factory=lambda: ["no_destructive_operations", "idempotent_mutations"])

    @field_validator("invariants")
    @classmethod
    def required_invariants(cls, values):
        if "no_destructive_operations" not in values:
            raise ValueError("The non-destructive operations invariant is mandatory")
        return values


class Project(Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,40}$")
    name: str = Field(min_length=1, max_length=100)
    base_url: str
    adapter: Literal["generic-http-v1", "campuspass-v1"] = "generic-http-v1"
    token_env: str = Field(default="SERVICE_RECOVERY_TOKEN", pattern=r"^[A-Z][A-Z0-9_]{1,80}$")
    contract: Contract = Field(default_factory=Contract)
    integration: HTTPIntegration = Field(default_factory=HTTPIntegration)
    timeout_seconds: float = Field(default=2, ge=0.1, le=30)
    latency_ms: int = Field(default=1500, ge=50, le=30000)
    enabled: bool = True
    demo_enabled: bool = False

    @model_validator(mode="after")
    def registered_operations(self):
        if self.adapter == "generic-http-v1":
            registered = {o.name for o in self.integration.operations}
            if not set(self.contract.allowed).issubset(registered):
                raise ValueError("Every allowed operation needs a registered HTTP operation specification")
            if not set(self.contract.approval_required).issubset(registered):
                raise ValueError("Approval rules must reference registered operations")
            if self.demo_enabled:
                raise ValueError("Generic services do not expose the CampusPass demo fault controls")
        return self

    @field_validator("base_url")
    @classmethod
    def origin(cls, value):
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("Use an HTTP origin without credentials, path, or query")
        return value.rstrip("/")


class Action(Strict):
    operation: str = Field(min_length=1, max_length=80)
    order_id: str | None = Field(default=None, max_length=100)
    parameters: dict[str, str | int | bool] = Field(default_factory=dict, max_length=8)


class Candidate(Strict):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    rationale: str = Field(min_length=1, max_length=3000)
    actions: list[Action] = Field(max_length=5)
    risks: list[str] = Field(default_factory=list, max_length=10)


class RecoveryPlan(Strict):
    diagnosis: str = Field(min_length=1, max_length=10000)
    evidence_ids: list[str] = Field(default_factory=list)
    candidates: list[Candidate] = Field(min_length=2, max_length=5)


class ImportRequest(Strict):
    @model_validator(mode="before")
    @classmethod
    def discard_legacy_model_override(cls, value):
        if isinstance(value, dict):
            return {key: item for key, item in value.items() if key != "model"}
        return value

    repository: str
    requirements: str = Field(min_length=10, max_length=20000)
    context: str = Field(default="", max_length=20000)
    acceptance_profile: Literal["auto", "python-pytest", "node-test", "javascript-vitest"] = "auto"
    install_dependencies: bool = False


class FileChange(Strict):
    path: str
    content: str = Field(max_length=50000)


class SourceEdit(Strict):
    path: str
    before: str = Field(min_length=1, max_length=12000)
    after: str = Field(max_length=18000)


class RequirementFinding(Strict):
    requirement: str = Field(min_length=1, max_length=1000)
    status: Literal["implemented", "incomplete", "unknown"]
    evidence_paths: list[str] = Field(default_factory=list, max_length=20)
    explanation: str = Field(max_length=2000)


class CodeProposal(Strict):
    requirements: list[RequirementFinding] = Field(default_factory=list, max_length=50)
    continuation_plan: list[str] = Field(default_factory=list, max_length=20)
    diagnosis: str
    changes: list[FileChange] = Field(default_factory=list, max_length=8)
    edits: list[SourceEdit] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.changes and not self.edits:
            raise ValueError("A proposal must contain a source change or exact text edit")
        if len({c.path for c in self.changes} | {e.path for e in self.edits}) > 8:
            raise ValueError("At most eight source files may change")
        return self
