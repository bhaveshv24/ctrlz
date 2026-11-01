import copy
import pytest
from ctrlz.workflow_revision import verify_unchanged_observer,MAIN,DB,HELPER
from ctrlz.workflow_models import Activation,RuleDecision
from test_workflow_observability import env,active,OP

FILES={MAIN:'from ._ctrlz_session_observer import attach as _ctrlz_session_attach\ndef create_app():\n    _ctrlz_session_attach(app, sessions, engine, {"proposal_id":"approved"})\n',DB:'\n'.join('class '+n+':\n    order_id: str\n' for n in ['Order','Payment','Job','Ticket']),HELPER:'def attach(*args):\n    return None\n'}

def test_observer_reuse_accepts_unrelated_business_changes_only_with_same_mapping():
    candidate=copy.deepcopy(FILES);candidate[MAIN]+='def new_demo_control():\n    return "disabled by default"\n';candidate[DB]+='class DemoFault:\n    pass\n'
    assert verify_unchanged_observer(FILES,candidate)['observer_sha256']

@pytest.mark.parametrize('change',[HELPER,DB,MAIN])
def test_observer_reuse_rejects_changed_observer_mapping_or_attachment(change):
    candidate=copy.deepcopy(FILES)
    if change==HELPER:candidate[change]+='\n# modified observer'
    elif change==DB:candidate[change]=candidate[change].replace('order_id: str','other_id: str')
    else:candidate[change]=candidate[change].replace('"approved"','"different"')
    with pytest.raises(ValueError):verify_unchanged_observer(FILES,candidate)

async def test_reused_observer_requires_new_approval_and_exact_reviewed_revision(env,monkeypatch):
    p=await active(env,monkeypatch);app,c,*_=env;w=app.state.workflows
    # Explicit state-machine unit fixture, not a real provider/source verification.
    p['rule'].update(technique='existing_telemetry',hooks=[],classification='sufficient',missing_signals=[])
    p.update(status='proposed',approval=None,activation=None,revision_review={'revision':'b'*40,'artifact_digest':'c'*64})
    p['proposal_hash']=w.binding(p,p['rule']);w.save_proposal(p)
    payload={'approval_hash':'a'*64,'revision':'b'*40,'artifact_digest':'c'*64,'reconciliation_source_id':'state','check_mode':'deadline_targeted'}
    assert (await c.post('/workflow-proposals/'+p['id']+'/activate',headers=OP,json=payload)).status_code==409
    r=await c.post('/workflow-proposals/'+p['id']+'/decision',headers=OP,json={'proposal_hash':p['proposal_hash'],'decision':'approve'});assert r.status_code==200
    payload['approval_hash']=r.json()['approval']['hash'];payload['revision']='d'*40
    assert (await c.post('/workflow-proposals/'+p['id']+'/activate',headers=OP,json=payload)).status_code==409
    assert (await c.post('/workflow-proposals/'+p['id']+'/revision-review',json={'revision':'b'*40})).status_code==401
    assert (await c.post('/workflow-proposals/'+p['id']+'/revision-review',headers=OP,json={'revision':'b'*40,'command':'arbitrary'})).status_code==422
