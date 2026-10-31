"""Email accounts, opaque expiring sessions, and persistent sign-in throttling."""
import hashlib
import os
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
from .database import database_engine, postgres_url
from psycopg.rows import dict_row
from psycopg import IntegrityError as PostgresIntegrityError
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def email_address(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address')
        return value


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class Accounts:
    def __init__(self, root, database_url=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'accounts.db'
        self.engine = database_engine(database_url, 'ctrlz_accounts') if database_url and postgres_url(database_url) else None
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                    salt TEXT NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset REAL NOT NULL);
            ''')
        if self.engine is None:self.path.chmod(0o600)
        self.dummy_salt = secrets.token_hex(16)
        self.dummy_hash = password_hash(secrets.token_urlsafe(24), self.dummy_salt)

    @contextmanager
    def connect(self):
        if self.engine is None:
            db = sqlite3.connect(self.path, timeout=30)
            db.row_factory = sqlite3.Row
            try:
                with db:yield db
            finally:db.close()
        else:
            with self.engine.connect() as connection:
                db = connection.connection.driver_connection
                db.row_factory = dict_row
                with db.transaction():
                    db.execute('SET LOCAL search_path TO ctrlz_accounts')
                    yield PostgresAccountsConnection(db)

    @staticmethod
    def public(row):
        return {key: row[key] for key in ('id', 'email', 'role')}

    def users(self):
        with self.connect() as db:
            return [self.public(row) for row in db.execute('SELECT * FROM users ORDER BY email')]

    def create(self, credentials, role='user'):
        salt, uid = secrets.token_hex(16), uuid.uuid4().hex
        hashed = password_hash(credentials.password, salt)
        try:
            with self.connect() as db:
                if db.execute('SELECT COUNT(*) AS total FROM users').fetchone()['total'] >= 50:
                    raise HTTPException(409, 'This controlled deployment has reached its account limit')
                db.execute('INSERT INTO users VALUES(?,?,?,?,?)', (uid, credentials.email, salt, hashed, role))
        except (sqlite3.IntegrityError, PostgresIntegrityError):
            raise HTTPException(409, 'Account could not be created; use sign in or contact an administrator')
        return {'id': uid, 'email': credentials.email, 'role': role}

    def seed(self):
        """Write generated credentials locally once. Never return passwords through an API."""
        generated = []
        for prefix, default, role in [('ADMIN_1', 'admin1@ctrlz.local', 'admin'),
                                      ('ADMIN_2', 'admin2@ctrlz.local', 'admin'),
                                      ('USER', 'user@ctrlz.local', 'user')]:
            email = os.getenv('CTRLZ_' + prefix + '_EMAIL', default).strip().lower()
            with self.connect() as db:
                exists = db.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone()
            if exists:
                continue
            password = os.getenv('CTRLZ_' + prefix + '_PASSWORD') or secrets.token_urlsafe(24)
            self.create(Credentials(email=email, password=password), role)
            generated.append(f'{role}: {email}\nPassword: {password}\n')
        if generated:
            path = self.root / 'initial-credentials.txt'
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, 'a') as handle:
                handle.write('\n'.join(generated) + '\n')
            path.chmod(0o600)

    def throttle(self, key, limit=10):
        key = hashlib.sha256(key.encode()).hexdigest()
        now = time.time()
        with self.connect() as db:
            db.execute('DELETE FROM attempts WHERE reset < ?', (now,))
            row = db.execute('SELECT * FROM attempts WHERE key=?', (key,)).fetchone()
            if row and row['count'] >= limit:
                raise HTTPException(429, 'Too many attempts. Try again in 15 minutes')
            db.execute('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=attempts.count+1', (key, now+900))

    def login(self, credentials):
        with self.connect() as db:
            row = db.execute('SELECT * FROM users WHERE email=?', (credentials.email,)).fetchone()
        actual = password_hash(credentials.password, row['salt'] if row else self.dummy_salt)
        if not secrets.compare_digest(actual, row['password'] if row else self.dummy_hash) or not row:
            raise HTTPException(401, 'Email or password is incorrect')
        token = secrets.token_urlsafe(48)
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], time.time()+28800))
        return {'token': token, 'user': self.public(row), 'expires_in': 28800}

    def resolve(self, token):
        with self.connect() as db:
            row = db.execute('SELECT users.* FROM users JOIN sessions ON users.id=sessions.user_id WHERE digest=? AND expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        if not row:
            raise HTTPException(401, 'Session expired. Sign in again')
        return self.public(row)

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE digest=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def change_password(self, user, password):
        salt = secrets.token_hex(16)
        hashed = password_hash(password, salt)
        with self.connect() as db:
            db.execute('UPDATE users SET salt=?, password=? WHERE id=?', (salt, hashed, user['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))


class PostgresAccountsConnection:
    def __init__(self, connection):self.connection = connection

    def execute(self, sql, values=()):
        return self.connection.execute(sql.replace('?', '%s'), values)

    def executescript(self, sql):
        for statement in sql.split(';'):
            if statement.strip():self.connection.execute(statement.replace('expires REAL', 'expires DOUBLE PRECISION').replace('reset REAL', 'reset DOUBLE PRECISION'))
        for name in ('users', 'sessions', 'attempts'):
            self.connection.execute(f'ALTER TABLE {name} ENABLE ROW LEVEL SECURITY')
