import unittest
from mcp_server_supabase.service.planning import PlanningService

class PlanningTests(unittest.IsolatedAsyncioTestCase):
    async def test_branches(self):
        service = PlanningService()
        for branch in ("newly_instance", "existed_instance"):
            result = await service.creation(branch)
            self.assertEqual(result["execution"], "not_executed")
            self.assertIsNone(result["recommendation"])
            self.assertFalse(result["discovery"]["available"])
        self.assertIn("error", await service.creation("unknown"))

    async def test_ssl(self):
        service = PlanningService()
        self.assertEqual((await service.ssl(False))["status"], "planning_only")
        self.assertEqual((await service.ssl(True))["execution"], "not_executed")
        self.assertEqual(len(service.capabilities()["scenarios"]), 6)

    async def test_adapter(self):
        class FixtureClient:
            async def list_certificates(self):
                return {"source": "test_fixture", "certificates": []}
        result = await PlanningService(FixtureClient()).ssl(True)
        self.assertEqual(result["certificates"]["source"], "test_fixture")
        self.assertEqual(result["execution"], "not_executed")
