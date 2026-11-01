"""Opt-in real Docker acceptance tests. No host execution of generated source."""
import os
import subprocess
from pathlib import Path
import pytest
from ctrlz.continuation import Continuation
from ctrlz.models import CodeProposal, FileChange, ImportRequest, Action, Candidate
from ctrlz.replay import Replay
from ctrlz.store import Store

pytestmark = pytest.mark.skipif(os.getenv("RUN_DOCKER_TESTS") != "1", reason="Set RUN_DOCKER_TESTS=1 with Docker and sandbox image ready")


async def test_traceback_recovery_preserves_contract_after_wrong_default_proposal(tmp_path):
    import io
    import zipfile
    from ctrlz.models import SourceEdit
    from ctrlz.repository import RepositoryImports
    source = 'def authorize(state):\n    if state == "approved":\n        raise ValueError("Approval required")\n    return True\n'
    tests = 'import pytest\nfrom logic import authorize\ndef test_approved(): assert authorize("approved")\ndef test_pending():\n    with pytest.raises(ValueError): authorize("pending")\n'
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr('logic.py', source)
        archive.writestr('test_logic.py', tests)
        archive.writestr('defaults.py', 'STATE = "approved"\n')
    root = tmp_path/'imports'
    snapshot = RepositoryImports(root).import_zip(data.getvalue())
    class WrongDefault:
        provider = 'Explicit wrong-root-cause regression fixture; no external model'
        async def code(self, request, files, baseline):
            return CodeProposal(diagnosis='Wrong default proposal', edits=[SourceEdit(path='defaults.py', before='STATE = "approved"', after='STATE = "pending"')])
    store = Store(f"sqlite:///{tmp_path/'recovery.db'}")
    incident, _ = store.create('code-import', 'code', snapshot['repository'], {})
    runner = Continuation(store, WrongDefault(), root, tmp_path/'artifacts')
    await runner.run(incident['id'], ImportRequest(repository=snapshot['repository']))
    result = store.get(incident['id'])
    assert result['status'] == 'resolved', result
    with zipfile.ZipFile(io.BytesIO(runner.repaired_archive(result))) as archive:
        assert b'state != "approved"' in archive.read('repaired-repository/logic.py')
        assert archive.read('repaired-repository/defaults.py') == b'STATE = "approved"\n'
        assert archive.read('repaired-repository/test_logic.py') == tests.encode()
    assert (Path(snapshot['repository'])/'logic.py').read_text() == source
    assert any(e['stage'] == 'guard_candidate_tests' and e['payload'].get('origin') == 'traceback_comparison_search' and e['payload']['passed'] for e in store.events())
    store.engine.dispose()


class CodeFixture:
    async def code(self, request, files, baseline):
        assert baseline["exit_code"] == 1
        return CodeProposal(diagnosis="Explicit test patch for a reproduced arithmetic defect", changes=[FileChange(path="maths.py", content="def add(a, b):\n    return a + b\n")])


