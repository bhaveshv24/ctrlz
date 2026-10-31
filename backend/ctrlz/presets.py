"""Optional demonstration presets. The recovery core has no default demo application."""
from .models import Contract, Project


def campuspass_project(**values):
    defaults = {"adapter": "campuspass-v1", "token_env": "CAMPUSPASS_RECOVERY_TOKEN", "contract": Contract(allowed=["restore_checkout", "resume_worker", "retry_order"], approval_required=["resume_worker"], invariants=["no_duplicate_entitlements", "no_destructive_operations"])}
    return Project(**{**defaults, **values})
