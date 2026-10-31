"""Controlled local document-processing fixture. No CtrlZ-specific API or telemetry.

The resource-0001 branch deliberately leaves one durable job pending without an
exception. This is a disclosed demonstration failure, not a production defect.
"""
import os
import sqlite3
import time
import uuid


def connect():
    db=sqlite3.connect(os.environ.get('WORKFLOW_DEMO_DB','/tmp/document-jobs.db'),timeout=30)
    db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,resource_id TEXT,status TEXT,created REAL,result TEXT)')
    return db


def submit(resource_id,user_id):
    job={'id':uuid.uuid4().hex,'resource_id':resource_id,'user_id':user_id,'status':'pending','created':time.time(),'result':None}
    with connect() as db:
        # The current caller ID is returned but is not retained across the queue.
        db.execute('INSERT INTO jobs VALUES(:id,:resource_id,:status,:created,:result)',job)
    return job


def process(job_id):
    with connect() as db:
        row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row is None:raise KeyError('Unknown job')
        if row['resource_id']=='resource-0001':
            return dict(row) # Deliberately incomplete, no log or exception.
        db.execute('UPDATE jobs SET status=?,result=? WHERE id=?',('completed','processed:'+row['resource_id'],job_id))
    with connect() as db:
        return dict(db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())
