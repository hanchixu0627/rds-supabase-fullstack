"""Offline planning only; no cloud operation or invented resource data."""
import os
from mcp_server_supabase.service.contracts import ssl_body
from mcp_server_supabase.client.base import OfflineClient, SupabaseClient

SCENARIOS = {
    "create": "Single creation via local reference available: existing PG or postPaid new PG; backend policy/live acceptance pending",
    "delete": "Application-only execution available; PG cascade remains unavailable",
    "access": "SSL/EIP/application-password adapters available; certificate discovery and live validation pending",
    "security_group": "Native VPC group query/create and rule add/delete adapters available; shared-resource inventory and live validation pending",
    "apikey": "Metadata/reset and protected local-file key delivery available; automatic new-key correlation unavailable",
    "business_config": "Auth/SMTP/GitHub/confirmation-template/OBS adapters available; omitted SK requires enabled Storage and unchanged AK",
}


class PlanningService:
    def __init__(self, client: SupabaseClient | None = None):
        self.client = client if client is not None else OfflineClient()

    def capabilities(self) -> dict[str, object]:
        return {"mode": "configured_" + os.getenv("SUPABASE_TRANSPORT", "rest"), "generated_supabase_sdk": False, "cloud_verified": False, "input_policy": "reject_unknown_fields", "local_plan_cancellation": "prepared_only", "cloud_execution": "configured_subset", "implemented_operations": ["application queries", "key metadata", "auth query", "job query", "bounded job observation", "accepted Auth plan reconciliation", "SSL", "EIP", "application-only deletion", "key reset", "registration flags", "local request references", "application password", "Auth providers and confirmation template", "OBS full-credential update", "VPC group query/create", "VPC rule add/delete", "creation candidate queries", "Single creation", "protected local key delivery"], "scenarios": SCENARIOS.copy()}

    async def creation(self, manage_type: str) -> dict[str, object]:
        if manage_type not in ("newly_instance", "existed_instance"):
            return {"error": {"code": "MCP_INVALID_ARGS", "message": "Invalid manage_type", "hint": "Use newly_instance or existed_instance"}}
        discovery = await self.client.discover_creation_options(manage_type)
        branch = ["PG version", "PG flavor", "storage type", "parameter template", "enterprise project"] if manage_type == "newly_instance" else ["manageable PG instance", "secure credential reference"]
        return {"status": "planning_only", "execution": "not_executed", "manage_type": manage_type,
                "steps": ["region/project", "AZ/mode", "Supabase flavor", *branch, "VPC/subnet/security group", "prepare a protected local creation request", "preview create_supabase_application"],
                "discovery": discovery, "recommendation": None,
                "missing": ["verified live candidates", "backend password/version/capacity/sale policies", "resource and business acceptance"]}

    async def ssl(self, enable_ssl: bool) -> dict[str, object]:
        if not enable_ssl:
            return {"status": "planning_only", "execution": "not_executed", "request_body": ssl_body(False), "missing": ["verified transport", "job terminal schema", "live state verification"]}
        return {"status": "planning_only", "execution": "not_executed",
                "steps": ["list certificates", "select compatible certificate", "review SSL enable plan", "submit once after execution support exists", "verify application state"],
                "certificates": await self.client.list_certificates(),
                "missing": ["certificate schema/compatibility", "response and SSL effective-state contract"]}
