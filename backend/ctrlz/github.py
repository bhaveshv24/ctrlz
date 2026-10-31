"""Normalize GitHub identities without following arbitrary URLs or sending credentials."""
import re
from urllib.parse import urlsplit


def normalize_github(value: str):
    value = value.strip()
    if value.startswith('git@github.com:'):
        value = value.removeprefix('git@github.com:')
    elif '://' in value:
        url = urlsplit(value)
        if url.scheme not in {'https', 'http', 'ssh'} or url.hostname not in {'github.com', 'www.github.com'} or url.password or url.port or (url.username and not (url.scheme == 'ssh' and url.username == 'git')):
            raise ValueError('Use a GitHub repository URL or owner/repo without credentials')
        value = url.path.strip('/')
    parts = value.strip('/').split('/')
    if len(parts) < 2 or len(parts) > 2 and parts[2] not in {'tree', 'blob', 'issues', 'pull', 'pulls', 'actions', 'releases', 'commits', 'settings'}:
        raise ValueError('Use owner/repo or a GitHub repository link')
    owner, repo = parts[:2]
    repo = repo.removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})', owner) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', repo) or repo in {'.','..'}:
        raise ValueError('Malformed GitHub owner or repository name')
    return {'owner':owner,'repo':repo,'full_name':f'{owner}/{repo}','url':f'https://github.com/{owner}/{repo}'}
