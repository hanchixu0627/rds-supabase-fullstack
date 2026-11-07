from huaweicloud_mcp_core.security import ToolRisk,guard
from mcp_server_supabase.service.network import Network

def register(server):
    service=Network()

    @server.tool()
    @guard(risk=ToolRisk.READ)
    async def list_supabase_security_groups(limit:int=10,marker:str|None=None)->dict:
        """Read a VPC security-group page using the independently configured SUPABASE_VPC_ENDPOINT."""
        return await service.list_groups(limit,marker)

    @server.tool()
    @guard(risk=ToolRisk.READ)
    async def show_supabase_security_group(group_id:str)->dict:
        """Read a VPC group and rules. Does not prove which applications share the group."""
        return await service.show_group(group_id)

    @server.tool()
    @guard(risk=ToolRisk.WRITE)
    async def create_supabase_security_group(name:str,confirm:bool=False,plan_id:str|None=None)->dict:
        """Preview then create a native VPC group; no automatic attachment or application ingress."""
        return await service.create_group(name,confirm,plan_id)

    @server.tool()
    @guard(risk=ToolRisk.DANGEROUS)
    async def add_supabase_security_group_rule(group_id:str,source_cidr:str,port:int=8443,confirm:bool=False,plan_id:str|None=None)->dict:
        """Add one TCP ingress rule for a bounded source after confirmation. Verify every shared resource first."""
        return await service.add_rule(group_id,source_cidr,port,confirm,plan_id)

    @server.tool()
    @guard(risk=ToolRisk.DANGEROUS)
    async def delete_supabase_security_group_rule(group_id:str,rule_id:str,confirm:bool=False,plan_id:str|None=None)->dict:
        """Delete only the specified rule after ownership and shared-resource impact checks; can interrupt traffic."""
        return await service.delete_rule(group_id,rule_id,confirm,plan_id)
