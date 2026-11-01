import sqlite3
import pytest
import jobs

@pytest.fixture(autouse=True)
def database(tmp_path,monkeypatch):
    monkeypatch.setenv('WORKFLOW_DEMO_DB',str(tmp_path/'jobs.db'))

def test_submission_durably_records_expected_state():
    job=jobs.submit('document-1','user-1')
    with jobs.connect() as db:row=dict(db.execute('SELECT * FROM jobs WHERE id=?',(job['id'],)).fetchone())
    assert row=={k:v for k,v in job.items() if k!='user_id'} and row['status']=='pending' and row['result'] is None

def test_worker_completes_correct_resource_and_user():
    job=jobs.submit('document-2','user-2')
    result=jobs.process(job['id'])
    assert result=={**{k:v for k,v in job.items() if k!='user_id'},'status':'completed','result':'processed:document-2'}
    with jobs.connect() as db:assert dict(db.execute('SELECT * FROM jobs').fetchone())==result

def test_repeat_processing_preserves_business_result():
    job=jobs.submit('document-3','user-3')
    assert jobs.process(job['id'])==jobs.process(job['id'])
    with jobs.connect() as db:assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==1

def test_controlled_silent_gap_preserves_pending_record():
    job=jobs.submit('resource-0001','user-0001')
    assert jobs.process(job['id'])=={k:v for k,v in job.items() if k!='user_id'}

def test_unknown_job_exception_propagates():
    with pytest.raises(KeyError):jobs.process('missing-job')
