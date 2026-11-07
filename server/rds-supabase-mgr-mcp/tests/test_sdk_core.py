import unittest
from unittest.mock import patch
import test_http as fixtures
Handler=fixtures.Handler
from huaweicloud_mcp_core.errors import McpToolError

class SdkTests(fixtures.HttpTests):
    setUpClass=classmethod(fixtures.HttpTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.HttpTests.tearDownClass.__func__)
    def setUp(self):
        fixtures.HttpTests.setUp(self)
        from mcp_server_supabase.client.sdk_core import SdkCoreClient
        self.sdk=SdkCoreClient(self.client.endpoint,'project','test-ak','test-sk',allow_loopback=True)
        self.client=self.sdk
        self.service.client=self.sdk

    async def test_signed_request_and_null_body(self):
        status,data=await self.sdk.request('PUT','/v3/{project}/ai-application/app/supabase/api-key/key-1/reset')
        self.assertEqual(status,202)
        self.assertEqual(data['job_id'],'job-1')
        self.assertEqual(Handler.calls[-1][2],b'')
        self.assertIsNone(Handler.calls[-1][3])
        self.assertTrue(Handler.authorization.startswith('SDK-HMAC-SHA256'))

    async def test_sdk_does_not_retry_or_redirect(self):
        Handler.code=302
        with self.assertRaises(McpToolError):await self.sdk.request('GET','/v3/{project}/jobs')
        self.assertEqual(len(Handler.calls),1)

    async def test_query_encoding_and_secret_filter(self):
        result=await self.service.read('keys','app',10,20)
        self.assertNotIn('smtp_pwd',result['data'])
        self.assertIn('offset=20',Handler.calls[0][1])
        self.assertIsNone(Handler.calls[0][3])

    async def test_sdk_credentials_bind_plan(self):
        from mcp_server_supabase.client.sdk_core import SdkCoreClient
        preview=await self.service.mutate('app','ssl',{'enable_ssl':False})
        self.service.client=SdkCoreClient(self.client.endpoint,'project','other-ak','other-sk',allow_loopback=True)
        with patch.dict(fixtures.os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            with self.assertRaises(McpToolError):
                await self.service.mutate('app','ssl',{'enable_ssl':False},True,preview['plan_id'])
        self.assertTrue(all(call[0]=='GET' for call in Handler.calls))

    async def test_sdk_missing_credentials_never_calls_network(self):
        self.sdk._ak=''
        with self.assertRaises(McpToolError): await self.sdk.request('GET','/v3/{project}/jobs')
        self.assertEqual(Handler.calls,[])

    def test_transport_selection_has_no_silent_fallback(self):
        from mcp_server_supabase.client.sdk_core import configured_client, SdkCoreClient
        with patch.dict(fixtures.os.environ,{'SUPABASE_TRANSPORT':'sdk_core'}):
            self.assertIsInstance(configured_client(),SdkCoreClient)
        with patch.dict(fixtures.os.environ,{'SUPABASE_TRANSPORT':'unknown'}):
            with self.assertRaises(McpToolError): configured_client()

    async def test_temporary_credentials_header(self):
        self.sdk._security_token='fixture-sts'
        await self.sdk.request('GET','/v3/{project}/jobs')
        self.assertEqual(Handler.security_token,'fixture-sts')

    async def test_endpoint_rejects_console_path_without_request(self):
        self.sdk.endpoint='https://example.invalid/console/rest'
        with self.assertRaises(McpToolError): await self.sdk.request('GET','/v3/{project}/jobs')
        self.assertEqual(Handler.calls,[])
