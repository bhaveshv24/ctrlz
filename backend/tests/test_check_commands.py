from ctrlz.check_commands import check_commands

def test_uv_test_extra_and_requirements_are_distinct(tmp_path):
    (tmp_path/'pyproject.toml').write_text('[project.optional-dependencies]\ntest=["pytest"]\n')
    (tmp_path/'uv.lock').write_text('version=1')
    assert check_commands(tmp_path,'python-pytest')['setup']=='uv sync --extra test'
    assert check_commands(tmp_path,'python-pytest')['test']=='uv run python -m pytest -q'
    (tmp_path/'uv.lock').unlink();(tmp_path/'pyproject.toml').unlink()
    (tmp_path/'requirements.txt').write_text('pytest')
    assert 'pip install -r requirements.txt' in check_commands(tmp_path,'python-pytest')['setup']
