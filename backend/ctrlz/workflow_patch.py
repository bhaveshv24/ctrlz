"""Compile constrained AI hook plans, preserve business AST, test only in existing Docker sandboxes."""
import ast
import difflib
import json
import shutil
import zipfile
from pathlib import Path
from .repository import inspect_repository, test_file
from .sandbox import Sandbox
from .runtime_store import digest
from .workflow_source import tree_digest


def compile_patch(files,rule,plan,audit_id,approval_hash):
    if [h.model_dump() for h in plan.hooks]!=[h.model_dump() for h in rule.hooks]:
        raise ValueError('AI hook plan exceeds or differs from the exact approved scope')
    result=dict(files)
    if rule.instrumentation_driver=='campuspass_committed_session':return compile_session(files,rule,plan,audit_id,approval_hash)
    tag=digest({'approval':approval_hash,'hooks':[h.model_dump() for h in plan.hooks]})
    helper=Path(__file__).with_name('workflow_probe.py').read_text()
    helpers=set()
    for path in sorted({h.path for h in plan.hooks}):
        before=files[path]
        tree=ast.parse(before)
        if any(isinstance(n,ast.Name) and n.id=='_ctrlz_observe' for n in ast.walk(tree)):
            raise ValueError('Instrumentation alias already exists')
        lines=before.splitlines(keepends=True)
        insertions=[]
        for hook in [h for h in plan.hooks if h.path==path]:
            nodes=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==hook.function]
            if len(nodes)!=1:raise ValueError('Ambiguous function anchor')
            node=nodes[0]
            if node.decorator_list or any(isinstance(n,(ast.Yield,ast.YieldFrom)) for n in ast.walk(node)):
                raise ValueError('Decorated functions and generators need a different reviewed strategy')
            config={**hook.model_dump(exclude={'path','function'}),'audit_id':audit_id,'workflow_id':rule.id,'artifact_digest':tag}
            indent=' ' * node.col_offset
            insertions.append((node.lineno-1,indent+'@_ctrlz_observe(**'+repr(config)+')\n'))
        parent=Path(path).parent
        helper_path=(parent/'_ctrlz_observe.py').as_posix()
        if helper_path in files:raise ValueError('Supporting observability module would overwrite source')
        helpers.add(helper_path)
        prefix='.' if (parent/'__init__.py').as_posix() in files else ''
        offset=0
        for n,node in enumerate(tree.body):
            if n==0 and isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):offset=node.end_lineno
            elif isinstance(node,ast.ImportFrom) and node.module=='__future__':offset=node.end_lineno
            else:break
        insertions.append((offset,'from '+prefix+'_ctrlz_observe import observe as _ctrlz_observe\n'))
        for index,text in sorted(insertions,reverse=True):lines.insert(index,text)
        after=''.join(lines)
        validate_business_ast(before,after)
        result[path]=after
    for path in helpers:result[path]=helper
    diff=''.join(''.join(difflib.unified_diff(files.get(p,'').splitlines(True),result[p].splitlines(True),fromfile='a/'+p if p in files else '/dev/null',tofile='b/'+p)) for p in sorted(result) if result[p]!=files.get(p))
    return result,{'instrumentation_digest':tag,'source_digest':tree_digest(result),'changed_files':[p for p in result if result[p]!=files.get(p)],'diff':diff,'rationale':plan.rationale}


