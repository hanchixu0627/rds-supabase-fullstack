"""Auth users management services (GoTrue auth admin API channel).

Adapted from the upstream direct-SQL implementation: the cloud instance has
no direct database connection, so all five tools operate through the official
auth admin API with the service-role key. Field names are mapped back to the
upstream tool contract (app_metadata -> raw_app_meta_data, user_metadata ->
raw_user_meta_data); timestamps keep the GoTrue ISO 8601 text format (a
documented deviation from the Postgres text cast used upstream).
"""

from typing import Any, NoReturn

from huaweicloud_mcp_core import McpToolError

from ..client.rds_supabase_client import RdsSupabaseClient
from ..settings import RdsSupabaseSettings

# Bound the per-request page size; the admin API accepts larger values but a
# bounded window keeps memory predictable for very large limit arguments.
_ADMIN_PAGE_SIZE_CAP = 1000


def _to_auth_user(user: dict[str, Any]) -> dict[str, Any]:
    """Map a GoTrue admin user object to the upstream tool row shape."""
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "role": user.get("role"),
        "created_at": user.get("created_at"),
        "last_sign_in_at": user.get("last_sign_in_at"),
        "raw_app_meta_data": user.get("app_metadata"),
        "raw_user_meta_data": user.get("user_metadata"),
    }


def _to_updated_auth_user(user: dict[str, Any]) -> dict[str, Any]:
    """Upstream update returns the row including updated_at."""
    return {**_to_auth_user(user), "updated_at": user.get("updated_at")}