@pytest.mark.parametrize("converter_failure", [False, True])
async def test_completion_extends_a_healthy_project_and_exports_zip(tmp_path, converter_failure):
    import io
    import zipfile
    from ctrlz.repository import RepositoryImports
    source = 'def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    raise NotImplementedError\n'
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr('maths.py', source)
        archive.writestr('test_maths.py', 'from maths import add\ndef test_add(): assert add(2, 3) == 5\n')
    root = tmp_path/'imports'
    snapshot = RepositoryImports(root).import_zip(data.getvalue())
    calls = []
    class CompletionFixture:
        provider = 'Explicit local completion fixture; no external model'
        async def code(self, request, files, baseline):
            calls.append(baseline.get('previous_attempt'))
            if converter_failure and len(calls) == 1:
                from crewai.utilities.converter import ConverterError
                raise ConverterError('Failed to convert text into CodeProposal: Use either changes or edits for each file, never both: maths.py')
            if converter_failure:
                assert 'schema_error' in baseline['previous_attempt']
                assert 'never the same path in both' in baseline['previous_attempt']['instruction']
            assert request.mode == baseline['mode'] == 'complete'
            assert baseline['exit_code'] == 0
            from ctrlz.models import SourceEdit
            return CodeProposal(diagnosis='Implement requested multiplication', edits=[SourceEdit(path='maths.py', before='raise NotImplementedError', after='return a * b')])
    store = Store(f"sqlite:///{tmp_path/'completion.db'}")
    incident, _ = store.create('project-completion', 'code', snapshot['repository'], {})
    runner = Continuation(store, CompletionFixture(), root, tmp_path/'artifacts')
    await runner.run(incident['id'], ImportRequest(repository=snapshot['repository'], mode='complete', requirements='Implement the unfinished multiplication function'))
    result = store.get(incident['id'])
    assert result['status'] == 'resolved', result
    assert result['verification']['checks']['baseline_established']
    assert len(calls) == (2 if converter_failure else 1)
    if converter_failure:
        assert any(e['stage'] == 'code_proposal_rejected' and 'schema_error' in e['payload'] for e in store.events())
    with zipfile.ZipFile(io.BytesIO(runner.repaired_archive(result))) as archive:
        assert b'return a * b' in archive.read('repaired-repository/maths.py')
    assert (Path(snapshot['repository'])/'maths.py').read_text() == source
    store.engine.dispose()


@pytest.mark.parametrize("first_invalid", [False, True])
async def test_real_worktree_sandbox_and_verified_artifact(tmp_path, first_invalid):
    repo = tmp_path / "imports" / "unfinished"
    repo.mkdir(parents=True)
    (repo / "maths.py").write_text("def add(a, b):\n    return a - b\n")
    (repo / "test_maths.py").write_text("from maths import add\ndef test_add():\n    assert add(2, 3) == 5\n")
    for args in (["git", "init"], ["git", "config", "core.autocrlf", "false"], ["git", "add", "."], ["git", "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", "unfinished"]):
        subprocess.run(args, cwd=repo, check=True, capture_output=True)
    store = Store(f"sqlite:///{tmp_path}/sandbox.db")
    incident, _ = store.create("code-import", "code", str(repo), {})
    class RevisingCodeFixture(CodeFixture):
        calls = 0
        async def code(self, request, files, baseline):
            self.calls += 1
            if first_invalid and self.calls == 1:
                return CodeProposal(diagnosis="Explicit invalid syntax fixture", changes=[FileChange(path="maths.py", content="def add(a, b):n return a + b")])
            if first_invalid:
                assert "SyntaxError" in baseline["previous_attempt"]["test_result"]["output"]
            return await super().code(request, files, baseline)
    fixture = RevisingCodeFixture()
    continuation = Continuation(store, fixture, tmp_path / "imports", tmp_path / "artifacts")
    previous_umask = os.umask(0o077)
    try:
        await continuation.run(incident["id"], ImportRequest(repository=str(repo), requirements="Fix addition and preserve the existing tests"))
    finally:
        os.umask(previous_umask)
    result = store.get(incident["id"])
    assert result["status"] == "resolved", result
    assert "return a + b" in result["patch"]
    assert result['download_ready'] is True
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(continuation.repaired_archive(result))) as archive:
        assert b'return a + b' in archive.read('repaired-repository/maths.py')
        assert archive.read('repaired-repository/test_maths.py') == (repo/'test_maths.py').read_bytes()
    assert "return a - b" in (repo / "maths.py").read_text()
    assert fixture.calls == (2 if first_invalid else 1)
    assert len(subprocess.check_output(["git", "worktree", "list"], cwd=repo, text=True).splitlines()) == 1
    store.engine.dispose()


