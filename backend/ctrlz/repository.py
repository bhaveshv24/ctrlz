"""Managed source snapshots. Imported code is data here; it is never run on the host."""
import configparser
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from pydantic import Field
from .models import Strict
from .github import normalize_github

MAX_BYTES = 64 * 1024 * 1024
MAX_UPLOAD = 25 * 1024 * 1024
MAX_FILES = 3000
SKIP_DIRS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache', '.next', 'dist', 'build', 'coverage', '.cache', '.idea', '.vscode'}
SOURCE_EXTENSIONS = {'.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx'}
PROFILES = {'python-pytest': {'label': 'Python / pytest', 'image': 'ctrlz-sandbox:local', 'runner': ['python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--assert=plain', '--junitxml=/results/report.xml']}, 'node-test': {'label': 'JavaScript / Node test', 'image': 'ctrlz-node-sandbox:local', 'runner': ['node', '--test', '--test-reporter=junit', '--test-reporter-destination=/results/report.xml']}, 'javascript-vitest': {'label': 'JavaScript / TypeScript / Vitest', 'image': 'ctrlz-node-sandbox:local', 'runner': ['node', 'node_modules/vitest/vitest.mjs', 'run', '--reporter=junit', '--outputFile=/results/report.xml', '--configLoader=runner', '--maxWorkers=2', '--cache=false']}}


class RepositorySource(Strict):
    kind: str = Field(pattern=r'^(github|local)$')
    source: str = Field(min_length=1, max_length=2048)
    subdirectory: str = Field(default='', max_length=200)


def test_file(name):
    p = PurePosixPath(name)
    return any(part in {'test', 'tests', '__tests__'} for part in p.parts) or p.name.startswith('test_') or p.name.endswith('_test.py') or bool(re.search(r'\.(test|spec)\.[cm]?[jt]sx?$', p.name)) or p.name == 'conftest.py'


def sensitive(name):
    p = PurePosixPath(name)
    return (p.name.startswith('.env') and not p.name.endswith('.example')) or p.suffix.lower() in {'.pem', '.key', '.p12', '.db', '.sqlite', '.sqlite3'} or p.name in {'.npmrc', '.pypirc', 'id_rsa', 'id_ed25519', 'credentials.json', '.netrc'}


def editable(name):
    p = PurePosixPath(name)
    return p.suffix in SOURCE_EXTENSIONS and not test_file(name) and not any(part.startswith('.') for part in p.parts) and p.name not in {'setup.py', 'sitecustomize.py', 'usercustomize.py'} and not re.search(r'\.config\.[cm]?[jt]sx?$', p.name) and not sensitive(name)


def relative_path(name):
    if '\\' in name or '\x00' in name:
        raise ValueError('Invalid snapshot path')
    p = PurePosixPath(name)
    if p.is_absolute() or not p.parts or any(part in {'..', ':'} for part in p.parts) or any(':' in part for part in p.parts):
        raise ValueError('Snapshot path escapes its root')
    return p


def git(args, cwd, timeout=60, raw=False):
    env = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0'}
    result = subprocess.run(['git', '-c', 'core.hooksPath='+os.devnull, '-c', 'core.fsmonitor=false', '-c', 'core.quotePath=false', '-c', 'credential.helper=', *args], cwd=cwd, env=env, capture_output=True, text=not raw, encoding=None if raw else 'utf-8', timeout=timeout)
    if result.returncode:
        raise ValueError('Git could not complete the source snapshot operation')
    return result.stdout if raw or 'diff' in args else result.stdout.strip()


def python_dependencies(root):
    dependencies = []
    if (root/'requirements.txt').is_file():
        for line in (root/'requirements.txt').read_text().splitlines():
            line = line.split(' #')[0].strip()
            if line and not line.startswith('#'):
                dependencies.append(line)
    elif (root/'pyproject.toml').is_file():
        config = tomllib.loads((root/'pyproject.toml').read_text())
        project = config.get('project', {})
        dependencies.extend(project.get('dependencies', []))
        dependencies.extend(project.get('optional-dependencies', {}).get('test', []))
        dependencies.extend(config.get('dependency-groups', {}).get('test', []))
    for filename in ['requirements-test.txt', 'requirements-dev.txt', 'tests/requirements.txt']:
        if (root/filename).is_file():
            for line in (root/filename).read_text().splitlines():
                line = line.split(' #')[0].strip()
                if line and not line.startswith('#'):
                    dependencies.append(line)
    from packaging.requirements import Requirement
    for item in dependencies:
        if not isinstance(item, str) or len(item) > 300:
            raise ValueError('Unsupported dependency declaration')
        parsed = Requirement(item)
        if parsed.url or item.startswith('-'):
            raise ValueError('Only Python package-index requirements are supported; URL/path/options are rejected')
    if len(dependencies) > 100:
        raise ValueError('Dependency count exceeds the bounded repair environment')
    return sorted(set(dependencies))