def compile_session(files,rule,plan,proposal_id,approval_hash):
    path='backend/campuspass/main.py';helper='backend/campuspass/_ctrlz_session_observer.py'
    if helper in files:raise ValueError('Generated session helper already exists')
    original=files[path];tree=ast.parse(original)
    factory=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='create_app'),None)
    if factory is None:raise ValueError('Expected application factory missing')
    returns=[n for n in factory.body if isinstance(n,ast.Return) and isinstance(n.value,ast.Name) and n.value.id=='app']
    if len(returns)!=1:raise ValueError('Ambiguous application return')
    tag=digest({'approval':approval_hash,'driver':'campuspass_committed_session','rule':rule.model_dump()})
    contract={'proposal_id':proposal_id,'workflow_id':rule.id,'artifact_digest':tag,'allowed_fields':rule.allowed_fields}
    lines=original.splitlines(True)
    lines.insert(returns[0].lineno-1,'    _ctrlz_session_attach(app, sessions, engine, '+repr(contract)+')\n')
    lines.insert(0,'from ._ctrlz_session_observer import attach as _ctrlz_session_attach\n')
    candidate=''.join(lines);check=ast.parse(candidate)
    check.body=check.body[1:]
    cf=next(n for n in check.body if isinstance(n,ast.FunctionDef) and n.name=='create_app')
    cf.body=[n for n in cf.body if not(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_ctrlz_session_attach')]
    if ast.dump(tree,include_attributes=False)!=ast.dump(check,include_attributes=False):raise ValueError('Business AST changed')
    result={**files,path:candidate,helper:Path(__file__).with_name('campuspass_observer_template.py').read_text()}
    diff=''.join(''.join(difflib.unified_diff(files.get(p,'').splitlines(True),result[p].splitlines(True),fromfile='a/'+p if p in files else '/dev/null',tofile='b/'+p)) for p in [path,helper])
    return result,{'instrumentation_digest':tag,'source_digest':tree_digest(result),'changed_files':[path,helper],'diff':diff,'rationale':plan.rationale,'driver':'campuspass_committed_session'}


def validate_business_ast(before,after):
    original=ast.parse(before);candidate=ast.parse(after)
    candidate.body=[n for n in candidate.body if not (isinstance(n,ast.ImportFrom) and n.module=='_ctrlz_observe' and len(n.names)==1 and n.names[0].name=='observe' and n.names[0].asname=='_ctrlz_observe')]
    for node in ast.walk(candidate):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            node.decorator_list=[d for d in node.decorator_list if not (isinstance(d,ast.Call) and isinstance(d.func,ast.Name) and d.func.id=='_ctrlz_observe')]
    if ast.dump(original,include_attributes=False)!=ast.dump(candidate,include_attributes=False):
        raise ValueError('Instrumentation changed the original business AST')


PROBE_TEST='''import importlib.util
from pathlib import Path
import pytest

def probe():
    path=next(Path('/workspace').rglob('_ctrlz_observe.py'))
    spec=importlib.util.spec_from_file_location('probe_under_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def config():
    return dict(audit_id='audit',workflow_id='flow',artifact_digest='a'*64,role='start',fields={'instance_id':'result.id'})

def test_observation_preserves_result_and_emits(monkeypatch):
    p=probe();events=[];monkeypatch.setenv('CTRLZ_OBSERVE_ENABLED','1');monkeypatch.setenv('CTRLZ_OBSERVE_REVISION','a'*40);monkeypatch.setattr(p,'_emit',events.append)
    value={'id':'job-1','amount':499}
    assert p.observe(**config())(lambda:value)() is value
    assert len(events)==1 and events[0]['workflow']['instance_id']=='job-1'
    assert 'amount' not in str(events[0])

def test_export_failure_preserves_outcome(monkeypatch):
    p=probe();monkeypatch.setenv('CTRLZ_OBSERVE_ENABLED','1');monkeypatch.setenv('CTRLZ_OBSERVE_REVISION','a'*40)
    def fail(event):raise RuntimeError('Exporter unavailable')
    monkeypatch.setattr(p,'_emit',fail)
    value={'id':'job-1'}
    assert p.observe(**config())(lambda:value)() is value

def test_original_exception_propagates(monkeypatch):
    p=probe();monkeypatch.setenv('CTRLZ_OBSERVE_ENABLED','1')
    error=ValueError('Original business failure')
    @p.observe(**config())
    def fail():raise error
    with pytest.raises(ValueError) as caught:fail()
    assert caught.value is error

def test_async_behavior_and_disabled_export(monkeypatch):
    import asyncio
    p=probe();events=[];monkeypatch.setenv('CTRLZ_OBSERVE_ENABLED','0');monkeypatch.setattr(p,'_emit',events.append)
    @p.observe(**config())
    async def work():return {'id':'job-1'}
    assert asyncio.run(work())=={'id':'job-1'} and events==[]
'''


def verify(files,candidate,directory,install_dependencies=False):
    directory=Path(directory);original=directory/'baseline';changed=directory/'candidate'
    for root,items in [(original,files),(changed,candidate)]:
        root.mkdir(parents=True,exist_ok=True)
        for path,content in items.items():
            target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
        # Import data remains read-only in containers, including immutable original tests.
        for p in root.rglob('*'):p.chmod(0o755 if p.is_dir() else 0o644)
        root.chmod(0o755)
    directory.chmod(0o755)
    base_root=original/'backend' if (original/'backend/pyproject.toml').is_file() and not (original/'pyproject.toml').exists() else original
    candidate_root=changed/'backend' if base_root!=original else changed
    inspection=inspect_repository(base_root)
    if inspection['profile']!='python-pytest' or not inspection['tests']:raise ValueError('Instrumentation verification currently requires original Python/pytest acceptance tests')
    baseline=Sandbox(base_root,'python-pytest',install_dependencies)
    instrumented=Sandbox(candidate_root,'python-pytest',install_dependencies)
    before_digest=tree_digest(files)
    try:
        setup=baseline.prepare(inspection)
        before=baseline.run()
        # Share only the isolated, explicitly approved dependency volume, not host dependencies.
        instrumented.volume=baseline.volume
        after=instrumented.run()
        identities=lambda r:{c['id']:c['status'] for c in r['cases']}
        checks={'original_tests_pass':before['exit_code']==0 and bool(before['cases']) and all(c['status']=='passed' for c in before['cases']),
                'same_original_tests':identities(before)==identities(after),
                'candidate_original_tests_pass':after['exit_code']==0 and bool(after['cases']),
                'original_snapshot_unchanged':tree_digest({p:(original/p).read_text() for p in files})==before_digest,
                'original_tests_immutable':all(candidate.get(p)==v for p,v in files.items() if test_file(p))}
        probe=SESSION_PROBE_TEST if any(p.endswith('_ctrlz_session_observer.py') for p in candidate) else PROBE_TEST
        dedicated_path=candidate_root/'tests/test_ctrlz_instrumentation.py' if (candidate_root/'tests').is_dir() else candidate_root/'test_ctrlz_instrumentation.py'
        if dedicated_path.exists():raise ValueError('Dedicated verification test would overwrite existing source')
        dedicated_path.write_text(probe)
        dedicated_path.chmod(0o644)
        dedicated=instrumented.run()
        checks['dedicated_instrumentation_tests_pass']=dedicated['exit_code']==0 and len(dedicated['cases'])>=len(after['cases'])+4 and all(c['status']=='passed' for c in dedicated['cases'])
        return {'passed':all(checks.values()),'checks':checks,'baseline':before,'candidate':after,'instrumentation':dedicated,'dependency_setup':setup,'network':'none','limitations':['Functional equivalence is supported by original tests and unchanged business AST, not mathematically guaranteed.','Nonblocking stdout is best-effort; lifecycle delivery alone cannot confirm a missing business outcome.']}
    finally:
        baseline.close()


def export(directory,candidate,patch):
    directory=Path(directory)
    (directory/'instrumentation.patch').write_text(patch['diff'])
    with zipfile.ZipFile(directory/'instrumented-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path,content in sorted(candidate.items()):archive.writestr(path,content)

SESSION_PROBE_TEST = '''import uuid
import pytest
from campuspass.main import create_app
from campuspass.db import Order,Job,Payment

@pytest.fixture
def observed(tmp_path,monkeypatch):
    for key,value in {'CTRLZ_WORKFLOW_ENABLED':'true','CTRLZ_APP_RECEIVER':'http://127.0.0.1:19998/app','CTRLZ_STATE_RECEIVER':'http://127.0.0.1:19998/state','CTRLZ_APP_SOURCE_TOKEN':'app-test','CTRLZ_STATE_SOURCE_TOKEN':'state-test','CTRLZ_DEPLOYED_REVISION':'b'*40}.items():monkeypatch.setenv(key,value)
    app=create_app('sqlite:///'+str(tmp_path/'orders.db'),worker=False)
    yield app,app.state.workflow_observer
    app.state.workflow_observer.close()

def purchase(app):
    with app.state.sessions.begin() as s:
        o=Order(request_id=uuid.uuid4().hex,event_id='agentathon',email='fixture@example.com');s.add(o);s.flush();identifier=o.id
        s.add_all([Payment(order_id=identifier,amount=499),Job(order_id=identifier)]);s.flush()
    return identifier

def test_committed_start_and_completed_event(observed):
    app,observer=observed;oid=purchase(app)
    start=observer.queue.get_nowait();assert start['workflow']['kind']=='workflow.started'
    assert start['workflow']['instance_id']==oid and 'fixture@example.com' not in str(start)
    from campuspass.worker import issue
    with app.state.sessions.begin() as s:issue(s,oid)
    assert observer.queue.get_nowait()['workflow']['kind']=='workflow.completed'

def test_targeted_read_verifies_entitlement(observed):
    app,observer=observed;oid=purchase(app)
    assert observer.lookup(oid)['state']=='pending'
    from campuspass.worker import issue
    with app.state.sessions.begin() as s:issue(s,oid)
    assert observer.lookup(oid)['state']=='completed'
    assert observer.lookup(str(uuid.uuid4())) is None

def test_rollback_emits_no_start(observed):
    app,observer=observed
    with pytest.raises(ValueError):
        with app.state.sessions.begin() as s:
            o=Order(request_id=uuid.uuid4().hex,event_id='agentathon',email='fixture@example.com');s.add(o);s.flush();s.add(Job(order_id=o.id));s.flush();raise ValueError('rollback')
    assert observer.queue.empty()

def test_observation_failure_does_not_break_business_commit(observed,monkeypatch):
    app,observer=observed
    def fail(value):raise RuntimeError('export down')
    monkeypatch.setattr(observer.queue,'put_nowait',fail)
    oid=purchase(app)
    assert observer.lookup(oid)['state']=='pending' and observer.metrics['events_dropped']==1
'''
