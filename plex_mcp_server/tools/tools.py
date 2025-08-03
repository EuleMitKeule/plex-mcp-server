from abc import ABC

import aiohttp
from mcp.types import AnyFunction

from plex_mcp_server.common import mcp
from plex_mcp_server.const import PermissionsType
from plex_mcp_server.plex_client import PlexClient


class PlexMcpTools(ABC):
    def __init__(
        self,
        plex_url: str,
        plex_token: str,
        permissions: PermissionsType,
        tools: list[AnyFunction],
    ) -> None:
        self._plex_url = plex_url
        self._plex_token = plex_token
        self._plex_client = PlexClient(plex_url, plex_token)
        self._permissions = permissions

        for tool in tools:
            mcp.add_tool(tool)

    @property
    def _plex_headers(self) -> dict:
        """Get standard Plex headers for HTTP requests"""
        return {"X-Plex-Token": self._plex_token, "Accept": "application/json"}

    async def _async_get_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: dict,
    ) -> dict:
        """Helper function to make async HTTP requests"""
        async with session.get(url, headers=headers) as response:
            return await response.json()
