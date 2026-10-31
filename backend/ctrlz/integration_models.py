from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Assertion(Spec):
    pointer: str = Field(pattern=r"^(/[^~]*(~[01][^~]*)*)?$", max_length=200)
    operator: Literal["eq", "in", "exists"] = "eq"
    value: Any = None
    label: str = Field(default="Configured assertion", max_length=120)

    @model_validator(mode="after")
    def scalar_values(self):
        valid = lambda v: v is None or type(v) in (str, int, float, bool)
        if self.operator == "in":
            if not isinstance(self.value, list) or not self.value or len(self.value) > 20 or not all(valid(v) for v in self.value):
                raise ValueError("in assertions require a bounded list of scalar values")
        elif not valid(self.value):
            raise ValueError("Assertions accept scalar values only")
        return self


class Parameter(Spec):
    kind: Literal["string", "integer", "boolean"] = "string"
    resource_bound: bool = False
    choices: list[str] = Field(default_factory=list, max_length=20)


class OperationSpec(Spec):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,60}$")
    description: str = Field(min_length=10, max_length=1000)
    path: str = Field(pattern=r"^/[a-zA-Z0-9/_-]+$", max_length=200)
    effect: Literal["restore", "restart", "resume", "retry", "reconfigure"]
    risk: Literal["low", "high"] = "high"
    idempotent: Literal[True] = True
    parameters: dict[str, Parameter] = Field(default_factory=dict, max_length=8)
    preconditions: list[Assertion] = Field(min_length=1, max_length=10)

    @field_validator("parameters")
    @classmethod
    def parameter_names(cls, value):
        import re
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,50}", k) or k in {"request_id", "expected_revision"} for k in value):
            raise ValueError("Invalid or reserved parameter name")
        return value


class HTTPIntegration(Spec):
    health_path: str = "/health"
    diagnostics_path: str | None = None
    workflow_path: str | None = None
    resource_path: str | None = None
    revision_pointer: str = "/revision"
    health_checks: list[Assertion] = Field(default_factory=list, max_length=10)
    service_checks: list[Assertion] = Field(default_factory=list, max_length=10)
    resource_checks: list[Assertion] = Field(default_factory=list, max_length=10)
    operations: list[OperationSpec] = Field(default_factory=list, max_length=12)

    @field_validator("health_path", "diagnostics_path", "workflow_path", "resource_path")
    @classmethod
    def relative_paths(cls, value):
        import re
        if value is not None:
            plain = value.replace("{resource}", "resource")
            if not re.fullmatch(r"/[a-zA-Z0-9/_-]*", plain) or ".." in plain or "//" in plain:
                raise ValueError("Paths must remain relative to the registered origin")
        return value

    @model_validator(mode="after")
    def consistency(self):
        if len({o.name for o in self.operations}) != len(self.operations):
            raise ValueError("Operation names must be unique")
        if self.operations and (not self.diagnostics_path or not self.service_checks):
            raise ValueError("Recovery operations need diagnostics/revision and explicit postconditions")
        if self.workflow_path and (not self.resource_path or not self.resource_checks):
            raise ValueError("Workflow monitoring requires a resource endpoint and acceptance assertions")
        return self
