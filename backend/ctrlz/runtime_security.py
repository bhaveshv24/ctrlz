"""Private source credentials and conservative redaction before persistence/AI."""
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path


class SourceSecrets:
    def __init__(self, root, store=None):
        self._cache = {}
        self.store = store if store is not None and store.engine.dialect.name == 'postgresql' else None
        self.root = Path(root) / 'runtime-secrets'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)

    def path(self, *scope):
        return self.root / (hashlib.sha256('/'.join(scope).encode()).hexdigest()+'.token')

    def get(self, *scope):
        path = self.path(*scope)
        if self.store is not None:
            if path.stem in self._cache:return self._cache[path.stem]
            from .runtime_store import RuntimeSecret
            with self.store.sessions() as db:
                row = db.get(RuntimeSecret, path.stem)
                if row:self._cache[path.stem] = row.value
                return row.value if row else ''
        return path.read_text().strip() if path.exists() else ''

    def provision(self, *scope):
        path = self.path(*scope)
        if self.store is not None:
            if path.stem in self._cache and path.is_file():return path
            from .runtime_store import RuntimeSecret
            with self.store.sessions.begin() as db:
                self.store.lock(db)
                row = db.get(RuntimeSecret, path.stem)
                if row is None:
                    value = path.read_text().strip() if path.exists() else secrets.token_hex(32)
                    row = RuntimeSecret(scope=path.stem, value=value)
                    db.add(row)
                value = row.value
            self._cache[path.stem] = value
            # Preserve the server-only credential-file interface for collectors.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as handle:handle.write(value)
            return path
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        return path

    def pseudonym(self, value):
        if value is None:
            return None
        self.provision('pseudonym-salt')
        return hmac.new(self.get('pseudonym-salt').encode(), value.encode(), hashlib.sha256).hexdigest()[:24]


class Redactor:
    def __init__(self, additional=()):
        self.additional = list(additional)

    def text(self, value):
        if value is None:
            return None
        value = str(value)
        configured = [v for k,v in os.environ.items() if any(x in k.upper() for x in ['TOKEN','PASSWORD','SECRET','API_KEY']) and len(v) >= 8]
        for secret in sorted(set(configured+self.additional), key=len, reverse=True):
            if secret:
                value = value.replace(secret, '[REDACTED]')
        value = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[REDACTED PRIVATE KEY]', value, flags=re.S)
        value = re.sub(r'(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+', '[REDACTED AUTH]', value)
        value = re.sub(r'''(?ix)(["']?(?:password|passwd|authorization|cookie|set-cookie|api[_-]?key|access[_-]?token|refresh[_-]?token|secret)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;}]+)''', r'\1[REDACTED]', value)
        value = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|nvapi-[A-Za-z0-9_-]+|sk-[A-Za-z0-9_-]{12,}|AKIA[A-Z0-9]{16})\b', '[REDACTED TOKEN]', value)
        value = re.sub(r'(?i)(https?://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', value)
        value = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[REDACTED EMAIL]', value)
        value = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[REDACTED IP]', value)
        value = re.sub(r'\b(?:\d[ -]?){13,19}\b', '[REDACTED NUMBER]', value)
        return value

    def tree(self, value):
        if isinstance(value, dict):
            return {k:self.tree(v) for k,v in value.items()}
        if isinstance(value, list):
            return [self.tree(v) for v in value]
        return self.text(value) if isinstance(value, str) else value
