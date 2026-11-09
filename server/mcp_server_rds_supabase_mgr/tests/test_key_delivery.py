import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from huaweicloud_mcp_core.errors import McpToolError
from mcp_server_supabase.service.operations import Operations
from mcp_server_supabase.service.plans import PlanStore

class KeyDeliveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.output=Path(self.tmp.name).resolve()/'key.txt';self.registry=Path(self.tmp.name)/'requests.json'
        self.registry.write_text(json.dumps({'delivery':{'output_file':str(self.output)}}));self.registry.chmod(0o600)
        self.env=patch.dict(os.environ,{'SUPABASE_REQUESTS_FILE':str(self.registry),'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'});self.env.start();self.addCleanup(self.env.stop)
        self.client=AsyncMock();self.client.endpoint='https://example.invalid';self.client.project='project';self.client.token='fixture'
        self.ops=Operations(self.client,PlanStore(Path(self.tmp.name)/'ledger.db'))
    def responses(self):return [(200,{'id':'app','status':'normal'}),(200,{'total_count':1,'data':[{'id':'key','status':'normal'}]}),(200,{'api_key':'fixture-private-value'})]
    async def test_plaintext_never_returns_to_model_or_ledger(self):
        preview=await self.ops.deliver_key('app','key','delivery')
        self.assertFalse(self.output.exists());self.client.request.assert_not_awaited()
        self.client.request.side_effect=self.responses()
        result=await self.ops.deliver_key('app','key','delivery',True,preview['plan_id'])
        self.assertEqual(self.output.read_text(),'fixture-private-value')
        self.assertNotIn('fixture-private-value',str(result))
        self.assertNotIn(b'fixture-private-value',(Path(self.tmp.name)/'ledger.db').read_bytes())
        self.assertEqual(self.client.request.call_args.args,('GET','/v3/{project}/ai-application/app/supabase/api-key/key/value'))
    async def test_existing_output_not_overwritten_or_fetched(self):
        self.output.write_text('original')
        with self.assertRaises(McpToolError):await self.ops.deliver_key('app','key','delivery')
        self.assertEqual(self.output.read_text(),'original');self.client.request.assert_not_awaited()
    async def test_missing_value_is_unknown_not_success(self):
        preview=await self.ops.deliver_key('app','key','delivery')
        self.client.request.side_effect=self.responses()[:2]+[(200,{'unexpected':'fixture-private-value'})]
        with self.assertRaises(McpToolError) as error:await self.ops.deliver_key('app','key','delivery',True,preview['plan_id'])
        self.assertNotIn('fixture-private-value',str(error.exception))
        self.assertEqual(self.ops.plans.inspect(preview['plan_id'])['state'],'unknown')
