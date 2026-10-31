"""Reviewed workflow contracts. No expressions, commands, SQL or URLs are executable inputs."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ID=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$'
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)

class WorkflowLimits(BaseSettings):
    model_config=SettingsConfigDict(env_prefix='CTRLZ_WORKFLOW_',extra='ignore',hide_input_in_errors=True)
    retention_days:int=Field(default=7,ge=1,le=90)
    maximum_records:int=Field(default=100000,ge=1000,le=1000000)

def safe_path(value):
    from .runtime_models import StackFrame
    StackFrame.safe_path(value)

FIELDS = {'instance_id', 'resource_id', 'request_id', 'trace_id', 'user_id', 'parent_id'}


class Location(Strict):
    path: str = Field(max_length=300)
    line: int = Field(ge=1)
    @model_validator(mode='after')
    def valid(self):
        safe_path(self.path)
        return self


class Hook(Strict):
    path: str = Field(max_length=300)
    function: str = Field(pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    role: Literal['start', 'complete']
    fields: dict[str, str] = Field(max_length=6,description='instance_id is mandatory. Keys are normalized telemetry fields; values are actual arg.PARAM or result.KEY source paths.',
        json_schema_extra={'properties':{name:{'type':'string','pattern':r'^(arg|result)\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$','description':'A source dictionary path, for example result.id or arg.job_id; never prose or an expression.'} for name in sorted(FIELDS)},'required':['instance_id'],'additionalProperties':False})
    completion_key: str | None = Field(default=None, pattern=r'^result\.[A-Za-z_][A-Za-z0-9_]*$')
    completion_value: str | None = Field(default=None, max_length=80)
    @model_validator(mode='after')
    def bounded(self):
        import re
        safe_path(self.path)
        if not set(self.fields) <= FIELDS or 'instance_id' not in self.fields:
            raise ValueError('An actual instance identifier and approved data fields are required')
        if any(not re.fullmatch(r'(?:arg|result)\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?', x) for x in self.fields.values()):
            raise ValueError('Only bounded argument/result dictionary paths are supported')
        if any(re.search(r'password|secret|token|email|cookie|authorization|body|ip_address',x,re.I) for x in self.fields.values()):
            raise ValueError('Sensitive argument/result mappings cannot be instrumented')
        if self.role == 'complete' and (not self.completion_key or self.completion_value is None):
            raise ValueError('Completion hooks require an explicit returned-state predicate')
        return self


class WorkflowRule(Strict):
    id: str = Field(pattern=ID)
    name: str = Field(min_length=1,max_length=150)
    description: str = Field(min_length=1,max_length=2000)
    evidence: list[Location] = Field(min_length=1,max_length=12)
    start_condition: str = Field(min_length=1,max_length=1500)
    completion_condition: str = Field(min_length=1,max_length=1500)
    failure_conditions: list[str] = Field(max_length=8)
    existing_signals: list[str] = Field(max_length=8)
    missing_signals: list[str] = Field(max_length=8)
    classification: Literal['confirmed_gap','suspected_gap','possible_gap','sufficient','insufficient']
    technique: Literal['existing_telemetry','zero_code','read_only_reconciliation','instrumentation','insufficient']
    deadline_seconds: int = Field(default=60,ge=1,le=86400)
    allowed_fields: list[Literal['instance_id','resource_id','request_id','trace_id','user_id','parent_id']] = Field(min_length=1,max_length=6)
    hooks: list[Hook] = Field(default_factory=list,max_length=4)
    uncertainties: list[str] = Field(min_length=1,max_length=10)
    privacy: str = Field(min_length=1,max_length=2000)
    overhead: str = Field(min_length=1,max_length=1000)
    permissions: list[str] = Field(max_length=8)
    independent_verification: str = Field(min_length=1,max_length=1500)
    coverage_limits: list[str] = Field(min_length=1,max_length=10)
    @model_validator(mode='before')
    @classmethod
    def narrow_unapproved_optional_mappings(cls,value):
        # A proposal is not yet approved. Narrow redundant AI mappings to its
        # declared privacy scope rather than silently broadening that scope.
        if not isinstance(value,dict):return value
        import copy
        value=copy.deepcopy(value);allowed=set(value.get('allowed_fields',[]));removed=set()
        for hook in value.get('hooks',[]):
            if not isinstance(hook,dict) or not isinstance(hook.get('fields'),dict):continue
            removed.update(set(hook['fields'])-allowed)
            hook['fields']={k:v for k,v in hook['fields'].items() if k in allowed}
            # A job ID is not evidence of a user or request identity. Omit an
            # unsupported optional association rather than inventing one.
            identifiers={'user_id':{'user_id','customer_id','account_id','subject_id'},'resource_id':{'resource_id','order_id','document_id','file_id','reservation_id'},'request_id':{'request_id'},'trace_id':{'trace_id'}}
            for field,path in list(hook['fields'].items()):
                if field in identifiers and isinstance(path,str) and path.split('.')[-1] not in identifiers[field] and not __import__('re').search('password|secret|token|email|cookie|authorization|body|ip_address',path,__import__('re').I):
                    removed.add(field+' (unsupported association)');del hook['fields'][field]
        if removed:
            value['coverage_limits']=list(value.get('coverage_limits',[]))[:9]+['Privacy normalization removed optional hook fields outside the proposed collection scope: '+', '.join(sorted(removed))+'. Review the remaining fields before approval.']
        return value
    @model_validator(mode='after')
    def consistent(self):
        if 'instance_id' not in self.allowed_fields or len(set(self.allowed_fields))!=len(self.allowed_fields):
            raise ValueError('Unique fields must include instance_id')
        if any(not set(h.fields)<=set(self.allowed_fields) for h in self.hooks):
            raise ValueError('Hook fields exceed the proposed privacy scope')
        if self.technique=='instrumentation' and (not self.hooks or not any(h.role=='start' for h in self.hooks)):
            raise ValueError('Instrumentation needs an explicit start anchor')
        if self.technique=='instrumentation' and (self.classification not in {'confirmed_gap','suspected_gap','possible_gap'} or not self.missing_signals):
            raise ValueError('Do not generate instrumentation when no actual observability gap is proposed')
        if len({(h.path,h.function) for h in self.hooks})!=len(self.hooks):raise ValueError('Duplicate function hooks are unsupported')
        return self


class AuditAssessment(Strict):
    summary: str = Field(min_length=1,max_length=5000)
    workflows: list[WorkflowRule] = Field(max_length=8)
    limitations: list[str] = Field(min_length=1,max_length=10)


class AuditRequest(Strict):
    deployment_id: str = Field(pattern=ID)
    source_id: str = Field(pattern=ID)


class RuleDecision(Strict):
    proposal_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['approve','reject','edit']
    rule: WorkflowRule | None = None


class GenerationRequest(Strict):
    approval_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    install_dependencies: bool = False


class PatchPlan(Strict):
    hooks: list[Hook] = Field(min_length=1,max_length=4)
    rationale: str = Field(min_length=1,max_length=3000)

class PatchSelection(Strict):
    hook_indices:list[int]=Field(min_length=1,max_length=4,description='Indices into the approved hooks, in the same order. Select every approved hook; do not invent or rewrite mappings.')
    rationale:str=Field(min_length=1,max_length=3000)


class Activation(Strict):
    approval_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    revision: str = Field(pattern=r'^(?:[a-f0-9]{40}|sha256:[a-f0-9]{64})$')
    artifact_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    reconciliation_source_id: str | None = Field(default=None,pattern=ID)


class WorkflowSignal(Strict):
    audit_id: str = Field(pattern=ID)
    workflow_id: str = Field(pattern=ID)
    kind: Literal['workflow.started','workflow.completed','workflow.failed','workflow.cancelled','workflow.timeout','workflow.reconciliation_failed','workflow.reconciled','workflow.heartbeat']
    instance_id: str | None = Field(default=None,pattern=ID)
    resource_id: str | None = Field(default=None,pattern=ID)
    parent_id: str | None = Field(default=None,pattern=ID)
    artifact_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    revision: str = Field(pattern=r'^(?:[a-f0-9]{40}|sha256:[a-f0-9]{64})$')
    started_at: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    state: Literal['pending','running','completed','failed','cancelled','unknown'] | None = None
    error_class: str | None = Field(default=None,max_length=100,pattern=ID)
