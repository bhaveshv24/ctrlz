"""Manifest-derived display instructions; never execute repository instructions."""
import json
import shlex
import tomllib


def check_commands(root, profile):
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
