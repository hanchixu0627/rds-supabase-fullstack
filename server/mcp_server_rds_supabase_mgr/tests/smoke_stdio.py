"""Offline protocol integration; run after installing the project."""
import asyncio
import sys
import os
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    temp = tempfile.TemporaryDirectory()
    params = StdioServerParameters(command=sys.executable, args=['-m', 'mcp_server_supabase.main'], env={**os.environ, 'SUPABASE_STATE_FILE':os.path.join(temp.name,'state.db')})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            assert {t.name for t in result.tools} >= {'get_supabase_capabilities', 'plan_supabase_creation', 'plan_supabase_ssl'}
            for name, args in [('get_supabase_capabilities', {}), ('plan_supabase_creation', {'manage_type': 'newly_instance'}), ('plan_supabase_ssl', {'enable_ssl': True}), ('change_supabase_ssl', {'application_id':'fixture-app','enable_ssl':False}), ('change_supabase_eip', {'application_id':'fixture-app','is_bind':False})]:
                response = await session.call_tool(name, args)
                assert not response.is_error, response
                print(name, "OK")

asyncio.run(main())
