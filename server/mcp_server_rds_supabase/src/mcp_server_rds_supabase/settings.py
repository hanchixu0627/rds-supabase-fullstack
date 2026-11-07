"""RDS Supabase MCP server settings loaded from the environment.

Direct database connections are intentionally not supported: the cloud
instance is only reachable through the Kong gateway (0.4.0).
"""

import os
from dataclasses import dataclass, field

from huaweicloud_mcp_core import McpToolError


@dataclass(frozen=True)
class RdsSupabaseSettings:
    """Configuration for the RDS Supabase gateway and optional direct access."""

    url: str = ""
    anon_key: str = field(default="", repr=False)
    service_role_key: str | None = field(default=None, repr=False)
    jwt_secret: str | None = field(default=None, repr=False)
    workspace_path: str = ""
    tools_config_path: str | None = None

    @classmethod
    def from_env(cls) -> "RdsSupabaseSettings":
        """Read settings from the environment, mirroring the upstream CLI validation."""
        url = os.environ.get("SUPABASE_URL", "").strip()
        anon_key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
        if not url:
            raise McpToolError(
                "MCP_CONFIG_ERROR",
                "Error: Supabase URL is required. Use --url or SUPABASE_URL.",
            )
        if not anon_key:
            raise McpToolError(
                "MCP_CONFIG_ERROR",
                "Error: Supabase Anon Key is required. Use --anon-key or SUPABASE_ANON_KEY.",
            )
        return cls(
            url=url.rstrip("/"),
            anon_key=anon_key,
            service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip() or None,
            jwt_secret=os.environ.get("SUPABASE_AUTH_JWT_SECRET", "").strip() or None,
            workspace_path=os.environ.get("RDS_SUPABASE_WORKSPACE_PATH", "").strip() or os.getcwd(),
            tools_config_path=os.environ.get("RDS_SUPABASE_TOOLS_CONFIG", "").strip() or None,
        )
