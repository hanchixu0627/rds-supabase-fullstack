from huaweicloud_mcp_core.security import ToolRisk, guard
from mcp_server_supabase.service.planning import PlanningService


def register(server):
    service = PlanningService()

    @server.tool()
    @guard(risk=ToolRisk.READ)
    async def get_supabase_capabilities() -> dict[str, object]:
        """Discover six scenario contract states. Run first; returns offline capabilities, never cloud status."""
        return service.capabilities()

    @server.tool()
    @guard(risk=ToolRisk.READ)
    async def plan_supabase_creation(manage_type: str) -> dict[str, object]:
        """Plan creation without submitting. Args: manage_type is newly_instance or existed_instance. Returns missing contracts and ordered steps, not a deployable plan."""
        return await service.creation(manage_type)

    @server.tool()
    @guard(risk=ToolRisk.READ)
    async def plan_supabase_ssl(enable_ssl: bool = True) -> dict[str, object]:
        """Plan SSL selection without cloud calls. Args: enable_ssl defaults true; false is unconfirmed. Returns planning status and missing contracts."""
        return await service.ssl(enable_ssl)
