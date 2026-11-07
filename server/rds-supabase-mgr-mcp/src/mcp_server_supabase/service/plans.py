"""Local, durable, one-use intent ledger. Stores digests, not request bodies or tokens."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from huaweicloud_mcp_core.errors import McpToolError


def fingerprint(scope):
    return hashlib.sha256(json.dumps(scope,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class PlanStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv('SUPABASE_STATE_FILE', str(Path.home()/'.local/state/huaweicloud-supabase/plans.sqlite3')))

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink():
            raise McpToolError('MCP_GUARDRAIL_BLOCKED','State file must not be a symlink')
        fd=os.open(self.path,os.O_CREAT|os.O_RDWR,0o600);os.close(fd)
        if os.name != 'nt':os.chmod(self.path,0o600)
        db=sqlite3.connect(self.path,timeout=10)
        db.execute('CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, digest TEXT, expires REAL, state TEXT, job TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS verification (plan TEXT PRIMARY KEY, checked_at REAL, kind TEXT)')
        db.commit()
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def issue(self, digest, ttl=600):
        plan=secrets.token_urlsafe(24);expires=time.time()+ttl
        with self.connect() as db:
            db.execute('INSERT INTO plans VALUES (?,?,?,?,NULL)',(plan,digest,expires,'prepared'))
        return {'plan_id':plan,'expires_at':expires}

    def claim(self, plan, digest):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT digest,expires,state FROM plans WHERE id=?',(plan,)).fetchone()
            if not row or row[0]!=digest or row[1]<time.time() or row[2]!='prepared':
                raise McpToolError('MCP_GUARDRAIL_BLOCKED','Plan missing, changed, expired or already used',hint='Preview again only after reconciling prior executions.')
            if db.execute("SELECT 1 FROM plans WHERE digest=? AND state IN ('submitted','accepted','unknown')",(digest,)).fetchone():
                raise McpToolError('MCP_GUARDRAIL_BLOCKED','Equivalent intent has an unresolved execution',hint='Reconcile the recorded operation; do not replay or delete its ledger.')
            db.execute("UPDATE plans SET state='submitted' WHERE id=?",(plan,))

    def finish(self, plan, state, job=None):
        if state not in ('accepted','unknown'):raise ValueError('Invalid execution state')
        with self.connect() as db:
            db.execute("UPDATE plans SET state=?,job=? WHERE id=? AND state='submitted'",(state,job,plan))

    def record(self, plan):
        """Internal only: never expose binding digest as a tool response."""
        with self.connect() as db:
            row=db.execute('SELECT expires,state,job,digest FROM plans WHERE id=?',(plan,)).fetchone()
            evidence=db.execute('SELECT checked_at FROM verification WHERE plan=?',(plan,)).fetchone()
        if not row:raise McpToolError('MCP_NOT_FOUND','Unknown plan')
        return {'plan_id':plan,'expires_at':row[0],'state':row[1],'job_id':row[2],
                'digest':row[3], 'resource_checked_at':evidence[0] if evidence else None}

    def inspect(self, plan):
        result=self.record(plan)
        result.pop('digest')
        return {**result,'resource_verified':result['state']=='verified',
                'business_verified':False,'completion_verified':False}

    def verify_auth(self, plan, digest, job_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state,digest,job FROM plans WHERE id=?',(plan,)).fetchone()
            if row != ('accepted',digest,job_id):
                raise McpToolError('MCP_GUARDRAIL_BLOCKED','Execution record changed; do not release it')
            db.execute("UPDATE plans SET state='verified' WHERE id=?",(plan,))
            db.execute('INSERT INTO verification VALUES (?,?,?)',(plan,time.time(),'auth_flags'))
        return self.inspect(plan)

    def cancel(self, plan):
        """Revoke an unsubmitted local intent atomically; never cancel a cloud task."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM plans WHERE id=?', (plan,)).fetchone()
            if not row:
                raise McpToolError('MCP_NOT_FOUND', 'Unknown plan',
                                   hint='Use the plan ID returned by the preview.')
            if row[0] not in ('prepared', 'cancelled'):
                raise McpToolError('MCP_GUARDRAIL_BLOCKED',
                                   'Submission has started; local cancellation is unavailable',
                                   hint='Inspect the plan and cloud job; the cloud operation may continue.')
            db.execute("UPDATE plans SET state='cancelled' WHERE id=? AND state='prepared'", (plan,))
        return {'plan_id': plan, 'state': 'cancelled', 'execution': 'not_executed',
                'cloud_cancellation_requested': False}
