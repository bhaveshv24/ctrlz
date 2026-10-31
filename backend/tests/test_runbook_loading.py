from pathlib import Path
from ctrlz.runbooks import Runbooks


def test_packaged_runbooks_load_from_unrelated_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    books = Runbooks(Path('/missing/configured/runbooks'), tmp_path/'index')
    assert books.collection.count() >= 3
    results = books.search('service outage health unavailable recovery')
    assert results
    assert any('outage' in result['id'] or 'http' in result['id'] for result in results)


def test_custom_runbooks_take_precedence(tmp_path):
    source = tmp_path/'guides'
    source.mkdir()
    (source/'custom.md').write_text('Unique recovery guide for test service outage', encoding='utf-8')
    books = Runbooks(source, tmp_path/'custom-index')
    assert books.collection.count() == 1
    assert books.search('test service')[0]['id'] == 'custom.md'
