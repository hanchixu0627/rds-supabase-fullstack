import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from huaweicloud_mcp_core.errors import McpToolError
from mcp_server_supabase.service.operations import Operations
from mcp_server_supabase.service.plans import PlanStore

class RequestReferenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.registry=Path(self.tmp.name)/'requests.json'
        self.registry.write_text(json.dumps({'password-change':{'application_password':'fixture-private-secret'}}));self.registry.chmod(0o600)
        self.env=patch.dict(os.environ,{'SUPABASE_REQUESTS_FILE':str(self.registry),'HUAWEICLOUD_MCP_READ_ONLY':'false','SUPABASE_ENABLE_WRITES':'true'})
        self.env.start();self.addCleanup(self.env.stop)
        self.client=AsyncMock();self.client.endpoint='https://example.invalid';self.client.project='project';self.client.token='fixture'
        self.ops=Operations(self.client,PlanStore(Path(self.tmp.name)/'state.db'))

    async def test_password_preview_redacts_and_submission_uses_reference(self):
        preview=await self.ops.mutate_reference('app','password','password-change')
        self.assertNotIn('fixture-private-secret',str(preview))
        self.client.request.side_effect=[(200,{'id':'app','status':'normal'}),(202,{'job_id':'job-1'})]
        result=await self.ops.mutate_reference('app','password','password-change',True,preview['plan_id'])
        self.assertEqual(result['status'],'accepted')
        call=self.client.request.call_args
        self.assertTrue(call.args[1].endswith('/password'))
        self.assertEqual(call.kwargs['body'],{'application_password':'fixture-private-secret'})

    async def test_changed_secret_requires_new_confirmation(self):
        preview=await self.ops.mutate_reference('app','password','password-change')
        self.registry.write_text(json.dumps({'password-change':{'application_password':'changed-private-secret'}}))
        self.client.request.return_value=(200,{'id':'app','status':'normal'})
        with self.assertRaises(McpToolError):await self.ops.mutate_reference('app','password','password-change',True,preview['plan_id'])
        self.assertTrue(all(c.args[0]=='GET' for c in self.client.request.call_args_list))

    async def test_instance_password_and_unknown_field_rejected(self):
        for body in ({'instance_password':'private'},{'application_password':'private','extra':'private'}):
            self.registry.write_text(json.dumps({'bad':body}))
            with self.assertRaises(McpToolError) as error:await self.ops.mutate_reference('app','password','bad')
            self.assertNotIn('private',str(error.exception))
        self.client.request.assert_not_awaited()

    async def test_storage_full_credentials_and_disable(self):
        for body in ({'enabled':True,'type':'obs','bucket_name':'bucket-a','ak':'fixture-ak','sk':'fixture-sk'}, {'enabled':False}):
            self.registry.write_text(json.dumps({'storage':body}))
            preview=await self.ops.mutate_reference('app','storage','storage')
            self.assertNotIn('fixture-sk',str(preview));self.assertNotIn('fixture-ak',str(preview))
        self.registry.write_text(json.dumps({'storage':{'enabled':True,'type':'obs','bucket_name':'bucket-a','ak':'fixture-ak'}}))
        preview=await self.ops.mutate_reference('app','storage','storage')
        self.client.request.return_value=(200,{'id':'app','status':'normal','storage_component':{'enabled':False}})
        with self.assertRaises(McpToolError):await self.ops.mutate_reference('app','storage','storage',True,preview['plan_id'])

    async def test_auth_preserves_omission_and_redacts_nested_secret(self):
        body={'github_oauth_provider':{'enable_github':True,'oauth_client_id':'fixture-client','oauth_client_secret':'fixture-private-secret','redirect_uri':'https://example.invalid/callback'}}
        self.registry.write_text(json.dumps({'oauth':body}))
        preview=await self.ops.mutate_reference('app','auth_config','oauth')
        self.assertNotIn('fixture-private-secret',str(preview))
        self.client.request.side_effect=[(200,{'id':'app','status':'normal'}),(202,{'job_id':'job-1'})]
        await self.ops.mutate_reference('app','auth_config','oauth',True,preview['plan_id'])
        self.assertEqual(self.client.request.call_args.kwargs['body'],body)

    async def test_untrusted_reference_paths_and_permissions_rejected(self):
        for ref in ('../requests.json','/etc/passwd','missing'):
            with self.assertRaises(McpToolError):await self.ops.mutate_reference('app','password',ref)
        if os.name!='nt':
            self.registry.chmod(0o644)
            with self.assertRaises(McpToolError):await self.ops.mutate_reference('app','password','password-change')

    async def test_smtp_template_urls_and_invalid_nested_values(self):
        from mcp_server_supabase.service.request_refs import validate_request,preview_request
        body={'site_url':'https://example.invalid','allow_redirect_urls':'https://example.invalid/a,https://example.invalid/b',
              'email_oauth_provider':{'enable_email_sign_up':True,'enable_email_auto_confirm':False,
                'smtp_config':{'smtp_host':'smtp.example.invalid','smtp_port':587,'smtp_user':'user','smtp_pwd':'fixture-secret','smtp_max_frequency':60}},
              'email_template_config':{'mailer_confirmation':{'subject':'Confirm','url':'https://example.invalid/template?signature=fixture-secret'}}}
        self.assertEqual(validate_request('auth_config',body),body)
        self.assertNotIn('fixture-secret',str(preview_request(body)))
        invalid=[{'email_oauth_provider':{'smtp_config':{'smtp_port':True}}},
                 {'email_oauth_provider':{'smtp_config':{'smtp_max_frequency':-1}}},
                 {'email_oauth_provider':{'enable_email_sign_up':False,'smtp_config':{'smtp_host':'x'}}},
                 {'email_template_config':{'unknown':{'subject':'x'}}},
                 {'email_template_config':{'mailer_confirmation':{}}},
                 {'site_url':'https://user:secret@example.invalid'},
                 {'allow_redirect_urls':','.join(['https://example.invalid']*11)},
                 {'github_oauth_provider':{'enable_github':False,'oauth_client_secret':'secret'}}]
        for item in invalid:
            with self.assertRaises(McpToolError):validate_request('auth_config',item)

    async def test_secret_failure_and_ledger_do_not_expose_body(self):
        preview=await self.ops.mutate_reference('app','password','password-change')
        self.client.request.side_effect=[(200,{'id':'app','status':'normal'}),RuntimeError('fixture-private-secret')]
        with self.assertRaises(McpToolError) as error:
            await self.ops.mutate_reference('app','password','password-change',True,preview['plan_id'])
        self.assertNotIn('fixture-private-secret',str(error.exception))
        self.assertNotIn('fixture-private-secret',str(self.ops.plans.inspect(preview['plan_id'])))
        self.assertNotIn(b'fixture-private-secret',(Path(self.tmp.name)/'state.db').read_bytes())

    async def test_storage_omitted_sk_preserved_only_for_enabled_matching_identity(self):
        body={'enabled':True,'type':'obs','bucket_name':'new-bucket','ak':'fixture-ak'}
        self.registry.write_text(json.dumps({'storage':body}))
        preview=await self.ops.mutate_reference('app','storage','storage')
        self.client.request.side_effect=[(200,{'id':'app','status':'normal','storage_component':{'enabled':True,'ak':'fixture-ak'}}),(202,{'job_id':'job'})]
        await self.ops.mutate_reference('app','storage','storage',True,preview['plan_id'])
        self.assertNotIn('sk',self.client.request.call_args.kwargs['body'])
