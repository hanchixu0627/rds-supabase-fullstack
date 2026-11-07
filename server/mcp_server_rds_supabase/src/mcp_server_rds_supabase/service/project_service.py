"""Project URL, JWT secret, type generation and pg_net hook services."""

import re
import sys
from typing import Any

from ..client.rds_supabase_client import RdsSupabaseClient
from ..settings import RdsSupabaseSettings
from . import support

_SCHEMA_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
_SCHEMA_DISPLAY_PATTERN = re.compile(r"[^\w-]", re.ASCII)
_WINDOWS_DRIVE_PATTERN = re.compile(r"^/[a-zA-Z]:")


def _log(message: str) -> None:
    """Mirror one upstream console.error line on stderr."""
    print(message, file=sys.stderr, flush=True)


class ProjectService:
    """Implementations of the project tool group."""

    def __init__(
        self,
        client: RdsSupabaseClient | None = None,
        settings: RdsSupabaseSettings | None = None,
    ) -> None:
        self._client = client or RdsSupabaseClient.shared()
        self._settings = settings or self._client.settings

    async def get_project_url(self) -> dict[str, Any]:
        """Return the configured Supabase project URL."""
        return {"project_url": self._client.get_supabase_url()}

    async def verify_jwt_secret(self) -> dict[str, Any]:
        """Report whether the JWT secret is configured, without echoing it."""
        status = "found" if self._client.get_jwt_secret() else "not_configured"
        return {"jwt_secret_status": status}

    async def rebuild_hooks(self) -> dict[str, Any]:
        """Attempt to restart the pg_net worker, reporting failures inline."""
        restart_sql = "SELECT net.worker_restart()"
        try:
            _log("Attempting to restart pg_net worker...")
            result = await self._client.execute_sql(
                query=restart_sql, read_only=False
            )
            if support.is_sql_error_response(result):
                error = result["error"]
                not_found = error.get("code") == "42883"
                message = (
                    f"Failed to restart pg_net worker: {error.get('message')}"
                    f"{' (Is pg_net installed and enabled?)' if not_found else ''}"
                )
                _log(message)
                return {"success": False, "message": message}
            _log("pg_net worker restart requested successfully.")
            return {"success": True, "message": "pg_net worker restart requested successfully."}
        except Exception as exc:
            error_message = str(exc)
            _log(f"Exception attempting to restart pg_net worker: {error_message}")
            return {
                "success": False,
                "message": f"Exception attempting to restart pg_net worker: {error_message}",
            }

    async def generate_typescript_types(
        self,
        *,
        included_schemas: list[str] | None = None,
        output_filename: str = "database.types.ts",
        output_path: str,
    ) -> dict[str, Any]:
        """Report that type generation is unavailable (no direct connection).

        The upstream implementation shells out to the Supabase CLI against a
        direct database connection; direct connections are not supported on
        this deployment (0.4.0), so the tool answers with a structured
        failure pending a rework decision.
        """
        return {
            "success": False,
            "message": (
                "Error: Direct database connections are not supported on this "
                "deployment. Cannot generate types."
            ),
            "platform": sys.platform,
        }
