"""RDS Supabase MCP server and tool registration."""

from huaweicloud_mcp_core import build_server

from . import __version__

mcp = build_server("rds-supabase", version=__version__)

# Bottom-up registration. The import order below is the upstream TypeScript
# tool registration order (database, project, auth_users, storage, platform,
# inspection) and must not be sorted alphabetically.
from .tools import (  # noqa: E402,F401  # isort: skip
    database,
    project,
    auth_users,
    storage,
    platform,
    inspection,
)
