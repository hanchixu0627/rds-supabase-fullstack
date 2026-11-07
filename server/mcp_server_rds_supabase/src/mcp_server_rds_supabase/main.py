"""Console entry point."""

import asyncio
import sys

from huaweicloud_mcp_core import McpToolError, run_standard

from .client.rds_supabase_client import RdsSupabaseClient
from .server import mcp
from .settings import RdsSupabaseSettings
from .tools_config import apply_tools_config


async def _startup(settings: RdsSupabaseSettings) -> None:
    """Probe the gateway RPC and apply the tools whitelist."""
    client = RdsSupabaseClient.shared()
    await client.check_and_create_rpc_function()
    await apply_tools_config(settings.tools_config_path, mcp)


def main() -> None:
    """Validate settings, probe the gateway, then run the MCP server."""
    try:
        settings = RdsSupabaseSettings.from_env()
    except McpToolError as exc:
        print(exc.message, file=sys.stderr)
        raise SystemExit(1) from None
    try:
        asyncio.run(_startup(settings))
    except Exception as exc:
        print(f"Error during client initialization: {exc}", file=sys.stderr)
    run_standard(mcp, service_name="rds-supabase")


if __name__ == "__main__":
    main()
