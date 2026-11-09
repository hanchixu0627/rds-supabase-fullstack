"""Transport boundary for future verified REST and UniSDK adapters."""
from typing import Protocol


class SupabaseClient(Protocol):
    async def discover_creation_options(self, manage_type: str) -> dict[str, object]: ...
    async def list_certificates(self) -> dict[str, object]: ...


class OfflineClient:
    async def discover_creation_options(self, manage_type: str) -> dict[str, object]:
        return {"source": "offline", "available": False, "options": []}

    async def list_certificates(self) -> dict[str, object]:
        return {"source": "offline", "available": False, "certificates": []}