def _admin_error_message(body: Any) -> str:
    if isinstance(body, dict):
        for key in ("msg", "message", "error"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
    return str(body) if body else "unknown auth admin API error"


class AuthUsersService:
    """Implementations of the auth users tool group (admin API channel)."""

    def __init__(
        self,
        client: RdsSupabaseClient | None = None,
        settings: RdsSupabaseSettings | None = None,
    ) -> None:
        self._client = client or RdsSupabaseClient.shared()
        self._settings = settings or self._client.settings

    def _require_admin_channel(self, action: str) -> None:
        if not self._client.is_service_role_available():
            raise McpToolError(
                "MCP_CONFIG_ERROR",
                f"Service role key (SUPABASE_SERVICE_ROLE_KEY) is required to "
                f"{action} auth users.",
            )

    def _raise_admin_error(self, status: int, body: Any, action: str) -> NoReturn:
        if status == 0:
            raise McpToolError(
                "MCP_AUTH_ADMIN_ERROR",
                f"Auth admin API request failed while trying to {action}: "
                f"{_admin_error_message(body)}",
            )
        raise McpToolError(
            "MCP_AUTH_ADMIN_ERROR",
            f"Auth admin API returned {status} while trying to {action}: "
            f"{_admin_error_message(body)}",
        )

    async def list_auth_users(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List users newest first, honouring limit/offset semantics.

        The admin API paginates with page/per_page and sorts by created_at
        desc (verified against the SQL ordering), so the requested
        [offset, offset+limit) window is assembled across up to two pages.
        """
        self._require_admin_channel("list")
        per_page = min(limit, _ADMIN_PAGE_SIZE_CAP)
        collected: list[dict[str, Any]] = []
        page = offset // per_page + 1
        skip = offset % per_page
        first_page = True
        while len(collected) < limit:
            status, body = await self._client.auth_admin_list_users(
                page=page, per_page=per_page
            )
            if status != 200:
                self._raise_admin_error(status, body, "list auth users")
            page_users: list[dict[str, Any]] = (
                body.get("users", []) if isinstance(body, dict) else []
            )
            take_from = skip if first_page else 0
            first_page = False
            need = limit - len(collected)
            collected.extend(page_users[take_from : take_from + need])
            if len(page_users) < per_page:
                break
            page += 1
        return [_to_auth_user(user) for user in collected[:limit]]

    async def get_auth_user(self, *, user_id: str) -> dict[str, Any]:
        """Fetch one user by id."""
        self._require_admin_channel("get")
        status, body = await self._client.auth_admin_get_user(user_id)
        if status == 200 and isinstance(body, dict):
            return _to_auth_user(body)
        if status == 404:
            raise McpToolError("MCP_USER_NOT_FOUND", f"User with ID {user_id} not found.")
        self._raise_admin_error(status, body, "get auth user details")

    async def delete_auth_user(self, *, user_id: str) -> dict[str, Any]:
        """Delete one user by id (structured result, never raises for 404)."""
        self._require_admin_channel("delete")
        status, _body = await self._client.auth_admin_delete_user(user_id)
        if status == 200:
            return {
                "success": True,
                "message": f"Successfully deleted user with ID: {user_id}",
            }
        if status == 404:
            return {
                "success": False,
                "message": f"User with ID {user_id} not found or could not be deleted.",
            }
        self._raise_admin_error(status, _body, "delete auth users")

    async def create_auth_user(
        self,
        *,
        email: str,
        password: str,
        role: str | None = None,
        app_metadata: dict[str, Any] | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a user; password hashing and confirmation are handled by GoTrue.

        The optional role parameter is accepted for upstream signature parity
        but is not forwarded: the admin API always assigns 'authenticated'
        (documented deviation from the upstream raw-SQL role override).
        """
        self._require_admin_channel("create")
        payload: dict[str, Any] = {
            "email": email,
            "password": password,
            "email_confirm": True,
        }
        if app_metadata is not None:
            payload["app_metadata"] = app_metadata
        if user_metadata is not None:
            payload["user_metadata"] = user_metadata
        status, body = await self._client.auth_admin_create_user(payload)
        if status == 200 and isinstance(body, dict):
            return _to_auth_user(body)
        is_duplicate = status == 422 and isinstance(body, dict) and (
            body.get("error_code") == "email_exists"
            or "already" in str(body.get("msg", ""))
        )
        if is_duplicate:
            raise McpToolError(
                "23505", f"User creation failed: Email '{email}' likely already exists."
            )
        raise McpToolError(
            "MCP_USER_CREATION_FAILED",
            f"User creation failed: {_admin_error_message(body)}",
        )

    async def update_auth_user(
        self,
        *,
        user_id: str,
        email: str | None = None,
        password: str | None = None,
        role: str | None = None,
        app_metadata: dict[str, Any] | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update user fields; metadata is replaced as a whole (upstream parity).

        The optional role parameter is accepted for upstream signature parity
        but cannot be forwarded: the admin API does not support role changes.
        Providing only role therefore fails with a clear message instead of
        silently doing nothing.
        """
        if not (email or password or role or app_metadata is not None
                or user_metadata is not None):
            raise McpToolError(
                "MCP_VALIDATION_ERROR",
                "At least one field to update (email, password, role, "
                "app_metadata, user_metadata) must be provided.",
            )
        payload: dict[str, Any] = {}
        if email:
            payload["email"] = email
        if password:
            payload["password"] = password
        if app_metadata is not None:
            payload["app_metadata"] = app_metadata
        if user_metadata is not None:
            payload["user_metadata"] = user_metadata
        if not payload:
            raise McpToolError(
                "MCP_UNSUPPORTED_OPERATION",
                "Updating role is not supported through the auth admin API; "
                "provide email, password, app_metadata or user_metadata.",
            )
        self._require_admin_channel("update")
        status, body = await self._client.auth_admin_update_user(user_id, payload)
        if status == 200 and isinstance(body, dict):
            return _to_updated_auth_user(body)
        if status == 404:
            raise McpToolError(
                "MCP_USER_NOT_FOUND",
                f"User update failed: User with ID {user_id} not found or no rows affected.",
            )
        is_duplicate = (
            status == 500
            and isinstance(body, dict)
            and str(body.get("code")) == "23505"
        )
        if is_duplicate:
            raise McpToolError(
                "23505",
                f"User update failed: Email '{email}' likely already exists "
                f"for another user.",
            )
        raise McpToolError(
            "MCP_USER_UPDATE_FAILED",
            f"User update failed: {_admin_error_message(body)}",
        )
