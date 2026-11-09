import tempfile
from pathlib import Path
from mcp_server_supabase.service.plans import PlanStore
import asyncio
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from mcp_server_supabase.client.rest import RestClient
from mcp_server_supabase.service.operations import Operations
from huaweicloud_mcp_core.errors import McpToolError

class Handler(BaseHTTPRequestHandler):
    calls = []
    code = 200
    payload = {'status':'normal', 'id':'app', 'current_actions':[], 'smtp_pwd':'never-return'}
    def log_message(self, *args): pass
    def respond(self):
        body = self.rfile.read(int(self.headers.get('Content-Length',0)))
        type(self).authorization=self.headers.get('Authorization','')
        type(self).security_token=self.headers.get('X-Security-Token')
        type(self).calls.append((self.command,self.path,body,self.headers.get('X-Auth-Token')))
        code = self.code if self.command == 'GET' else 202
        value = (self.keys_payload if '/api-keys' in self.path else self.payload) if self.command == 'GET' else {'job_id':'job-1'}
        self.send_response(code); self.end_headers(); self.wfile.write(json.dumps(value).encode())
    do_GET = respond
    do_POST = respond
    do_PUT = respond
    do_DELETE = respond

class HttpTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls): cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
    def setUp(self):
        Handler.keys_payload={'total_count':1,'data':[{'id':'key-1','status':'normal','type':'secret','name':'test-key'}]}
        Handler.calls=[]; Handler.code=200; Handler.payload={'status':'normal','id':'app','current_actions':[],'smtp_pwd':'never-return'}
        self.client=RestClient(f'http://127.0.0.1:{self.server.server_port}','project','test-token',True)
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.service=Operations(self.client, PlanStore(Path(self.temp.name)/"state.db"))
    async def execute(self, app, action, body, confirm=False):
        preview=await self.service.mutate(app,action,body)
        if not confirm:return preview
        return await self.service.mutate(app,action,body,True,preview['plan_id'])
    async def test_query_encoding_and_secret_filter(self):
        data=await self.service.read('keys','app',10,20)
        self.assertNotIn('smtp_pwd',data['data'])
        self.assertIn('offset=20',Handler.calls[0][1]); self.assertEqual(Handler.calls[0][3],'test-token')
    async def test_preview_and_write_gate(self):
        result=await self.execute('app','ssl',{'enable_ssl':False},False)
        self.assertEqual(result['changes']['cert_id'],None); self.assertEqual(Handler.calls,[])
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'false'}):
            with self.assertRaises(McpToolError): await self.execute('app','delete',None,True)
        self.assertEqual(Handler.calls,[])
    async def test_actual_ssl_request(self):
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            result=await self.execute('app','ssl',{'enable_ssl':False},True)
        self.assertEqual(result['status'],'accepted'); self.assertFalse(result['complete']); self.assertTrue(result['follow_up']); self.assertFalse(result['urls_automatically_modified'])
        self.assertEqual([c[0] for c in Handler.calls],['GET','POST'])
        self.assertEqual(json.loads(Handler.calls[-1][2]),{'enable_ssl':False,'cert_id':None})
    async def test_null_delete_and_reset_body(self):
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            await self.execute('app','delete',None,True)
            await self.execute('app','reset_key',{'key_id':'key-1'},True)
        self.assertEqual(Handler.calls[1][2],b''); self.assertTrue(Handler.calls[-1][1].endswith('/api-key/key-1/reset'))
    async def test_unknown_state_blocks(self):
        Handler.payload={'status':'creating'}
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            with self.assertRaises(McpToolError): await self.execute('app','delete',None,True)
        self.assertEqual(len(Handler.calls),1)
    async def test_no_redirect_or_retry(self):
        Handler.code=302
        with self.assertRaises(McpToolError): await self.service.read('application','app')
        self.assertEqual(len(Handler.calls),1)
    async def test_plain_http_rejected(self):
        client=RestClient('http://example.com','p','test')
        with self.assertRaises(McpToolError): await client.request('GET','/v3/{project}/jobs')
        self.assertEqual(Handler.calls,[])
    async def test_auth_patch_preserves_omission(self):
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            await self.execute('app','auth_flags',{'enable_anonymous_users':False},True)
        self.assertEqual(json.loads(Handler.calls[-1][2]),{'enable_anonymous_users':False})
    async def test_eip_binding_body(self):
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            await self.execute('app','eip',{'is_bind':True,'public_ip_id':'eip-1','public_ip_address':'192.0.2.1'},True)
        self.assertEqual(json.loads(Handler.calls[-1][2])['public_ip_address'],'192.0.2.1')
        self.assertTrue(Handler.calls[-1][1].endswith('/public-eip'))
    async def test_wrong_target_and_readonly_block(self):
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'true'}):
            with self.assertRaises(McpToolError): await self.execute('app','delete',None,True)
        self.assertEqual(Handler.calls,[])
        Handler.payload={'id':'different-app','status':'normal'}
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            with self.assertRaises(McpToolError): await self.execute('app','delete',None,True)
        self.assertEqual(len(Handler.calls),1)
    async def test_plan_binding_and_no_replay_over_http(self):
        preview=await self.service.mutate('app','ssl',{'enable_ssl':False})
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            with self.assertRaises(McpToolError):
                await self.service.mutate('app','ssl',{'enable_ssl':True,'cert_id':'cert-1'},True,preview['plan_id'])
            await self.service.mutate('app','ssl',{'enable_ssl':False},True,preview['plan_id'])
            with self.assertRaises(McpToolError):
                await self.service.mutate('app','ssl',{'enable_ssl':False},True,preview['plan_id'])
        self.assertEqual(sum(c[0]=='POST' for c in Handler.calls),1)
    async def test_unknown_execution_is_durable(self):
        from unittest.mock import AsyncMock
        self.client.request=AsyncMock(side_effect=[(200,{'id':'app','status':'normal'}),McpToolError('MCP_SDK_ERROR','timeout')])
        preview=await self.service.mutate('app','ssl',{'enable_ssl':False})
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            with self.assertRaises(McpToolError):
                await self.service.mutate('app','ssl',{'enable_ssl':False},True,preview['plan_id'])
        fresh=PlanStore(Path(self.temp.name)/'state.db')
        self.assertEqual(fresh.inspect(preview['plan_id'])['state'],'unknown')

    async def test_unbind_must_not_discard_binding_arguments(self):
        with self.assertRaises(McpToolError) as error:
            await self.service.mutate('app', 'eip', {'is_bind':False, 'public_ip_id':'eip-1'})
        self.assertEqual(error.exception.code, 'MCP_INVALID_ARGS')
        self.assertEqual(Handler.calls, [])

    async def test_key_filters_and_whitelist(self):
        Handler.keys_payload = {'total_count':1, 'data':[{'id':'key-1','status':'normal',
            'type':'secret', 'name':'test', 'value':'private-value', 'unknown':'private-value',
            'api_key':'private-value'}], 'unexpected':'private-value'}
        result = await self.service.read('keys','app',20,0,
            status='normal', key_type='secret', sort_key='name', sort_dir='asc')
        self.assertNotIn('private-value', str(result))
        self.assertEqual(result['data']['data'][0], {'id':'key-1','status':'normal','type':'secret','name':'test'})
        self.assertIn('status=normal',Handler.calls[0][1])
        self.assertIn('type=secret',Handler.calls[0][1])
        self.assertIn('sort_key=name',Handler.calls[0][1])

    async def test_invalid_key_filter_never_calls_backend(self):
        with self.assertRaises(McpToolError) as error:
            await self.service.read('keys','app',status='not-a-status')
        self.assertEqual(error.exception.code,'MCP_INVALID_ARGS')
        self.assertEqual(Handler.calls,[])

    async def test_reset_requires_exact_normal_scoped_key(self):
        for response in (
            {'total_count':0,'data':[]},
            {'total_count':1,'data':[{'id':'other','status':'normal'}]},
            {'total_count':1,'data':[{'id':'key-1','status':'deleted'}]},
            {'total_count':2,'data':[{'id':'key-1','status':'normal'},{'id':'key-1','status':'normal'}]},
            {'data':[{'id':'key-1','status':'normal'}]},
            {'total_count':True,'data':[{'id':'key-1','status':'normal'}]},
        ):
            with self.subTest(response=response):
                Handler.calls=[]; Handler.keys_payload=response
                preview=await self.service.mutate('app','reset_key',{'key_id':'key-1'})
                with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
                    with self.assertRaises(McpToolError):
                        await self.service.mutate('app','reset_key',{'key_id':'key-1'},True,preview['plan_id'])
                self.assertTrue(all(c[0]=='GET' for c in Handler.calls))
                self.assertEqual(self.service.plans.inspect(preview['plan_id'])['state'],'prepared')

    async def test_reset_preflight_filters_id_before_single_submission(self):
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            result=await self.execute('app','reset_key',{'key_id':'key-1'},True)
        self.assertEqual(result['status'],'accepted')
        self.assertEqual([c[0] for c in Handler.calls],['GET','GET','PUT'])
        self.assertIn('/app/supabase/api-keys?',Handler.calls[1][1])
        self.assertIn('id=key-1',Handler.calls[1][1])
        self.assertEqual(Handler.calls[-1][2],b'')

    async def test_malformed_key_metadata_fails_closed(self):
        for payload in ({'total_count':1,'data':{}}, {'total_count':-1,'data':[]},
                        {'total_count':1,'data':[{'id':{'value':'private-value'}}]}):
            Handler.keys_payload=payload
            with self.assertRaises(McpToolError):
                await self.service.read('keys','app')

    async def test_read_http_errors_are_actionable_and_do_not_retry(self):
        for status, category in ((400,'invalid_request'),(401,'authentication'),(403,'permission'),
                                 (404,'not_found'),(409,'state_conflict'),(429,'rate_limited'),(503,'service_unavailable')):
            Handler.calls=[]; Handler.code=status
            with self.assertRaises(McpToolError) as caught:
                await self.service.read('application','app')
            recovery=caught.exception.to_dict()['error']['recovery']
            self.assertEqual(recovery['category'],category)
            self.assertFalse(recovery['automatic_retry'])
            self.assertEqual(len(Handler.calls),1)

    async def test_unknown_write_error_includes_plan_for_reconciliation(self):
        from unittest.mock import AsyncMock
        self.client.request=AsyncMock(side_effect=[(200,{'id':'app','status':'normal'}),McpToolError('MCP_SDK_ERROR','private-response')])
        preview=await self.service.mutate('app','ssl',{'enable_ssl':False})
        with patch.dict(os.environ,{'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'}):
            with self.assertRaises(McpToolError) as caught:
                await self.service.mutate('app','ssl',{'enable_ssl':False},True,preview['plan_id'])
        error=caught.exception.to_dict()['error']
        self.assertEqual(error['recovery']['category'],'submission_unknown')
        self.assertEqual(error['recovery']['plan_id'],preview['plan_id'])
        self.assertFalse(error['recovery']['automatic_retry'])
        self.assertNotIn('private-response',str(error))

    async def test_job_uses_single_object_and_drops_freeform_details(self):
        Handler.payload={'job':{'id':'job-1','status':'Completed','process':'','fail_reason':'private-marker'}}
        result=await self.service.job('job-1')
        self.assertEqual(result['task_status'],'completed')
        self.assertFalse(result['completion_verified'])
        self.assertNotIn('private-marker',str(result))
        self.assertIn('/jobs?id=job-1',Handler.calls[0][1])

    async def test_delete_and_eip_preview_describe_retained_costs(self):
        result=await self.service.mutate('app','delete',None)
        self.assertIn('PG',str(result['warnings']))
        result=await self.service.mutate('app','eip',{'is_bind':False})
        self.assertIn('unbinding does not release',str(result['warnings']))
        self.assertEqual(Handler.calls,[])
