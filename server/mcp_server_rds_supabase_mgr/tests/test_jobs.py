import unittest
from unittest.mock import AsyncMock
from mcp_server_supabase.service.operations import Operations
from huaweicloud_mcp_core.errors import McpToolError

class JobTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client=AsyncMock()
        self.service=Operations(self.client)

    async def test_completed_empty_progress_is_task_only(self):
        self.client.request.return_value=(200,{'job':{'id':'job-1','status':'Completed','process':'','ended':'now', 'fail_reason':'private-marker','entities':{'secret':'private-marker'}}})
        result=await self.service.job('job-1')
        self.assertEqual(result['task_status'],'completed')
        self.assertFalse(result['completion_verified'])
        self.assertNotIn('private-marker',str(result))

    async def test_unrecognized_or_mismatched_job_never_succeeds(self):
        for payload in ({'jobs':[{'id':'job-1','status':'Completed'}]},
                        {'job':{'id':'different','status':'Completed'}},
                        {'job':{'id':'job-1','status':'Pending'}}, {'job':None}):
            self.client.request.return_value=(200,payload)
            result=await self.service.job('job-1')
            self.assertEqual(result['task_status'],'unknown')
            self.assertFalse(result['completion_verified'])

    async def test_poll_stops_on_terminal(self):
        self.client.request.side_effect=[(200,{'job':{'id':'job-1','status':s}}) for s in ('Running','Completed')]
        result=await self.service.wait_job('job-1',max_attempts=3,interval_seconds=1,sleep=AsyncMock())
        self.assertEqual(result['task_status'],'completed')
        self.assertEqual(result['attempts'],2)
        self.assertEqual(self.client.request.await_count,2)

    async def test_poll_exhaustion_does_not_mean_failure(self):
        self.client.request.return_value=(200,{'job':{'id':'job-1','status':'Running'}})
        result=await self.service.wait_job('job-1',max_attempts=2,interval_seconds=1,sleep=AsyncMock())
        self.assertEqual(result['task_status'],'running')
        self.assertTrue(result['observation_exhausted'])
        self.assertFalse(result['completion_verified'])

    async def test_unknown_failed_and_auth_error_do_not_loop(self):
        for payload, expected in (({},'unknown'),({'job':{'id':'job-1','status':'Failed'}},'failed')):
            self.client.request.reset_mock(side_effect=True)
            self.client.request.return_value=(200,payload)
            result=await self.service.wait_job('job-1',sleep=AsyncMock())
            self.assertEqual(result['task_status'],expected)
            self.assertEqual(self.client.request.await_count,1)
        self.client.request.side_effect=McpToolError('MCP_PERMISSION_DENIED','denied')
        with self.assertRaises(McpToolError):await self.service.wait_job('job-1',sleep=AsyncMock())

    async def test_limits_fail_before_network(self):
        for args in ({'max_attempts':True},{'max_attempts':11},{'interval_seconds':0},{'interval_seconds':6}):
            with self.assertRaises(McpToolError):await self.service.wait_job('job-1',**args)
        self.client.request.assert_not_awaited()

    async def test_inventory_is_scoped_to_supabase(self):
        self.client.request.return_value=(200,{})
        await self.service.read('applications')
        self.assertEqual(self.client.request.call_args.kwargs['query']['type'],'supabase')

    async def test_poll_timeout_retains_uncertainty(self):
        self.client.request.side_effect=TimeoutError()
        result=await self.service.wait_job('job-1')
        self.assertTrue(result['observation_exhausted'])
        self.assertEqual(result['task_status'],'unknown')
        self.assertEqual(self.client.request.await_count,1)
