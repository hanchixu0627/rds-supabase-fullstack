"""Project configuration, type generation and pg_net hook tools."""

from typing import Any

from huaweicloud_mcp_core import ToolRisk, guard

from ..server import mcp
from ..service.project_service import ProjectService

_DEFAULT_INCLUDED_SCHEMAS = ["public"]


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_project_url() -> dict[str, Any]:
    """Returns the configured Supabase project URL for this server.

    Scenario: resolve the REST endpoint base URL before building raw HTTP
    requests against the gateway.

    Args:
        (none)

    Returns:
        The configured project URL.
    """
    return await ProjectService().get_project_url()


@mcp.tool()
@guard(risk=ToolRisk.WRITE)
async def generate_typescript_types(
    included_schemas: list[str] = _DEFAULT_INCLUDED_SCHEMAS,
    output_filename: str = "database.types.ts",
    *,
    output_path: str,
) -> dict[str, Any]:
    """Generates TypeScript types from the database schema using the Supabase CLI (`supabase gen types`) and downloads the file to the specified absolute path. The tool returns the current platform (win32, darwin, linux) to help with path formatting. Requires DATABASE_URL configuration and Supabase CLI installed.

    Scenario: refresh local TypeScript definitions after a schema change so
    frontend code stays fully typed.

    Args:
        included_schemas: Database schemas to include in type generation.
        output_filename: Filename to save the generated types to in the workspace root.
        output_path: Absolute path where to download the generated TypeScript file. Examples: Windows: "C:\\\\path\\\\to\\\\project\\\\database.types.ts", macOS/Linux: "/path/to/project/database.types.ts". This parameter is required.

    Returns:
        Success flag, the generation message, the generated types and saved
        file path when successful, and the current platform identifier.
    """
    return await ProjectService().generate_typescript_types(
        included_schemas=included_schemas,
        output_filename=output_filename,
        output_path=output_path,
    )



@mcp.tool()
@guard(risk=ToolRisk.WRITE)
async def rebuild_hooks() -> dict[str, Any]:
    """Attempts to restart the pg_net worker. Requires the pg_net extension to be installed and available.

    Scenario: reload pg_net after enabling the extension or when database
    hooks stop delivering their HTTP requests.

    Args:
        (none)

    Returns:
        Success flag and a message describing the pg_net worker restart
        attempt.
    """
    return await ProjectService().rebuild_hooks()


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def verify_jwt_secret() -> dict[str, Any]:
    """Checks if the Supabase JWT secret is configured for this server.

    Scenario: confirm JWT secret availability before debugging auth token
    verification failures.

    Args:
        (none)

    Returns:
        The JWT secret configuration status (found or not_configured), never
        the secret itself.
    """
    return await ProjectService().verify_jwt_secret()
