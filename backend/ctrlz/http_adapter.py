"""Configurable same-origin HTTP recovery. Application vocabulary lives in contracts."""
import asyncio
import os
import re
import time
from urllib.parse import quote
import httpx


def pointer(document, path):
    value = document
    try:
        for part in path.split('/')[1:] if path else []:
            part = part.replace('~1', '/').replace('~0', '~')
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value
    except (KeyError, IndexError, ValueError, TypeError):
        return None


def assertion(document, rule):
    value = pointer(document, rule.pointer)
    if rule.operator == 'exists':
        return value is not None
    if rule.operator == 'in':
        return any(type(value) is type(expected) and value == expected for expected in rule.value)
    return type(value) is type(rule.value) and value == rule.value


class HTTPAdapter:
    def __init__(self, project, client):
        self.project, self.client = project, client

    @property
    def operations(self):
        return {op.name: op for op in self.project.integration.operations}

    @property
    def operation_semantics(self):
        return {op.name: {'description': op.description, 'effect': op.effect, 'risk': op.risk, 'parameters': {k: v.model_dump() for k, v in op.parameters.items()}, 'preconditions': [p.model_dump() for p in op.preconditions]} for op in self.operations.values()}

    @property
    def headers(self):
        return {'X-Recovery-Token': os.getenv(self.project.token_env, '')}

    def revision(self, diagnostics):
        return pointer(diagnostics.get('body', {}), self.project.integration.revision_pointer)

    @staticmethod
    def action_parameters(action):
        return action.parameters

    def validate_action(self, action):
        op = self.operations.get(action.operation)
        if not op or action.order_id is not None or set(action.parameters) != set(op.parameters):
            return False
        for name, rule in op.parameters.items():
            value = action.parameters[name]
            expected = {'string': str, 'integer': int, 'boolean': bool}[rule.kind]
            if type(value) is not expected or isinstance(value, str) and len(value) > 200:
                return False
            if rule.choices and value not in rule.choices:
                return False
        return True

    def needs_approval(self, operation):
        return self.operations[operation].risk == 'high'

    async def read(self, name, resource=None):
        config = self.project.integration
        paths = {'health': config.health_path, 'diagnostics': config.diagnostics_path, 'workflows': config.workflow_path, 'order': config.resource_path}
        path = paths.get(name)
        if path is None:
            return {'ok': True, 'configured': False, 'latency_ms': 0, 'body': {}}
        if '{resource}' in path:
            if not resource or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}', resource):
                raise ValueError('Invalid resource identifier')
            path = path.replace('{resource}', quote(resource, safe=''))
        start = time.monotonic()
        try:
            response = await self.client.get(self.project.base_url+path, headers=self.headers, timeout=self.project.timeout_seconds, follow_redirects=False)
            try:
                body = response.json()
            except ValueError:
                body = {'non_json_response': True}
            result = {'ok': response.is_success, 'configured': True, 'status': response.status_code, 'latency_ms': round((time.monotonic()-start)*1000, 2), 'body': body}
        except httpx.HTTPError as exc:
            result = {'ok': False, 'configured': True, 'latency_ms': round((time.monotonic()-start)*1000, 2), 'body': {}, 'error': type(exc).__name__}
        if name == 'health':
            result['accepted'] = result['ok'] and result['latency_ms'] <= self.project.latency_ms and all(assertion(result['body'], r) for r in config.health_checks)
        if name == 'workflows' and result['ok']:
            rows = result['body'].get('discrepancies') if isinstance(result['body'], dict) else None
            if not isinstance(rows, list) or len(rows) > 500 or any(not isinstance(r, dict) or not isinstance(r.get('id'), str) for r in rows):
                result.update(ok=False, error='Invalid discrepancy schema')
        return result

    def faults(self, health, workflows):
        if not health.get('accepted', False):
            yield 'outage', 'service', {'health': health}
        if workflows['ok'] and workflows.get('configured'):
            for row in workflows['body']['discrepancies']:
                if re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}', row['id']):
                    yield 'workflow', row['id'], {'workflow': row}

    def precondition(self, operation, diagnostics, parameters, resource):
        op = self.operations.get(operation)
        if not op or not diagnostics['ok'] or not diagnostics.get('configured') or type(self.revision(diagnostics)) not in (int, str):
            return False, 'Fresh configured diagnostics and a revision are required'
        if any(rule.resource_bound and parameters.get(name) != resource for name, rule in op.parameters.items()):
            return False, 'Action parameters must match the incident resource'
        passed = all(assertion(diagnostics['body'], rule) for rule in op.preconditions)
        return passed, '; '.join(rule.label for rule in op.preconditions)

    async def execute(self, action, request_id, revision):
        if not self.validate_action(action):
            raise ValueError('Unregistered operation or invalid parameters')
        response = await self.client.post(self.project.base_url+self.operations[action.operation].path, headers=self.headers, json={'request_id': request_id, 'expected_revision': revision, **action.parameters}, timeout=10, follow_redirects=False)
        response.raise_for_status()
        return response.json()

    async def verify(self, kind, resource):
        config = self.project.integration
        observations = []
        for _ in range(3):
            observations.append(await self.read('health'))
            await asyncio.sleep(0.1)
        checks = {'three_accepted_health_probes': all(p.get('accepted') for p in observations)}
        evidence = {'health': observations}
        if kind == 'workflow':
            result = await self.read('order', resource)
            evidence['resource'] = result
            checks['resource_endpoint_observed'] = result['ok'] and result.get('configured', False)
            for n, rule in enumerate(config.resource_checks):
                checks[f'resource_{n+1}: {rule.label}'] = result['ok'] and assertion(result['body'], rule)
            checks['resource_acceptance_defined'] = bool(config.resource_checks)
        elif config.service_checks:
            result = await self.read('diagnostics')
            evidence['diagnostics'] = result
            for n, rule in enumerate(config.service_checks):
                checks[f'service_{n+1}: {rule.label}'] = result['ok'] and assertion(result['body'], rule)
        return {'passed': all(checks.values()), 'checks': checks, 'evidence': evidence}
