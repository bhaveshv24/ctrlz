"""Disclosed, bounded mutations in disposable managed copies; never execute code on host."""
import ast
import asyncio
import io
import re
import shutil
import tokenize
import uuid
from pathlib import Path
from .repository import editable, git, inspect_repository
from .sandbox import Sandbox


def mutation(root, assessment):
    for name in assessment['editable_files']:
        if not editable(name) or name in assessment['tests']:
            continue
        path = root/name
        if path.is_symlink() or path.stat().st_size > 256000:
            continue
        try:
            source = path.read_text()
            if path.suffix == '.py':
                ast.parse(source)
                lines = source.splitlines(keepends=True)
                for token in tokenize.generate_tokens(io.StringIO(source).readline):
                    replacement = {'==':'!=', '!=':'==', '<':'<=', '<=':'<', '>':'>=', '>=':'>'}.get(token.string) if token.type == tokenize.OP else None
                    if replacement:
                        row, col = token.start
                        line = lines[row-1]
                        changed = ''.join(lines[:row-1])+line[:col]+replacement+line[token.end[1]:]+''.join(lines[row:])
                        ast.parse(changed)
                        return {'file':name, 'line':row, 'before':token.string, 'after':replacement, 'kind':'comparison flip'}, changed
            elif path.suffix in {'.js','.mjs','.cjs','.ts','.tsx','.jsx'}:
                # Only standalone boolean return lines; proof still requires the full suite.
                match = re.search(r'^(\s*return[ \t]+)(true|false)(;?[ \t]*)$', source, re.M)
                if match:
                    replacement = 'false' if match[2] == 'true' else 'true'
                    return {'file':name, 'line':source[:match.start(2)].count('\n')+1, 'before':match[2], 'after':replacement, 'kind':'swapped boolean return'}, source[:match.start(2)]+replacement+source[match.end(2):]
        except (UnicodeError, SyntaxError, tokenize.TokenError):
            continue
    return None


async def injected_copy(repo, imports, approve, record):
    assessment = inspect_repository(repo)
    if not assessment['supported']:
        raise ValueError('; '.join(assessment['warnings']))
    if assessment['dependency_install_required'] and not approve:
        raise ValueError('Isolated dependency setup requires approval')
    destination = imports.root/('repo-'+uuid.uuid4().hex[:12])
    destination.mkdir()
    try:
        omitted = await asyncio.to_thread(imports._copy, repo, destination)
        sandbox = Sandbox(destination, assessment['profile'], approve)
        try:
            environment = await asyncio.to_thread(sandbox.prepare, assessment)
            if assessment['profile'] != 'python-pytest':
                (destination/'node_modules').mkdir(exist_ok=True)
            clean = await asyncio.to_thread(sandbox.run)
            record('injection_clean_baseline', clean)
            if clean['exit_code'] != 0 or not clean['cases']:
                raise ValueError('Injected regression requires a passing original baseline with collected tests; use Repair for existing failures')
            candidate = mutation(destination, assessment)
            if not candidate:
                raise ValueError('No safe deterministic mutation is available in non-test source files')
            disclosure, changed = candidate
            (destination/disclosure['file']).write_text(changed)
            broken = await asyncio.to_thread(sandbox.run)
            record('injection_mutated_baseline', broken)
            before = {c['id'] for c in clean['cases']}
            after = {c['id'] for c in broken['cases']}
            if broken['exit_code'] != 1 or before != after or not any(not c['passed'] for c in broken['cases']):
                raise ValueError('Deterministic mutation did not prove a test regression with the same collected tests; nothing was repaired')
        finally:
            sandbox.close()
        disclosure.update(disclosed=True, original_repository=str(repo), original_commit=git(['rev-parse','HEAD'],repo), clean_baseline=clean, failing_baseline=broken, dependency_environment=environment)
        # Dependency volumes belong to Sandbox; no installed files enter the snapshot.
        shutil.rmtree(destination/'node_modules', ignore_errors=True)
        snapshot = imports._commit(destination, {'kind':'disclosed-injected-regression','original_repository':str(repo)}, omitted)
        return snapshot, disclosure
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
