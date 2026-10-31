"""Named Docker operations only. Dependency setup and offline tests are separate phases."""
import json
import os
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from .repository import PROFILES, python_dependencies


def docker(args, timeout=120):
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(['docker', *args], stdout=output, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=10)
            raise RuntimeError('Docker operation exceeded its execution budget')
        length = output.tell(); output.seek(max(0, length-16000))
        text = output.read().decode(errors='replace')
    return code, text


class Sandbox:
    def __init__(self, workspace, profile, install_dependencies=False):
        self.workspace, self.profile = Path(workspace).resolve(), profile
        self.install_dependencies = install_dependencies
        self.volume = None
        self.report = {'approved': install_dependencies, 'phase': 'not_required'}

    @property
    def image(self):
        return PROFILES[self.profile]['image']

    def base(self, name, network='none'):
        return ['run', '--rm', '--name', name, '--log-driver', 'none', '--network', network, '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128', '--memory', '512m', '--cpus', '2', '--user', '65534:65534', '--tmpfs', '/tmp:rw,nosuid,size=192m', '--env', 'HOME=/tmp', '--env', 'TMPDIR=/tmp', '--env', 'XDG_CACHE_HOME=/tmp/.cache']

    def prepare(self, inspection):
        code, text = docker(['image', 'inspect', self.image], 15)
        if code:
            raise RuntimeError(f'Docker sandbox image {self.image} is unavailable; build the supported runtime first')
        if not inspection['dependency_install_required']:
            return self.report
        if not self.install_dependencies:
            raise ValueError('Declared dependencies need explicit setup approval before tests can run')
        self.volume = 'ctrlz-deps-'+uuid.uuid4().hex[:16]
        code, text = docker(['volume', 'create', self.volume], 15)
        if code:
            raise RuntimeError('Could not create isolated dependency storage')
        initializer = ['node', '-e', "require('node:fs').chmodSync('/deps',0o777)"] if self.profile != 'python-pytest' else ['python', '-c', "import os; os.chmod('/deps',0o777)"]
        code, text = docker(['run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--user', '0:0', '--mount', f'type=volume,src={self.volume},dst=/deps,volume-nocopy', self.image, *initializer], 15)
        if code:
            raise RuntimeError('Could not initialize isolated dependency storage')
        with tempfile.TemporaryDirectory(prefix='ctrlz-manifests-') as directory:
            manifests = Path(directory); manifests.chmod(0o755)
            if self.profile == 'python-pytest':
                (manifests/'requirements.txt').write_text('\n'.join(python_dependencies(self.workspace))+'\n')
                runner = ['python', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '--no-cache-dir', '--only-binary=:all:', '--index-url', 'https://pypi.org/simple', '--target', '/deps', '-r', '/manifests/requirements.txt']
            else:
                for filename in ['package.json', 'package-lock.json']:
                    shutil.copyfile(self.workspace/filename, manifests/filename)
                runner = ['node', '/opt/ctrlz/install-node.mjs']
            for path in manifests.iterdir():path.chmod(0o644)
            name = 'ctrlz-setup-'+uuid.uuid4().hex[:12]
            args = self.base(name, 'bridge')+['--mount', f'type=bind,src={manifests},dst=/manifests,readonly', '--mount', f'type=volume,src={self.volume},dst=/deps,volume-nocopy', '--workdir', '/deps', self.image, *runner]
            try:
                code, text = docker(args, 180)
            except Exception:
                docker(['kill', name], 10)
                raise
        self.report = {'approved': True, 'phase': 'dependency_setup', 'exit_code': code, 'declared': inspection['dependencies'], 'output': text, 'install_scripts': 'disabled; Python binary wheels only', 'test_network': 'none'}
        if code:
            raise RuntimeError('Isolated dependency installation failed: '+text[-500:])
        return self.report

    def run(self):
        results = Path(tempfile.mkdtemp(prefix='ctrlz-test-results-')); results.chmod(0o777)
        name = 'ctrlz-test-'+uuid.uuid4().hex[:12]
        args = self.base(name)+['--mount', f'type=bind,src={self.workspace},dst=/workspace,readonly', '--mount', f'type=bind,src={results},dst=/results', '--workdir', '/workspace', '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=', '--env', 'PYTHONPATH=/workspace:/workspace/src:/deps', '--env', 'COVERAGE_FILE=/tmp/.coverage']
        if self.volume:
            target = '/deps' if self.profile == 'python-pytest' else '/workspace/node_modules'
            source = f'type=volume,src={self.volume},dst={target},readonly,volume-nocopy'
            if self.profile != 'python-pytest':
                # npm ci writes node_modules under /deps; mount only that subdirectory.
                source += ',volume-subpath=node_modules'
            args += ['--mount', source]
        runner = list(PROFILES[self.profile]['runner'])
        if self.profile == 'javascript-vitest':
            lock = json.loads((self.workspace/'package-lock.json').read_text())
            version = lock.get('packages',{}).get('node_modules/vitest',{}).get('version','0')
            if version.startswith('5.'):
                runner += ['--fsModuleCache=false']
        args += [self.image, *runner]
        try:
            code, output = docker(args, 90)
            report = results/'report.xml'; cases = []
            if report.is_file() and not report.is_symlink() and report.stat().st_size < 2_000_000:
                raw = report.read_bytes()
                if b'<!DOCTYPE' in raw:
                    raise ValueError('Unsafe test report declaration')
                for case in ET.fromstring(raw).iter('testcase'):
                    status = 'error' if case.find('error') is not None else 'failed' if case.find('failure') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
                    failure = case.find('error') if case.find('error') is not None else case.find('failure')
                    detail = '' if failure is None else (failure.get('message','')+' '+''.join(failure.itertext()))[:4000]
                    cases.append({'id': case.get('classname','')+'::'+case.get('name',''), 'passed': status == 'passed', 'status': status, 'detail': detail})
            failures = '\n'.join(c['id']+': '+c['detail'] for c in cases if not c['passed'] and c['status'] != 'skipped')
            output = (output+'\n'+failures)[-16000:]
            return {'exit_code': code, 'output': output, 'cases': cases, 'profile': self.profile, 'network': 'none'}
        except BaseException:
            docker(['kill', name], 10)
            raise
        finally:
            shutil.rmtree(results, ignore_errors=True)

    def close(self):
        if self.volume:
            code, text = docker(['volume', 'rm', self.volume], 20)
            if code:
                raise RuntimeError('Dependency volume cleanup required: '+self.volume)
