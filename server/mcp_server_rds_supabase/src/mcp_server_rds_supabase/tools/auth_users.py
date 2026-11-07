"""Auth users management tools."""

from typing import Any

from huaweicloud_mcp_core import ToolRisk, guard

from ..server import mcp
from ..service.auth_users_service import AuthUsersService
from ..service.support import as_text


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_auth_users(limit: int = 50, offset: int = 0) -> Any:
    """Lists users from the auth.users table.

    Scenario: page through the user directory before creating, updating or
    deleting an account.

    Args:
        limit: Max number of users to return
        offset: Number of users to skip

    Returns:
        Rows of id, email, role, raw metadata and timestamps per user, newest
        first.
    """
    return as_text(await AuthUsersService().list_auth_users(limit=limit, offset=offset))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_auth_user(user_id: str) -> dict[str, Any]:
    """Retrieves details for a specific user from auth.users by their ID.

    Scenario: inspect one account's role and metadata before updating or
    deleting it.

    Args:
        user_id: The UUID of the user to retrieve.

    Returns:
        The user row with id, email, role, raw metadata and timestamps.
    """
    return await AuthUsersService().get_auth_user(user_id=user_id)


@mcp.tool()
@guard(risk=ToolRisk.WRITE)
async def delete_auth_user(user_id: str) -> dict[str, Any]:
    """Deletes a user from auth.users by their ID. Requires service_role key and direct DB connection.

    Scenario: remove an account directly from auth.users when no email
    confirmation flow is involved.

    Args:
        user_id: The UUID of the user to delete.

    Returns:
        Success flag and a message reporting whether the user was deleted.
    """
    return await AuthUsersService().delete_auth_user(user_id=user_id)


@mcp.tool()
@guard(risk=ToolRisk.WRITE)
async def create_auth_user(
    email: str,
    password: str,
    role: str | None = None,
    app_metadata: dict[str, Any] | None = None,
    user_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Creates a new user directly in auth.users. WARNING: Requires plain password, insecure. Use with extreme caution.

    Scenario: seed a service or migration account directly when no
    confirmation email should be sent.

    Args:
        email: The email address for the new user.
        password: Plain text password (min 6 chars). WARNING: Insecure.
        role: User role.
        app_metadata: Optional app metadata.
        user_metadata: Optional user metadata.

    Returns:
        The created user row with id, email, role, raw metadata and
        timestamps.
    """
    return await AuthUsersService().create_auth_user(
        email=email,
        password=password,
        role=role,
        app_metadata=app_metadata,
        user_metadata=user_metadata,
    )


@mcp.tool()
@guard(risk=ToolRisk.WRITE)
async def update_auth_user(
    user_id: str,
    email: str | None = None,
    password: str | None = None,
    role: str | None = None,
    app_metadata: dict[str, Any] | None = None,
    user_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Updates fields for a user in auth.users. WARNING: Password handling is insecure. Requires service_role key and direct DB connection.

    Scenario: change an account's credentials, role or metadata; every
    provided field overwrites the stored value.

    Args:
        user_id: The UUID of the user to update.
        email: New email address.
        password: New plain text password (min 6 chars). WARNING: Insecure.
        role: New role.
        app_metadata: New app metadata (will overwrite existing).
        user_metadata: New user metadata (will overwrite existing).

    Returns:
        The updated user row with id, email, role, raw metadata and
        timestamps.
    """
    return await AuthUsersService().update_auth_user(
        user_id=user_id,
        email=email,
        password=password,
        role=role,
        app_metadata=app_metadata,
        user_metadata=user_metadata,
    )
