import unittest
from unittest.mock import AsyncMock
from huaweicloud_mcp_core.errors import McpToolError
from mcp_server_supabase.service.operations import Operations

class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_flavors_only_with_explicit_az_mode(self):
        client=AsyncMock();client.request.return_value=(200,{'flavors':[]})
        ops=Operations(client)
        await ops.creation_candidates('flavors','region-1a','Single')
        self.assertEqual(client.request.call_args.args,('GET','/v3/{project}/ai-application/supabase/flavors'))
        self.assertEqual(client.request.call_args.kwargs['query'],{'az_code':'region-1a','mode':'Single'})
        with self.assertRaises(McpToolError):await ops.creation_candidates('flavors','../bad','Single')
        with self.assertRaises(McpToolError):await ops.creation_candidates('flavors','region-1a','guess')

    async def test_managed_candidates_are_not_guessed_resources(self):
        client=AsyncMock();client.request.return_value=(200,{'instances':[]})
        result=await Operations(client).creation_candidates('manageable')
        self.assertEqual(client.request.call_args.kwargs['query'],{'application_type':'supabase'})
        self.assertFalse(result['creation_ready'])
        with self.assertRaises(McpToolError):await Operations(client).creation_candidates('arbitrary')
