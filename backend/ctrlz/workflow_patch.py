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
    inspection=inspect_repository(original)
    if inspection['profile']!='python-pytest' or not inspection['tests']:raise ValueError('Instrumentation verification currently requires original Python/pytest acceptance tests')
    baseline=Sandbox(original,'python-pytest',install_dependencies)
    instrumented=Sandbox(changed,'python-pytest',install_dependencies)
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
        (changed/'test_ctrlz_instrumentation.py').write_text(PROBE_TEST)
        (changed/'test_ctrlz_instrumentation.py').chmod(0o644)
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
