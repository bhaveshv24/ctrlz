"""Manifest-derived display instructions; never execute repository instructions."""
import ast
import re
import shlex
import tomllib


def _package_commands(root, profile):
    if profile == 'python-pytest':
        project = {}
        if (root/'pyproject.toml').is_file():
            try:project = tomllib.loads((root/'pyproject.toml').read_text())
            except (ValueError,OSError):pass
        extra = ' --extra test' if 'test' in project.get('project',{}).get('optional-dependencies',{}) else ''
        if (root/'uv.lock').is_file() or project.get('tool',{}).get('uv') is not None:
            return {'setup':f'uv sync{extra}', 'test':'uv run python -m pytest -q','directory':'.','basis':'pyproject.toml and uv configuration/lockfile'}
        requirements = 'requirements-lock.txt' if (root/'requirements-lock.txt').is_file() else 'requirements.txt' if (root/'requirements.txt').is_file() else None
        setup = 'python3 -m venv .venv\nsource .venv/bin/activate'
        if requirements:setup += '\npython -m pip install -r '+requirements
        elif project:setup += '\npython -m pip install '+shlex.quote('.[test]' if extra else '.')
        else:setup += '\npython -m pip install pytest'
        return {'setup':setup,'test':'python -m pytest -q','directory':'.','basis':requirements or ('pyproject.toml' if project else 'Detected pytest suite; no dependency manifest found')}
    if profile in {'node-test','javascript-vitest'}:
        return {'setup':'npm ci --ignore-scripts' if (root/'package-lock.json').is_file() else 'npm install --ignore-scripts', 'test':'node --test' if profile == 'node-test' else 'node node_modules/vitest/vitest.mjs run','directory':'.','basis':'Detected test profile and npm lockfile; install scripts disabled'}
    return None


def check_commands(root, profile):
    package = root
    manifests = ['pyproject.toml', 'requirements.txt', 'requirements-lock.txt', 'package.json']
    if not any((root/name).is_file() for name in manifests):
        candidates = [p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and not p.name.startswith('.') and any((p/name).is_file() for name in manifests) and (list(p.glob('test_*.py')) or (p/'tests').is_dir())]
        if len(candidates) == 1:package = candidates[0]
    result = _package_commands(package, profile)
    if result is None:return None
    directory = package.relative_to(root).as_posix()
    result['directory'] = directory
    prefix = '' if directory == '.' else 'cd '+shlex.quote(directory)+'\n'
    result['setup'] = prefix + result['setup']
    main = package/'main.py'
    if profile != 'python-pytest' or not main.is_file() or main.stat().st_size > 256000:return result
    try:
        tree = ast.parse(main.read_text())
        has_app = any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='app' for t in n.targets) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='FastAPI' for n in ast.walk(tree))
        if not has_app:return result
        endpoints = []
        sources = [main] + sorted((package/'routes').glob('*.py'))
        for path in sources[:40]:
            if path.is_symlink() or path.stat().st_size>256000:continue
            parsed = ast.parse(path.read_text())
            router_prefix = ''
            for n in ast.walk(parsed):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='APIRouter':
                    router_prefix = next((k.value.value for k in n.keywords if k.arg=='prefix' and isinstance(k.value,ast.Constant) and isinstance(k.value.value,str)), '')
            for n in ast.walk(parsed):
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    for d in n.decorator_list:
                        if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='get' and d.args and isinstance(d.args[0],ast.Constant) and isinstance(d.args[0].value,str):
                            route = (router_prefix if isinstance(d.func.value,ast.Name) and d.func.value.id=='router' else '') + d.args[0].value
                            if re.fullmatch(r'/[A-Za-z0-9_./-]*',route):endpoints.append(route)
        endpoints = sorted(set(endpoints),key=lambda route:(not any(x in route for x in ['health','leaderboard','streak','analytics']),route))[:12]
        runner = 'uv run uvicorn' if result['test'].startswith('uv run') else 'python -m uvicorn'
        result['server'] = result['setup']+'\n'+runner+' main:app --host 127.0.0.1 --port 8011'
        result['requests'] = '\n'.join('curl -i '+shlex.quote('http://127.0.0.1:8011'+route) for route in endpoints)
        result['api_note'] = 'GET routes detected statically from FastAPI source; these are manual checks, not recorded HTTP results. Keep the server terminal open and run requests in a second terminal. Authentication and runtime configuration may be required.'
    except (ValueError,OSError,SyntaxError):pass
    return result