def inspect_repository(root, requested='auto'):
    paths = sorted(str(p.relative_to(root).as_posix()) for p in root.rglob('*') if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(root).parts))
    if len(paths) > MAX_FILES or sum((root/p).stat().st_size for p in paths) > MAX_BYTES:
        raise ValueError('Repository exceeds the bounded snapshot size')
    if any((root/p).is_symlink() or sensitive(p) for p in paths):
        raise ValueError('Snapshot includes symlinks or credential/database files')
    patterns = []
    if (root/'pyproject.toml').is_file():
        patterns = tomllib.loads((root/'pyproject.toml').read_text()).get('tool',{}).get('pytest',{}).get('ini_options',{}).get('python_files',[])
    for filename in ['pytest.ini','.pytest.ini','setup.cfg','tox.ini']:
        if (root/filename).is_file():
            config = configparser.ConfigParser(interpolation=None)
            config.read(root/filename)
            section = 'tool:pytest' if filename == 'setup.cfg' else 'pytest'
            if config.has_option(section,'python_files'):
                patterns = config.get(section,'python_files').split()
    if isinstance(patterns,str):patterns = patterns.split()
    tests = [p for p in paths if (test_file(p) or any(fnmatch.fnmatch(Path(p).name, pattern) for pattern in patterns)) and Path(p).suffix in SOURCE_EXTENSIONS]
    sources = [p for p in paths if editable(p) and p not in tests]
    package = json.loads((root/'package.json').read_text()) if (root/'package.json').is_file() else {}
    dependencies, warnings = [], []
    profile = requested
    if profile == 'auto':
        script = package.get('scripts', {}).get('test', '')
        if package:
            profile = 'javascript-vitest' if 'vitest' in script or 'vitest' in package.get('devDependencies', {}) else 'node-test' if 'node --test' in script else None
        elif any(p.endswith('.py') for p in tests):
            profile = 'python-pytest'
        elif any(Path(p).suffix in {'.js', '.mjs', '.cjs'} for p in tests):
            profile = 'node-test'
        else:
            profile = None
    if profile not in PROFILES:
        warnings.append('No supported test runner detected. Choose Python/pytest, Node test or Vitest; arbitrary npm scripts are not executed.')
    elif profile == 'python-pytest':
        try:
            dependencies = python_dependencies(root)
        except Exception as exc:
            warnings.append(str(exc))
    else:
        declared = {**package.get('dependencies', {}), **package.get('devDependencies', {}), **package.get('optionalDependencies', {})}
        dependencies = [f'{name}@{version}' for name, version in declared.items()]
        if package.get('workspaces'):
            warnings.append('Select a self-contained package directory; workspace installs are not yet supported.')
        if declared:
            if not (root/'package-lock.json').is_file():
                warnings.append('JavaScript dependencies require package-lock.json for npm ci.')
            else:
                lock = json.loads((root/'package-lock.json').read_text())
                if lock.get('lockfileVersion', 0) < 2:
                    warnings.append('Use npm lockfile version 2 or 3.')
                for name, entry in lock.get('packages', {}).items():
                    url = entry.get('resolved', '')
                    if entry.get('link') or url and not url.startswith('https://registry.npmjs.org/'):
                        warnings.append('Only locked npm registry dependencies are supported; linked/git/custom-registry packages are rejected.')
                        break
        if profile == 'javascript-vitest':
            lock = json.loads((root/'package-lock.json').read_text()) if (root/'package-lock.json').is_file() else {}
            version = lock.get('packages', {}).get('node_modules/vitest', {}).get('version', '0')
            if not re.match(r'^[345]\.', version):
                warnings.append('The Vitest profile currently supports locked Vitest 3, 4 or 5.')
    if not tests:
        warnings.append('No existing acceptance tests detected. Add tests before requesting a verified repair.')
    if not sources:
        warnings.append('No supported editable source files detected.')
    return {'profile': profile, 'profile_label': PROFILES[profile]['label'] if profile in PROFILES else 'Unsupported', 'supported': not warnings, 'dependencies': dependencies, 'dependency_install_required': bool(dependencies), 'tests': tests[:100], 'test_file_count': len(tests), 'editable_files': sources[:300], 'file_count': len(paths), 'source_count': len(sources), 'warnings': list(dict.fromkeys(warnings)), 'files': paths[:1000]}


