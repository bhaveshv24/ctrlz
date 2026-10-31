"""Scenario descriptions derived from managed snapshots and configured service contracts."""
from .settings import Settings
from .repository import inspect_repository
from .demo_repository import mutation


def repository_target(repo):
    assessment = inspect_repository(repo)
    reason = '; '.join(assessment['warnings']) if not assessment['supported'] else None
    candidate = mutation(repo, assessment) if not reason else None
    facts = {k:assessment[k] for k in ['profile','profile_label','test_file_count','tests','editable_files','source_count','dependency_install_required','warnings']}
    return {'id':str(repo), 'kind':'repository', 'name':repo.name, 'facts':facts, 'scenarios':[
        {'id':'repair','title':f"Repair · {assessment['profile_label']}",'description':f"{assessment['test_file_count']} detected test files; {assessment['source_count']} editable source files. Reproduce an existing failure and produce a verified patch.",'disabled_reason':reason},
        {'id':'injected','title':'Disclosed injected regression','description':'Prove the original tests pass, mutate one non-test source file in a separate copy, prove the same tests fail, then run normal repair. The original snapshot stays untouched.','disabled_reason':reason or (None if candidate else 'No supported deterministic comparison or standalone boolean return mutation found.')}
    ]}


def service_target(project):
    campus = project['adapter'] == 'campuspass-v1'
    integration = project.get('integration',{})
    facts = {'adapter':project['adapter'],'origin':project['base_url'],'health_path':'/health' if campus else integration.get('health_path'), 'workflow_path':'/workflows' if campus else integration.get('workflow_path'), 'operations':project['contract']['allowed'] if campus else [o['name'] for o in integration.get('operations',[])], 'contract':project['contract'],'monitoring_enabled':project['enabled']}
    if campus:
        reason = 'Enable environment demo controls.' if not Settings().CTRLZ_DEMO_CONTROLS_ENABLED else 'Opt this project into demo faults.' if not project.get('demo_enabled') else 'Enable monitoring for this project.' if not project['enabled'] else None
        scenarios = [{'id':'outage','title':'C · Checkout goes dark.','description':'CampusPass checkout outage; independent monitoring and recovery.','disabled_reason':reason}, {'id':'workflow','title':'B · Paid. Still no ticket.','description':'CampusPass paused worker and simulated paid order without entitlement; no money is charged.','disabled_reason':reason}]
    else:
        scenarios = [{'id':'monitor','title':'Monitor configured health','description':f"Observe {facts['health_path']} using the registered monitoring configuration.",'disabled_reason':None if project['enabled'] else 'Enable monitoring in project settings first.'}, {'id':'contract','title':'Review recovery contract','description':f"{len(facts['operations'])} registered operations; inspect permissions, approval rules and invariants.",'disabled_reason':None}, {'id':'fault','title':'Controlled fault injection','description':'This integration has no registered demo fault controls.','disabled_reason':'Generic HTTP services do not expose CampusPass fault controls.'}]
    return {'id':project['id'],'kind':'service','name':project['name'],'facts':facts,'scenarios':scenarios}
