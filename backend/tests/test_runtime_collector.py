"""Collector transport is mocked here; real delivery is rehearsed separately."""
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('runtime_collector',Path(__file__).resolve().parents[2]/'scripts/runtime_log_collector.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)


def test_cursor_and_original_event_id_survive_failed_delivery(tmp_path,monkeypatch):
    log=tmp_path/'application.jsonl';cursor=tmp_path/'cursor.json'
    log.write_text(json.dumps({'event_id':'actual-log-entry','message':'failure'})+'\n')
    delivered=[]
    def failed(*args):raise RuntimeError('Temporary collector delivery error')
    monkeypatch.setattr(collector,'post',failed)
    with pytest.raises(RuntimeError):collector.collect_once(log,cursor,'http://localhost/telemetry/a/b/c/d','private-key')
    assert not cursor.exists()
    def success(endpoint,token,events):delivered.extend(events);return {'accepted':1,'duplicates':0,'incident_ids':[]}
    monkeypatch.setattr(collector,'post',success)
    assert collector.collect_once(log,cursor,'http://localhost/telemetry/a/b/c/d','private-key')==1
    assert delivered[0]['event_id']=='actual-log-entry'
    assert collector.collect_once(log,cursor,'http://localhost/telemetry/a/b/c/d','private-key')==0


def test_collector_rejects_unrelated_paths_and_symlinks(tmp_path,monkeypatch):
    secret=tmp_path/'.env';secret.write_text('sensitive')
    with pytest.raises(ValueError):collector.collect_once(secret,tmp_path/'cursor','http://localhost','token')
    real=tmp_path/'application.jsonl';real.write_text('')
    link=tmp_path/'linked.jsonl'
    try:link.symlink_to(real)
    except OSError:pytest.skip('Symlink creation unavailable on this host')
    with pytest.raises(OSError):collector.collect_once(link,tmp_path/'cursor','http://localhost','token')


def test_partial_log_record_waits_without_advancing_cursor(tmp_path,monkeypatch):
    log=tmp_path/'application.jsonl';log.write_text('{"event_id":"partial"')
    monkeypatch.setattr(collector,'post',lambda *a:pytest.fail('Incomplete line must not be sent'))
    cursor=tmp_path/'cursor'
    assert collector.collect_once(log,cursor,'http://localhost','token')==0
    assert not cursor.exists()


@pytest.mark.parametrize('endpoint',['http://remote.example/telemetry/a','https://user:secret@example.test/telemetry/a','http://localhost/other','https://example.test/telemetry/a?token=secret'])
def test_collector_requires_explicit_safe_transport(endpoint):
    with pytest.raises(ValueError):collector.post(endpoint,'not-sent',[])
