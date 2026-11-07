"""Gateway client for RDS Supabase (PostgREST RPC + auth admin API).

Direct database connections are intentionally not supported (0.4.0): the
cloud instance is only reachable through the Kong gateway, so SQL runs over
the hardened `execute_sql` RPC with the service-role key.
"""

import logging
from typing import Any

import httpx

from ..settings import RdsSupabaseSettings

logger = logging.getLogger(__name__)

SqlExecutionResult = Any  # list[dict[str, Any]] rows, or {"error": {...}}


class RdsSupabaseClient:
    """Gateway client for the RDS Supabase MCP server."""

    def __init__(
        self,
        settings: RdsSupabaseSettings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http = http_client
        self.rpc_function_exists = False

    _shared_client: "RdsSupabaseClient | None" = None

    @classmethod
    def shared(cls) -> "RdsSupabaseClient":
        """Process-lifetime client, mirroring the upstream single client."""
        if cls._shared_client is None:
            cls._shared_client = cls(RdsSupabaseSettings.from_env())
        return cls._shared_client

    # ------------------------------------------------------------------ RPC

    async def _post_rpc(self, key: str, payload: dict[str, Any]) -> httpx.Response:
        url = f"{self._settings.url}/rest/v1/rpc/execute_sql"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if self._http is not None:
            return await self._http.post(url, headers=headers, json=payload)
        async with httpx.AsyncClient(timeout=None) as one_shot:
            return await one_shot.post(url, headers=headers, json=payload)

    async def _rpc_call(
        self, key: str, *, label: str, payload: dict[str, Any]
    ) -> SqlExecutionResult:
        try:
            resp = await self._post_rpc(key, payload)
        except Exception as exc:
            return {
                "error": {
                    "message": f"Exception during {label} call: {exc}",
                    "code": "MCP_RPC_EXCEPTION",
                }
            }
        if resp.status_code != 200:
            try:
                body: dict[str, Any] = resp.json()
            except Exception:
                body = {}
            return {
                "error": {
                    "message": body.get("message"),
                    "code": body.get("code"),
                    "details": body.get("details"),
                    "hint": body.get("hint"),
                }
            }
        try:
            data: Any = resp.json()
        except Exception:
            data = None
        if isinstance(data, list):
            return data
        logger.error("Unexpected response format from execute_sql RPC: %s", data)
        return {
            "error": {
                "message": (
                    "Unexpected response format from execute_sql RPC. Expected JSON array."
                ),
                "code": "MCP_RPC_FORMAT_ERROR",
            }
        }

    async def execute_sql_via_rpc(
        self, query: str, read_only: bool = False
    ) -> SqlExecutionResult:
        """Execute SQL through the anon-key RPC channel."""
        if not self.rpc_function_exists:
            logger.error(
                "Attempted to call executeSqlViaRpc, but RPC function is not available."
            )
            return {
                "error": {
                    "message": (
                        "execute_sql RPC function not found or client not properly initialized."
                    ),
                    "code": "MCP_CLIENT_ERROR",
                }
            }
        logger.info("Executing via RPC (readOnly: %s): %s...", read_only, query[:100])
        return await self._rpc_call(
            self._settings.anon_key,
            label="RPC",
            payload={"query": query, "read_only": read_only},
        )

    async def execute_sql_via_service_role_rpc(
        self, query: str, read_only: bool = False
    ) -> SqlExecutionResult:
        """Execute SQL through the privileged service-role RPC channel."""
        if not self._settings.service_role_key:
            return {
                "error": {
                    "message": (
                        "Service role key not configured. Cannot execute privileged SQL via RPC."
                    ),
                    "code": "MCP_CONFIG_ERROR",
                }
            }
        if not self.rpc_function_exists:
            logger.error(
                "Attempted to call executeSqlViaServiceRoleRpc, "
                "but RPC function is not available."
            )
            return {
                "error": {
                    "message": (
                        "execute_sql RPC function not found or client not properly initialized."
                    ),
                    "code": "MCP_CLIENT_ERROR",
                }
            }
        logger.info(
            "Executing via Service Role RPC (readOnly: %s): %s...",
            read_only,
            query[:100],
        )
        return await self._rpc_call(
            self._settings.service_role_key,
            label="Service Role RPC",
            payload={"query": query, "read_only": read_only},
        )

    # ------------------------------------------------------- sql channel

    async def execute_sql(
        self, query: str, read_only: bool = True
    ) -> SqlExecutionResult:
        """Run SQL over the service-role RPC channel."""
        if self.is_service_role_available():
            logger.info("Using service role RPC method...")
            return await self.execute_sql_via_service_role_rpc(query, read_only)
        return {
            "error": {
                "message": (
                    "Service role key (SUPABASE_SERVICE_ROLE_KEY) is not configured. "
                    "Cannot execute SQL."
                ),
                "code": "MCP_CONFIG_ERROR",
            }
        }

    # ----------------------------------------------------------------- probe

    async def check_and_create_rpc_function(self) -> None:
        """Probe execute_sql and deploy the hardened DDL when possible."""
        key = self._settings.service_role_key or self._settings.anon_key
        if not self._settings.service_role_key:
            logger.warning(
                "Checking execute_sql with anon key - this will fail if function exists "
                "but is restricted to service_role."
            )
        try:
            resp = await self._post_rpc(key, {"query": "SELECT 1"})
        except Exception as exc:
            self.rpc_function_exists = False
            raise RuntimeError(f"Exception during RPC function check/creation: {exc}") from exc
        if resp.status_code == 200:
            logger.info("'public.execute_sql' function found.")
            self.rpc_function_exists = True
            return
        try:
            body: dict[str, Any] = resp.json()
        except Exception:
            body = {}
        code = body.get("code")
        if code not in ("42883", "PGRST202"):
            logger.error(
                "Unexpected error checking for 'public.execute_sql' function: %s", body
            )
            self.rpc_function_exists = False
            raise RuntimeError(f"Error checking for execute_sql function: {body.get('message')}")
        logger.warning(
            "'public.execute_sql' function not found (Code: %s). Direct database "
            "connections are not supported; deploy sql/mcp-execute-sql.sql via the "
            "management console to enable the SQL channel.",
            code,
        )
        self.rpc_function_exists = False

    # ------------------------------------------------------------- auth admin

    async def _admin_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        """Call the GoTrue auth admin API with the service-role key.

        Returns (HTTP status, parsed JSON body). A transport failure is
        reported as status 0 with the error text in body["msg"].
        """
        key = self._settings.service_role_key
        assert key is not None  # guarded by the service precheck
        url = f"{self._settings.url}{path}"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        try:
            if self._http is not None:
                resp = await self._http.request(
                    method, url, headers=headers, params=params, json=json_body
                )
            else:
                async with httpx.AsyncClient(timeout=None) as one_shot:
                    resp = await one_shot.request(
                        method, url, headers=headers, params=params, json=json_body
                    )
        except Exception as exc:
            return 0, {"msg": f"Exception during auth admin call: {exc}"}
        try:
            body: Any = resp.json() if resp.content else None
        except ValueError:
            body = None
        return resp.status_code, body

    async def auth_admin_list_users(
        self, *, page: int, per_page: int
    ) -> tuple[int, Any]:
        """List users page-by-page (GoTrue sorts by created_at desc)."""
        return await self._admin_request(
            "GET",
            "/auth/v1/admin/users",
            params={"page": page, "per_page": per_page},
        )

    async def auth_admin_get_user(self, user_id: str) -> tuple[int, Any]:
        """Fetch a single user by id."""
        return await self._admin_request("GET", f"/auth/v1/admin/users/{user_id}")

    async def auth_admin_create_user(
        self, payload: dict[str, Any]
    ) -> tuple[int, Any]:
        """Create a user through the auth admin API."""
        return await self._admin_request("POST", "/auth/v1/admin/users", json_body=payload)

    async def auth_admin_update_user(
        self, user_id: str, payload: dict[str, Any]
    ) -> tuple[int, Any]:
        """Update a user through the auth admin API."""
        return await self._admin_request(
            "PUT", f"/auth/v1/admin/users/{user_id}", json_body=payload
        )

    async def auth_admin_delete_user(self, user_id: str) -> tuple[int, Any]:
        """Delete a user through the auth admin API."""
        return await self._admin_request("DELETE", f"/auth/v1/admin/users/{user_id}")

    # --------------------------------------------------------------- getters

    @property
    def settings(self) -> RdsSupabaseSettings:
        """Settings this client was constructed with."""
        return self._settings

    def get_supabase_url(self) -> str:
        return self._settings.url

    def get_anon_key(self) -> str:
        return self._settings.anon_key

    def get_service_role_key(self) -> str | None:
        return self._settings.service_role_key

    def get_jwt_secret(self) -> str | None:
        return self._settings.jwt_secret

    def is_service_role_available(self) -> bool:
        return bool(self._settings.service_role_key)
