import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from huaweicloud_mcp_core.errors import McpToolError
from mcp_server_supabase.service.operations import Operations
from mcp_server_supabase.service.plans import PlanStore

class ReconcileTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.client=AsyncMock();self.client.endpoint='https://example.invalid';self.client.project='project';self.client.token='fixture'
        self.store=PlanStore(Path(self.temp.name)/'plans.db');self.ops=Operations(self.client,self.store)
        self.body={'enable_anonymous_users':True}

    async def accepted(self):
        preview=await self.ops.mutate('app','auth_flags',self.body)
        self.client.request.side_effect=[(200,{'id':'app','status':'normal'}),(202,{'job_id':'job-1'})]
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            await self.ops.mutate('app','auth_flags',self.body,True,preview['plan_id'])
        self.client.request.reset_mock(side_effect=True)
        return preview['plan_id']

    def evidence(self, status='Completed', value=True, target='app'):
        self.client.request.side_effect=[(200,{'job':{'id':'job-1','status':status}}),
            (200,{'id':target,'status':'normal'}),(200,{'enable_anonymous_users':value})]

    async def test_verified_record_allows_new_plan_not_old_replay(self):
        plan=await self.accepted();self.evidence()
        result=await self.ops.reconcile_auth(plan,'app',self.body)
        self.assertEqual(result['state'],'verified');self.assertTrue(result['resource_verified'])
        self.assertFalse(result['business_verified'])
        self.assertTrue(all(call.args[0]=='GET' for call in self.client.request.call_args_list))
        self.assertEqual(self.store.inspect(plan)['state'],'verified')
        fresh=await self.ops.mutate('app','auth_flags',self.body)
        self.store.claim(fresh['plan_id'],self.store.record(plan)['digest'])
        with self.assertRaises(McpToolError):self.store.claim(plan,self.store.record(plan)['digest'])

    async def test_mismatch_does_not_unlock(self):
        for kwargs in ({'status':'Running'},{'status':'Failed'},{'value':False},{'value':1},{'target':'other'}):
            with self.subTest(kwargs=kwargs):
                plan=await self.accepted();self.evidence(**kwargs)
                with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',self.body)
                self.assertEqual(self.store.inspect(plan)['state'],'accepted')
                # Independent test ledger, not a production recovery mechanism.
                self.store=PlanStore(Path(self.temp.name)/(plan+'.db'));self.ops.plans=self.store

    async def test_changed_parameters_and_identity_rejected_before_network(self):
        plan=await self.accepted()
        for body in ({'enable_anonymous_users':False},{'enable_anonymous_users':True,'enable_account_sign_up':True}):
            with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',body)
        self.client.token='changed'
        with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',self.body)
        self.client.request.assert_not_awaited()

    async def test_readonly_and_unknown_never_unlock(self):
        plan=await self.accepted()
        with patch.dict(os.environ,{'HUAWEICLOUD_MCP_READ_ONLY':'true'}):
            with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',self.body)
        with self.store.connect() as db:db.execute("UPDATE plans SET state='unknown' WHERE id=?",(plan,))
        with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',self.body)
        self.client.request.assert_not_awaited()

    async def test_failed_read_keeps_accepted(self):
        plan=await self.accepted();self.client.request.side_effect=McpToolError('MCP_SDK_ERROR','unavailable')
        with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',self.body)
        self.assertEqual(self.store.inspect(plan)['state'],'accepted')

    async def test_completed_other_job_and_missing_fields_stay_blocked(self):
        plan=await self.accepted()
        self.client.request.side_effect=[(200,{'job':{'id':'other','status':'Completed'}})]
        with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',self.body)
        self.assertEqual(self.store.inspect(plan)['state'],'accepted')
        self.client.request.side_effect=[(200,{'job':{'id':'job-1','status':'Completed'}}),
            (200,{'id':'app','status':'normal'}),(200,{})]
        with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',self.body)
        self.assertEqual(self.store.inspect(plan)['state'],'accepted')

    async def test_verify_is_atomic_and_durable(self):
        plan=await self.accepted();record=self.store.record(plan)
        from concurrent.futures import ThreadPoolExecutor
        def verify():
            try:return self.store.verify_auth(plan,record['digest'],record['job_id'])['state']
            except McpToolError:return 'blocked'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:verify(),range(2)))
        self.assertEqual(sorted(results),['blocked','verified'])
        fresh=PlanStore(self.store.path).inspect(plan)
        self.assertEqual(fresh['state'],'verified');self.assertIsInstance(fresh['resource_checked_at'],float)
        self.assertNotIn('digest',fresh)

    def test_legacy_database_keeps_records(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('CREATE TABLE plans (id TEXT PRIMARY KEY, digest TEXT, expires REAL, state TEXT, job TEXT)')
            db.execute("INSERT INTO plans VALUES ('legacy','digest',0,'unknown',NULL)")
        # Detect fixture handle leaks on every OS, not only Windows cleanup.
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute('SELECT 1')
        result=self.store.inspect('legacy')
        self.assertEqual(result['state'],'unknown')
        self.assertFalse(result['resource_verified'])

    async def test_malformed_read_fails_without_ledger_change(self):
        plan=await self.accepted()
        for responses in ([(200,{'job':{'id':'job-1','status':'Completed'}}),(200,[])],
                          [(200,{'job':{'id':'job-1','status':'Completed'}}),(200,{'id':'app','status':'normal'}),(200,[]) ]):
            self.client.request.side_effect=responses
            with self.assertRaises(McpToolError):await self.ops.reconcile_auth(plan,'app',self.body)
            self.assertEqual(self.store.inspect(plan)['state'],'accepted')
