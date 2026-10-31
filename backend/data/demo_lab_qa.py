from pathlib import Path
import os
from ctrlz.main import create_app
from ctrlz.store import Store
from ctrlz.models import Project
from ctrlz.presets import campuspass_project
from ctrlz.repository import RepositoryImports
store=Store(os.environ['DATABASE_URL'])
store.save_project(Project(id='dispatch-qa',name='Dispatch API · QA',base_url='http://127.0.0.1:8999').model_dump())
store.save_project(campuspass_project(id='campus-qa',name='CampusPass · optional fixture',base_url='http://127.0.0.1:8998').model_dump())
imports=RepositoryImports(os.environ['IMPORT_ROOT'])
repo=imports.root/'repo-healthy-python'
if not repo.exists():
    repo.mkdir()
    (repo/'pricing.py').write_text('def eligible(quantity):\n    return quantity >= 3\n')
    (repo/'test_pricing.py').write_text('from pricing import eligible\ndef test_boundary():\n    assert eligible(3)\ndef test_below():\n    assert not eligible(2)\n')
    imports._commit(repo,{'kind':'local'},[])
app=create_app(store=store,monitor=False)
