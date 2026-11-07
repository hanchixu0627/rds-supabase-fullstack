import unittest
import tempfile
from pathlib import Path
from mcp_server_supabase.service.plans import PlanStore
from mcp_server_supabase.service.network_contracts import ingress_rule
from mcp_server_supabase.service.operations import Operations

class LatestContractsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.service=Operations(plans=PlanStore(Path(self.temp.name)/"state.db"))
    def test_rule_array_and_default_port(self):
        result=ingress_rule('11111111-1111-4111-8111-111111111111','10.0.0.0/24')
        rule=result['security_group_rules'][0]
        self.assertEqual(rule['multiport'],'8443')
        self.assertEqual(rule['protocol'],'TCP')
        self.assertEqual(rule['remote_ip_prefix'],'10.0.0.0/24')
    def test_no_implicit_world_access(self):
        for cidr in ('0.0.0.0/0','::/0','invalid','10.0.0.1/24'):
            with self.assertRaises(ValueError):ingress_rule('11111111-1111-4111-8111-111111111111',cidr)
        with self.assertRaises(ValueError):ingress_rule('../bad','10.0.0.0/24')
    async def test_ssl_preview_has_followup_both_directions(self):
        for enabled in (False,True):
            result=await self.service.mutate('app','ssl',{'enable_ssl':enabled,'cert_id':'cert-123' if enabled else None})
            self.assertTrue(result['warnings'])
            self.assertTrue(result['follow_up'])
            self.assertEqual(result['target_protocol'],'https' if enabled else 'http')
            self.assertEqual(result['execution'],'not_executed')
    async def test_reset_preview_does_not_claim_completion(self):
        result=await self.service.mutate('app','reset_key',{'key_id':'old-key'})
        self.assertFalse(result['completion_verified'])
        self.assertIn('old key ID',' '.join(result['follow_up']))
        self.assertEqual(result['execution'],'not_executed')
