from ctrlz.check_commands import check_commands

def test_uv_test_extra_and_requirements_are_distinct(tmp_path):
    (tmp_path/'pyproject.toml').write_text('[project.optional-dependencies]\ntest=["pytest"]\n')
    (tmp_path/'uv.lock').write_text('version=1')
    assert check_commands(tmp_path,'python-pytest')['setup']=='uv sync --extra test'
    assert check_commands(tmp_path,'python-pytest')['test']=='uv run python -m pytest -q'
    (tmp_path/'uv.lock').unlink();(tmp_path/'pyproject.toml').unlink()
    (tmp_path/'requirements.txt').write_text('pytest')
    assert 'pip install -r requirements.txt' in check_commands(tmp_path,'python-pytest')['setup']

def test_nested_fastapi_commands_include_dependencies_folder_and_real_routes(tmp_path):
    backend=tmp_path/'backend';backend.mkdir()
    (backend/'requirements.txt').write_text('fastapi\nuvicorn\npytest')
    (backend/'test_api.py').write_text('')
    (backend/'main.py').write_text('from fastapi import FastAPI\napp=FastAPI()\n@app.get("/api/health")\ndef health(): return {}\n')
    guide=check_commands(tmp_path,'python-pytest')
    assert guide['directory']=='backend'
    assert guide['server'].startswith('cd backend\n')
    assert 'pip install -r requirements.txt' in guide['server']
    assert 'uvicorn main:app' in guide['server']
    assert '/api/health' in guide['requests']
    assert '/api/streak' not in guide['requests']
