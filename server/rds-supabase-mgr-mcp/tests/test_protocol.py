"""Exercise the real stdio boundary without cloud credentials or network calls."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_arguments_are_rejected_without_echo_or_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'plans.db'
            env = {**os.environ, 'SUPABASE_STATE_FILE':str(state),
                   'HUAWEICLOUD_MCP_READ_ONLY':'false', 'SUPABASE_ENABLE_WRITES':'false'}
            params = StdioServerParameters(command=sys.executable,
                args=['-m', 'mcp_server_supabase.main'], env=env)
            with tempfile.TemporaryFile(mode='w+') as errors:
                async with stdio_client(params, errlog=errors) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        for name, args in (
                            ('plan_supabase_creation', {'manage_type':'newly_instance'}),
                            ('change_supabase_ssl', {'application_id':'fixture-app','enable_ssl':False}),
                        ):
                            result = await session.call_tool(name, {**args, 'unsupported_marker':'private-marker-value'})
                            payload = result.structured_content or json.loads(result.content[0].text)
                            self.assertEqual(payload.get('error', {}).get('code'), 'MCP_INVALID_ARGS')
                            self.assertNotIn('private-marker-value', str(result))
                        tools = await session.list_tools()
                        self.assertTrue(all(t.input_schema.get('additionalProperties') is False for t in tools.tools))
                errors.seek(0)
                self.assertNotIn('private-marker-value', errors.read())
            self.assertFalse(state.exists(), 'Rejected requests must not issue plans')

    async def test_preview_cancel_and_inspect_over_stdio(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, 'SUPABASE_STATE_FILE':str(Path(directory)/'plans.db'),
                   'HUAWEICLOUD_MCP_READ_ONLY':'false', 'SUPABASE_ENABLE_WRITES':'false'}
            params = StdioServerParameters(command=sys.executable,
                args=['-m', 'mcp_server_supabase.main'], env=env)
            with tempfile.TemporaryFile(mode='w+') as errors:
                async with stdio_client(params, errlog=errors) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool('change_supabase_ssl', {'application_id':'fixture-app','enable_ssl':False})
                        preview = result.structured_content or json.loads(result.content[0].text)
                        self.assertEqual(preview['status'], 'confirmation_required')
                        result = await session.call_tool('cancel_supabase_plan', {'plan_id':preview['plan_id']})
                        cancelled = result.structured_content or json.loads(result.content[0].text)
                        self.assertEqual(cancelled['state'], 'cancelled')
                        self.assertFalse(cancelled['cloud_cancellation_requested'])
                        result = await session.call_tool('inspect_supabase_plan', {'plan_id':preview['plan_id']})
                        state = result.structured_content or json.loads(result.content[0].text)
                        self.assertEqual(state['state'], 'cancelled')
                        result = await session.call_tool('get_supabase_capabilities', {})
                        capabilities = result.structured_content or json.loads(result.content[0].text)
                        self.assertFalse(capabilities['cloud_verified'])

    async def test_local_cancel_obeys_read_only_policy(self):
        from mcp_server_supabase.service.plans import PlanStore
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'plans.db'
            store = PlanStore(state)
            plan = store.issue('readonly-cancel')
            env = {**os.environ, 'SUPABASE_STATE_FILE':str(state),
                   'HUAWEICLOUD_MCP_READ_ONLY':'true', 'SUPABASE_ENABLE_WRITES':'false'}
            params = StdioServerParameters(command=sys.executable,
                args=['-m', 'mcp_server_supabase.main'], env=env)
            with tempfile.TemporaryFile(mode='w+') as errors:
                async with stdio_client(params, errlog=errors) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool('cancel_supabase_plan', {'plan_id':plan['plan_id']})
                        payload = result.structured_content or json.loads(result.content[0].text)
                        self.assertEqual(payload['error']['code'], 'MCP_READ_ONLY')
            self.assertEqual(store.inspect(plan['plan_id'])['state'], 'prepared')

    async def test_auth_reconcile_is_discoverable_and_readonly_guarded(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'plans.db'
            env={k:v for k,v in os.environ.items() if not k.startswith(('HUAWEICLOUD_','SUPABASE_'))}
            env.update({'SUPABASE_STATE_FILE':str(state),'HUAWEICLOUD_MCP_READ_ONLY':'true','SUPABASE_ENABLE_WRITES':'false'})
            params=StdioServerParameters(command=sys.executable,args=['-m','mcp_server_supabase.main'],env=env)
            with tempfile.TemporaryFile(mode='w+') as errors:
                async with stdio_client(params,errlog=errors) as (read,write):
                    async with ClientSession(read,write) as session:
                        await session.initialize()
                        tools=await session.list_tools()
                        self.assertIn('reconcile_supabase_auth_plan',{t.name for t in tools.tools})
                        result=await session.call_tool('reconcile_supabase_auth_plan',{'plan_id':'fixture','application_id':'fixture','enable_anonymous_users':True})
                        payload=result.structured_content or json.loads(result.content[0].text)
                        self.assertEqual(payload['error']['code'],'MCP_READ_ONLY')
            self.assertFalse(state.exists())
