import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from mcp_server_supabase.service.plans import PlanStore
from huaweicloud_mcp_core.errors import McpToolError

class PlansTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'plans.db';self.store=PlanStore(self.path)
    def test_expiry_binding(self):
        p=self.store.issue('a',ttl=-1)
        with self.assertRaises(McpToolError):self.store.claim(p['plan_id'],'a')
        p=self.store.issue('a')
        with self.assertRaises(McpToolError):self.store.claim(p['plan_id'],'changed')
    def test_restart_and_equivalent_intent(self):
        p=self.store.issue('a');self.store.claim(p['plan_id'],'a');self.store.finish(p['plan_id'],'unknown')
        fresh=PlanStore(self.path)
        with self.assertRaises(McpToolError):fresh.claim(p['plan_id'],'a')
        q=fresh.issue('a')
        with self.assertRaises(McpToolError):fresh.claim(q['plan_id'],'a')
        self.assertEqual(fresh.inspect(p['plan_id'])['state'],'unknown')
    def test_concurrent_claim(self):
        p=self.store.issue('a')
        def claim(_):
            try:self.store.claim(p['plan_id'],'a');return True
            except McpToolError:return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(claim,range(2))),1)

    def test_cancel_survives_restart_and_cannot_submit(self):
        p = self.store.issue('cancel-me')
        result = self.store.cancel(p['plan_id'])
        self.assertEqual(result['state'], 'cancelled')
        self.assertFalse(result['cloud_cancellation_requested'])
        fresh = PlanStore(self.path)
        self.assertEqual(fresh.cancel(p['plan_id'])['state'], 'cancelled')
        with self.assertRaises(McpToolError):
            fresh.claim(p['plan_id'], 'cancel-me')
        replacement = fresh.issue('cancel-me')
        fresh.claim(replacement['plan_id'], 'cancel-me')

    def test_cancel_missing_or_submitted_does_not_change_execution(self):
        with self.assertRaises(McpToolError) as error:
            self.store.cancel('absent')
        self.assertEqual(error.exception.code, 'MCP_NOT_FOUND')
        for state in ('submitted', 'accepted', 'unknown'):
            p = self.store.issue(state)
            self.store.claim(p['plan_id'], state)
            if state != 'submitted':
                self.store.finish(p['plan_id'], state, 'job-test' if state == 'accepted' else None)
            with self.assertRaises(McpToolError):
                self.store.cancel(p['plan_id'])
            self.assertEqual(self.store.inspect(p['plan_id'])['state'], state)

    def test_cancel_races_with_claim(self):
        import threading
        p = self.store.issue('race')
        barrier = threading.Barrier(2)
        def act(cancel):
            barrier.wait()
            try:
                if cancel:
                    self.store.cancel(p['plan_id'])
                else:
                    self.store.claim(p['plan_id'], 'race')
                return True
            except McpToolError:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(act, (True, False))), 1)
        self.assertIn(self.store.inspect(p['plan_id'])['state'], ('cancelled', 'submitted'))
