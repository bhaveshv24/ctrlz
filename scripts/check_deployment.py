"""Verify a hosted CtrlZ stack without triggering recovery or exposing credentials."""
import argparse
import getpass
import json
import os
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def origin(value, allow_http=False):
    parts = urlsplit(value)
    schemes = {'http', 'https'} if allow_http else {'https'}
    if parts.scheme not in schemes or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in {'', '/'}:
        raise ValueError('Use an HTTPS origin with no path, credentials, query or fragment')
    return value.rstrip('/')


def check(backend, frontend, email=None, password=None, allow_http=False):
    backend, frontend = origin(backend, allow_http), origin(frontend, allow_http)

    def request(path, method='GET', body=None, headers=None, expected=200, base=backend):
        data = json.dumps(body).encode() if body is not None else None
        req = Request(base + path, data=data, method=method,
                      headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            response = urlopen(req, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            if response.status != expected:
                raise RuntimeError(f'{method} {path}: expected HTTP {expected}, received {response.status}')
            contents, response_headers = response.read(), response.headers
        try:
            result = json.loads(contents)
        except (ValueError, UnicodeError):
            result = None
        return result, response_headers

    health, _ = request('/health')
    if not isinstance(health, dict) or health.get('status') != 'healthy':
        raise RuntimeError('Backend health response is invalid')
    print('PASS: backend health')
    request('/', base=frontend)
    print('PASS: frontend responds')
    _, cors = request('/auth/login', method='OPTIONS', headers={
        'Origin': frontend, 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'authorization,content-type'})
    if cors.get('Access-Control-Allow-Origin') != frontend:
        raise RuntimeError('Backend CORS does not allow the exact frontend origin')
    print('PASS: exact frontend origin allowed by CORS')
    request('/projects', expected=401)
    print('PASS: anonymous workspace access rejected')
    config, _ = request('/auth/config')
    if config.get('registration_enabled'):
        raise RuntimeError('Staging should be invite-only: disable CTRLZ_ALLOW_REGISTRATION')
    print('PASS: invite-only account registration')
    if not email:
        print('SKIP: account checks (supply --email to verify sign-in and permissions)')
        return
    session, _ = request('/auth/login', method='POST', body={'email': email, 'password': password})
    token = session.get('token')
    if not token:
        raise RuntimeError('Login returned no session')
    headers = {'Authorization': 'Bearer ' + token}
    try:
        me, _ = request('/auth/me', headers=headers)
        if me.get('email') != email.strip().lower() or me.get('role') not in {'admin', 'user'}:
            raise RuntimeError('Signed-in identity or role does not match')
        projects, _ = request('/projects', headers=headers)
        if not isinstance(projects, list):
            raise RuntimeError('Workspace project response is invalid')
        request('/auth/users', headers=headers, expected=200 if me['role'] == 'admin' else 403)
        capabilities, _ = request('/capabilities', headers=headers)
        print('PASS: sign-in, workspace access and account-role permissions')
        print('Repository execution: ' + ('enabled; verify Docker acceptance separately' if capabilities.get('code_execution_enabled') else 'disabled on this host'))
    finally:
        request('/auth/logout', method='POST', body={}, headers=headers)
    request('/projects', headers=headers, expected=401)
    print('PASS: logout revokes session')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', required=True)
    parser.add_argument('--frontend', required=True)
    parser.add_argument('--email')
    parser.add_argument('--allow-http', action='store_true', help='Local rehearsal only')
    args = parser.parse_args()
    password = (os.getenv('CTRLZ_DEPLOY_CHECK_PASSWORD') or getpass.getpass('Account password: ')) if args.email else None
    try:
        check(args.backend, args.frontend, args.email, password, args.allow_http)
    except Exception as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
