"""Sanitized source history: never retain upstream Git objects or historical secrets."""
import shutil
import tempfile
from pathlib import Path
from .repository import MAX_BYTES, MAX_FILES, SKIP_DIRS, editable, git, inspect_repository, relative_path, sensitive


def source_files(root, protected):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(root).parts) and editable(p.relative_to(root).as_posix()) and p.relative_to(root).as_posix() not in protected}


def replace_sources(root, files, protected):
    for name in source_files(root, protected):
        (root/name).unlink()
    for name,content in files.items():
        relative_path(name)
        if not editable(name) or name in protected or len(content)>256000 or b'\x00' in content:
            raise ValueError('History source violates product-source boundaries')
        target=root/name
        current=root
        for part in Path(name).parts:
            current=current/part
            if current.is_symlink():raise ValueError('History symlinks are forbidden')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(content);target.chmod(0o644)
        for parent in target.parents:
            if parent==root.parent:break
            parent.chmod(0o755)


def preserve_history(upstream, destination, subdirectory=''):
    if not (upstream/'.git').exists():return [],'Source has no Git history'
    protected=set(inspect_repository(destination)['tests'])
    head=source_files(destination,protected)
    mappings=[]
    try:
        commits=git(['rev-list','--first-parent','--max-count=29','HEAD'],upstream).splitlines()[::-1]
        prefix=subdirectory.strip('/')+'/' if subdirectory else ''
        git(['init','-b','main'],destination)
        previous=None;aggregate=0
        for revision in commits:
            files={};count=0;size=0
            tree=git(['ls-tree','-rlz',revision],upstream,raw=True)
            for row in tree.split(b'\x00'):
                if not row:continue
                metadata,name=row.split(b'\t',1)
                mode,kind,blob,length=metadata.decode().split()
                name=name.decode('utf-8')
                if prefix:
                    if not name.startswith(prefix):continue
                    name=name[len(prefix):]
                if not name or not editable(name) or name in protected or sensitive(name) or any(p in SKIP_DIRS for p in Path(name).parts):continue
                relative_path(name)
                if mode not in {'100644','100755'} or kind!='blob':raise ValueError('Unsupported history entry')
                count+=1;size+=int(length)
                if count>MAX_FILES or size>MAX_BYTES or int(length)>256000:raise ValueError('Historical source exceeds bounds')
                content=git(['cat-file','blob',blob],upstream,raw=True)
                content.decode('utf-8')
                if b'\x00' in content:raise ValueError('History contains binary product source')
                files[name]=content
            aggregate+=size
            if aggregate>128*1024*1024:raise ValueError('Total sanitized history exceeds 128 MiB')
            if not files or files==previous:continue
            replace_sources(destination,files,protected)
            git(['add','--force','.'],destination)
            git(['-c','user.name=CtrlZ Snapshot','-c','user.email=snapshot@localhost','commit','--allow-empty','-m','Sanitized product source history'],destination)
            mappings.append({'snapshot_commit':git(['rev-parse','HEAD'],destination),'upstream_commit':revision})
            previous=files
        return mappings,None
    except (ValueError,UnicodeError,OSError):
        shutil.rmtree(destination/'.git',ignore_errors=True)
        return [],'History unavailable: historical paths, source bounds or Git validation failed'
    finally:
        replace_sources(destination,head,protected)
