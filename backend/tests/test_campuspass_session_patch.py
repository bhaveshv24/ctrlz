import ast
from pathlib import Path
from test_workflow_observability import rule
from ctrlz.workflow_models import WorkflowRule,PatchPlan
from ctrlz.workflow_patch import compile_patch
from ctrlz.workflow_source import inspect,validate_rule


def test_committed_session_patch_preserves_factory_business_ast_and_models():
    campus=Path(__file__).resolve().parents[3]/'CampusPass'
    files={'backend/campuspass/'+p.name:p.read_text() for p in (campus/'backend/campuspass').glob('*.py')}
    r=rule().model_dump();r.update(instrumentation_driver='campuspass_committed_session',hooks=[],evidence=[{'path':'backend/campuspass/main.py','line':36}])
    contract=WorkflowRule.model_validate(r);validate_rule(contract,files,inspect(files))
    candidate,patch=compile_patch(files,contract,PatchPlan.model_construct(hooks=[],rationale='Explicit deterministic test plan'),'wf-'+'a'*24,'a'*64)
    assert patch['changed_files']==['backend/campuspass/main.py','backend/campuspass/_ctrlz_session_observer.py']
    assert candidate['backend/campuspass/db.py']==files['backend/campuspass/db.py']
    assert candidate['backend/campuspass/worker.py']==files['backend/campuspass/worker.py']
    assert candidate['backend/campuspass/ticket_reference.py']==files['backend/campuspass/ticket_reference.py']
    assert '_ctrlz_session_attach(app, sessions, engine,' in candidate['backend/campuspass/main.py']
    assert 'after_commit' in candidate['backend/campuspass/_ctrlz_session_observer.py']


def test_dedicated_tests_respect_original_pytest_testpaths(tmp_path,monkeypatch):
    from ctrlz.workflow_patch import verify
    from ctrlz.workflow_models import PatchPlan
    from test_workflow_observability import FILES,rule
    import os,subprocess,pytest
    monkeypatch.setenv('DOCKER_HOST','unix:///run/user/'+str(os.getuid())+'/docker.sock')
    if subprocess.run(['docker','image','inspect','ctrlz-sandbox:local'],capture_output=True).returncode:pytest.skip('Existing Python sandbox unavailable')
    files={k:v for k,v in FILES.items() if k!='test_jobs.py'}
    files['tests/test_jobs.py']=FILES['test_jobs.py']
    files['pyproject.toml']='[tool.pytest.ini_options]\ntestpaths=["tests"]\n'
    r=rule();candidate,_=compile_patch(files,r,PatchPlan(hooks=r.hooks,rationale='Deterministic regression fixture'),'wf-'+'c'*24,'a'*64)
    result=verify(files,candidate,tmp_path/'verify')
    assert result['passed'] and len(result['instrumentation']['cases'])==9,result