class RepositoryImports:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _copy(self, source, destination):
        count, size, omitted = 0, 0, []
        for parent, directories, files in os.walk(source, followlinks=False):
            directories[:] = [d for d in directories if d not in SKIP_DIRS and not (Path(parent)/d).is_symlink()]
            for filename in files:
                path = Path(parent)/filename
                relative = path.relative_to(source).as_posix()
                if sensitive(relative):
                    omitted.append(relative)
                    continue
                if path.is_symlink() or not path.is_file():
                    raise ValueError('Snapshot links and special files are not allowed')
                count += 1; size += path.stat().st_size
                if count > MAX_FILES or size > MAX_BYTES:
                    raise ValueError('Source exceeds the bounded import size')
                target = destination/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        return omitted

    def _commit(self, path, provenance, omitted, history=None, history_note=None):
        if not (path/'.git').exists():git(['init', '-b', 'main'], path)
        git(['add', '--force', '.'], path)
        git(['-c', 'user.name=CtrlZ Snapshot', '-c', 'user.email=snapshot@localhost', 'commit', '--allow-empty', '-m', 'Explicitly imported source snapshot'], path)
        metadata = {'id': path.name, 'repository': str(path), 'commit': git(['rev-parse', 'HEAD'], path), 'provenance': provenance, 'omitted_files': omitted}
        metadata['history'] = (history or []) + [{'snapshot_commit':metadata['commit'],'upstream_commit':provenance.get('upstream_commit')}]
        metadata['history_note'] = history_note or 'Sanitized product source snapshots; acceptance tests/configuration fixed to imported HEAD'
        (path/'.git/ctrlz-import.json').write_text(json.dumps(metadata))
        return {**metadata, **inspect_repository(path)}

    def import_source(self, request):
        snapshot = self.root/('repo-'+uuid.uuid4().hex[:12])
        snapshot.mkdir()
        try:
            history = []; history_note = None
            subdir = relative_path(request.subdirectory) if request.subdirectory else None
            if request.kind == 'github':
                identity = normalize_github(request.source)
                with tempfile.TemporaryDirectory(prefix='ctrlz-clone-') as tmp:
                    upstream = Path(tmp)/'upstream'
                    git(['clone', '--depth', '30', '--no-recurse-submodules', '--', identity['url'], str(upstream)], Path(tmp), timeout=90)
                    commit = git(['rev-parse', 'HEAD'], upstream)
                    source = upstream.joinpath(*subdir.parts) if subdir else upstream
                    if not source.is_dir() or not source.resolve().is_relative_to(upstream.resolve()):
                        raise ValueError('Project subdirectory does not exist')
                    omitted = self._copy(source, snapshot)
                    from .history import preserve_history
                    history, history_note = preserve_history(upstream, snapshot, request.subdirectory)
                    provenance = {'kind': 'github', 'url': identity['url'], 'upstream_commit': commit, 'subdirectory': request.subdirectory}
            else:
                source = Path(request.source).expanduser().resolve()
                roots = [Path(p).expanduser().resolve() for p in os.getenv('REPOSITORY_SOURCE_ROOTS', str(self.root.parent.parent)).split(os.pathsep) if p]
                if not source.is_dir() or not any(source.is_relative_to(root) and source != root for root in roots) or self.root.is_relative_to(source):
                    raise ValueError('Local source must be within an operator-configured REPOSITORY_SOURCE_ROOTS directory and cannot contain the managed imports root')
                parent_source = source
                source = source.joinpath(*subdir.parts) if subdir else source
                if not source.resolve().is_relative_to(parent_source) or not source.is_dir():
                    raise ValueError('Invalid project subdirectory')
                omitted = self._copy(source, snapshot)
                from .history import preserve_history
                history, history_note = preserve_history(parent_source, snapshot, request.subdirectory)
                provenance = {'kind': 'local', 'source': str(source)}
            return self._commit(snapshot, provenance, omitted, history, history_note)
        except BaseException:
            shutil.rmtree(snapshot, ignore_errors=True)
            raise

    def import_zip(self, contents):
        snapshot = self.root/('repo-'+uuid.uuid4().hex[:12])
        snapshot.mkdir()
        try:
            if len(contents) > MAX_UPLOAD:
                raise ValueError('ZIP upload exceeds 25 MiB')
            with tempfile.TemporaryDirectory(prefix='ctrlz-unzip-') as tmp:
                unpacked = Path(tmp)
                total = 0
                with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                    entries = archive.infolist()
                    if len(entries) > MAX_FILES:
                        raise ValueError('Too many ZIP entries')
                    for entry in entries:
                        path = relative_path(entry.filename)
                        mode = entry.external_attr >> 16
                        if stat.S_ISLNK(mode) or mode and stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
                            raise ValueError('ZIP symlinks and special files are forbidden')
                        total += entry.file_size
                        if total > MAX_BYTES:
                            raise ValueError('Expanded ZIP exceeds 64 MiB')
                        if entry.is_dir() or any(part in SKIP_DIRS for part in path.parts) or sensitive(path.as_posix()):
                            continue
                        target = unpacked.joinpath(*path.parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(entry) as source, target.open('wb') as output:
                            shutil.copyfileobj(source, output, length=65536)
                children = list(unpacked.iterdir())
                source = children[0] if len(children) == 1 and children[0].is_dir() else unpacked
                omitted = self._copy(source, snapshot)
                provenance = {'kind': 'zip', 'archive_sha256': hashlib.sha256(contents).hexdigest()}
                return self._commit(snapshot, provenance, omitted)
        except BaseException:
            shutil.rmtree(snapshot, ignore_errors=True)
            raise
