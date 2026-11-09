import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from huaweicloud_mcp_core.errors import McpToolError
from mcp_server_supabase.service.operations import Operations
from mcp_server_supabase.service.plans import PlanStore

class CreationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'requests.json';self.file.touch(mode=0o600)
        self.env=patch.dict(os.environ,{'SUPABASE_REQUESTS_FILE':str(self.file),'SUPABASE_ENABLE_WRITES':'true','HUAWEICLOUD_MCP_READ_ONLY':'false'});self.env.start();self.addCleanup(self.env.stop)
        self.client=AsyncMock();self.client.endpoint='https://example.invalid';self.client.project='project';self.client.token='fixture'
        self.ops=Operations(self.client,PlanStore(Path(self.tmp.name)/'ledger.db'))
        self.body={'name':'test-app','basic_config':{'region':'region-1','vpc_id':'vpc-id','subnet_id':'subnet-id'},'version':'1.2.3','mode':'Single','flavor_ref':'rds.supabase.a.b.c','availability_zone':'region-1a','password':'fixture-secret','storage_component':{'enabled':False},'manage_type':'existed_instance','existing_instance':{'instance_id':'pg-id','database_name':'supabase','database_pwd':'fixture-secret'}}
    def save(self):self.file.write_text(json.dumps({'create':self.body}))
    async def test_create_existing_is_secret_free_and_returns_all_ids(self):
        self.save();preview=await self.ops.create_reference('create')
        self.assertNotIn('fixture-secret',str(preview));self.client.request.assert_not_awaited()
        self.client.request.return_value=(202,{'job_id':'job','application_id':'app','instance_id':'pg','instance_job_id':'pgjob'})
        result=await self.ops.create_reference('create',True,preview['plan_id'])
        self.assertEqual(result['application_id'],'app');self.assertFalse(result['completion_verified'])
        self.assertEqual(self.client.request.call_args.args,('POST','/v3/{project}/ai-application/supabases'))
        with self.assertRaises(McpToolError):await self.ops.create_reference('create',True,preview['plan_id'])
        self.assertEqual(self.client.request.await_count,1)
    async def test_no_ha_or_implicit_branch_or_unknown_fields(self):
        for key,value in [('mode','Ha'),('manage_type','guess'),('extra','secret')]:
            body=copy.deepcopy(self.body);body[key]=value;self.file.write_text(json.dumps({'create':body}))
            with self.assertRaises(McpToolError):await self.ops.create_reference('create')
        self.client.request.assert_not_awaited()
    async def test_new_pg_validates_branch_and_postpaid_only(self):
        del self.body['existing_instance'];self.body['manage_type']='newly_instance'
        self.body['managed_instance']={'datastore':{'type':'PostgreSQL','version':'16'},'charge_info':{'charge_mode':'postPaid'},'flavor_ref':'pg-flavor','volume':{'type':'CLOUDSSD','size':100},'availability_zone':'region-1a','security_group_id':'11111111-1111-4111-8111-111111111111','password':'fixture-secret','enterprise_project_id':'0'}
        self.save();preview=await self.ops.create_reference('create');self.assertNotIn('fixture-secret',str(preview))
        self.body['managed_instance']['charge_info']['charge_mode']='prePaid';self.save()
        with self.assertRaises(McpToolError):await self.ops.create_reference('create')
    async def test_unexpected_order_and_transport_result_are_not_success(self):
        self.save();preview=await self.ops.create_reference('create')
        self.client.request.return_value=(202,{'order_id':'order'})
        with self.assertRaises(McpToolError):await self.ops.create_reference('create',True,preview['plan_id'])
        self.assertEqual(self.ops.plans.inspect(preview['plan_id'])['state'],'unknown')
