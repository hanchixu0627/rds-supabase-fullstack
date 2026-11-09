import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from huaweicloud_mcp_core.errors import McpToolError

GROUP='11111111-1111-4111-8111-111111111111'
RULE='22222222-2222-4222-8222-222222222222'
class NetworkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from mcp_server_supabase.service.network import Network
        from mcp_server_supabase.service.plans import PlanStore
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.client=AsyncMock();self.client.endpoint='https://vpc.example.invalid';self.client.project='project';self.client.token='fixture'
        self.ops=Network(self.client,PlanStore(Path(self.tmp.name)/'state.db'))
        self.env=patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'});self.env.start();self.addCleanup(self.env.stop)

    async def test_native_single_rule_body_and_no_replay(self):
        preview=await self.ops.add_rule(GROUP,'192.0.2.0/24',8443)
        self.assertEqual(self.client.request.await_count,0)
        self.client.request.side_effect=[(200,{'security_group':{'id':GROUP,'security_group_rules':[]}}),
                                         (201,{'security_group_rule':{'id':RULE,'security_group_id':GROUP}})]
        result=await self.ops.add_rule(GROUP,'192.0.2.0/24',8443,True,preview['plan_id'])
        self.assertEqual(result['resource_id'],RULE)
        body=self.client.request.call_args.kwargs['body']
        self.assertIn('security_group_rule',body);self.assertNotIn('security_group_rules',body)
        self.assertEqual(body['security_group_rule']['priority'],1)
        self.client.request.side_effect=None;self.client.request.return_value=(200,{'security_group':{'id':GROUP,'security_group_rules':[]}})
        with self.assertRaises(McpToolError):await self.ops.add_rule(GROUP,'192.0.2.0/24',8443,True,preview['plan_id'])

    async def test_group_create_is_not_rule_creation(self):
        preview=await self.ops.create_group('app-group')
        self.client.request.return_value=(201,{'security_group':{'id':GROUP}})
        result=await self.ops.create_group('app-group',True,preview['plan_id'])
        self.assertEqual(result['resource_id'],GROUP)
        self.assertEqual(self.client.request.call_args.kwargs['body'],{'security_group':{'name':'app-group'}})

    async def test_delete_checks_ownership(self):
        preview=await self.ops.delete_rule(GROUP,RULE)
        self.client.request.return_value=(200,{'security_group_rule':{'id':RULE,'security_group_id':'other'}})
        with self.assertRaises(McpToolError):await self.ops.delete_rule(GROUP,RULE,True,preview['plan_id'])
        self.assertTrue(all(c.args[0]=='GET' for c in self.client.request.call_args_list))

    async def test_delete_success_keeps_ledger(self):
        preview=await self.ops.delete_rule(GROUP,RULE)
        self.client.request.side_effect=[(200,{'security_group_rule':{'id':RULE,'security_group_id':GROUP}}),(200,{'security_group':{'id':GROUP}}),(204,{})]
        result=await self.ops.delete_rule(GROUP,RULE,True,preview['plan_id'])
        self.assertEqual(result['status'],'applied');self.assertFalse(result['completion_verified'])
        self.assertEqual(self.ops.plans.inspect(preview['plan_id'])['state'],'accepted')

    async def test_invalid_or_world_source_and_readonly(self):
        for source in ('0.0.0.0/0','::/0','invalid'):
            with self.assertRaises(McpToolError):await self.ops.add_rule(GROUP,source,8443)
        with patch.dict(os.environ,{'HUAWEICLOUD_MCP_READ_ONLY':'true'}):
            with self.assertRaises(McpToolError):await self.ops.create_group('app-group',True,'fixture')
        self.client.request.assert_not_awaited()

    async def test_duplicate_rule_prevents_write(self):
        preview=await self.ops.add_rule(GROUP,'192.0.2.0/24',8443)
        self.client.request.return_value=(200,{'security_group':{'id':GROUP,'security_group_rules':[preview['changes']['security_group_rule']]}})
        with self.assertRaises(McpToolError):await self.ops.add_rule(GROUP,'192.0.2.0/24',8443,True,preview['plan_id'])
        self.assertEqual(self.ops.plans.inspect(preview['plan_id'])['state'],'prepared')

    async def test_malformed_mutation_response_keeps_unknown(self):
        preview=await self.ops.create_group('app-group')
        self.client.request.return_value=(202,{})
        with self.assertRaises(McpToolError):await self.ops.create_group('app-group',True,preview['plan_id'])
        self.assertEqual(self.ops.plans.inspect(preview['plan_id'])['state'],'unknown')

    async def test_list_and_show_fixed_paths(self):
        self.client.request.return_value=(200,{'security_groups':[]})
        await self.ops.list_groups(10)
        self.assertEqual(self.client.request.call_args.kwargs['query'],{'limit':10})
        self.client.request.return_value=(200,{'security_group':{'id':GROUP}})
        await self.ops.show_group(GROUP)
        self.assertTrue(self.client.request.call_args.args[1].endswith(GROUP))