async def test_replay_outage_in_disposable_compose(tmp_path, monkeypatch):
    campus = Path(__file__).resolve().parents[3] / "campuspass"
    if not (campus / "demo/docker-compose.replay.yml").is_file():
        pytest.skip("Complete sibling CampusPass checkout with controlled replay template required")
    monkeypatch.setenv("REPLAY_CAMPUSPASS_DIR", str(campus))
    store = Store(f"sqlite:///{tmp_path}/replay.db")
    incident, _ = store.create("demo", "outage", "service", {})
    await Replay(store).run(incident["id"], Candidate(id="restore", rationale="Test controlled checkout mitigation", actions=[Action(operation="restore_checkout")]))
    results = [e for e in store.events() if e["stage"] == "replay_result"]
    assert results, store.events()
    assert results[0]["payload"]["verification"]["passed"]
    assert results[0]["payload"]["production_mutated"] is False
    assert not any(e["stage"] == "replay_cleanup_required" for e in store.events())
    store.engine.dispose()


async def test_node_native_runner_and_new_source_module(tmp_path):
    import io, zipfile
    from ctrlz.repository import RepositoryImports
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('src/fees.mjs', "export function fee(cents) { return cents * 2; }\n")
        z.writestr('test/fees.test.mjs', "import {test} from 'node:test'; import assert from 'node:assert/strict'; import {fee} from '../src/fees.mjs'; test('round to integer cents',()=>assert.equal(fee(125),3)); test('zero amount',()=>assert.equal(fee(0),0));\n")
    imported=RepositoryImports(tmp_path/'imports').import_zip(archive.getvalue())
    class Fixture:
        async def code(self,request,files,baseline):
            assert baseline['profile']=='node-test'
            return CodeProposal(diagnosis='Use bounded fee rounding',changes=[FileChange(path='src/fees.mjs',content="import {round} from './round.mjs'; export function fee(cents) { return round(cents * .025); }\n"),FileChange(path='src/round.mjs',content='export const round = Math.round;\n')])
    store=Store(f'sqlite:///{tmp_path}/node.db'); incident,_=store.create('code-import','code',imported['repository'],{})
    await Continuation(store,Fixture(),tmp_path/'imports',tmp_path/'artifacts').run(incident['id'],ImportRequest(repository=imported['repository'],requirements='Fix the fee rounding regression and preserve zero behavior'))
    result=store.get(incident['id']); assert result['status']=='resolved',result
    assert 'src/round.mjs' in result['patch'] and result['verification']['passed']
    assert not (Path(imported['repository'])/'src/round.mjs').exists()
    store.engine.dispose()


async def test_typescript_locked_dependency_setup_and_offline_acceptance(tmp_path):
    import io,zipfile
    from ctrlz.repository import RepositoryImports
    from ctrlz.models import SourceEdit
    fixture=Path(__file__).resolve().parents[2]/'examples/invoice-typescript'
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:
        for path in fixture.rglob('*'):
            if path.is_file():z.writestr(path.relative_to(fixture).as_posix(),path.read_bytes())
    imported=RepositoryImports(tmp_path/'imports').import_zip(archive.getvalue())
    assert imported['supported'] and imported['dependency_install_required']
    class Fixture:
        async def code(self,request,files,baseline):
            assert len(baseline['cases'])==3 and 'expected' in baseline['output']
            return CodeProposal(diagnosis='Convert each price to cents',edits=[SourceEdit(path='src/money.ts',before='Math.round(amount)',after='Math.round(amount * 100)')])
    store=Store(f'sqlite:///{tmp_path}/typescript.db');incident,_=store.create('code-import','code',imported['repository'],{})
    await Continuation(store,Fixture(),tmp_path/'imports',tmp_path/'artifacts').run(incident['id'],ImportRequest(repository=imported['repository'],requirements='Repair invoice currency conversion and preserve acceptance',install_dependencies=True))
    result=store.get(incident['id']);assert result['status']=='resolved',result
    setup=next(e['payload'] for e in store.events() if e['stage']=='dependency_environment')
    assert setup['exit_code']==0 and setup['test_network']=='none'
    assert not any(e['stage']=='sandbox_cleanup_required' for e in store.events())
    store.engine.dispose()
