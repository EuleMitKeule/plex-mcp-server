import uvicorn
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from plex_mcp_server.common import mcp
from plex_mcp_server.const import PermissionsType, TransportType
from plex_mcp_server.tools.client_tools import PlexClientTools
from plex_mcp_server.tools.collection_tools import PlexCollectionTools
from plex_mcp_server.tools.library_tools import PlexLibraryTools
from plex_mcp_server.tools.media_tools import PlexMediaTools
from plex_mcp_server.tools.playlist_tools import PlexPlaylistTools
from plex_mcp_server.tools.server_tools import PlexServerTools
from plex_mcp_server.tools.sessions_tools import PlexSessionsTools
from plex_mcp_server.tools.user_tools import PlexUserTools


class PlexMcpServer:
    def __init__(
        self,
        plex_url: str,
        plex_token: str,
        plex_username: str | None,
        permissions: PermissionsType,
        host: str,
        port: int,
        transport: TransportType,
        debug: bool,
    ) -> None:
        "Initialize the Plex MCP Server."
        self._plex_url = plex_url
        self._plex_token = plex_token
        self._host = host
        self._port = port
        self._permissions = permissions
        self._transport = transport
        self._debug = debug
        self._sse = SseServerTransport("/messages/")
        self._tools = [
            PlexLibraryTools(plex_url, plex_token, permissions),
            PlexClientTools(plex_url, plex_token, permissions),
            PlexCollectionTools(plex_url, plex_token, permissions),
            PlexMediaTools(plex_url, plex_token, permissions),
            PlexPlaylistTools(plex_url, plex_token, permissions),
            PlexServerTools(plex_url, plex_token, permissions),
            PlexSessionsTools(plex_url, plex_token, permissions),
            PlexUserTools(plex_url, plex_token, plex_username, permissions),
        ]

    async def start(self) -> None:
        "Start the Plex MCP Server."
        match self._transport:
            case TransportType.SSE:
                await self._start_sse()
            case TransportType.STDIO:
                await self._start_stdio()

    async def _start_sse(self) -> None:
        "Start the server using Server-Sent Events (SSE)."
        app = Starlette(
            debug=self._debug,
            routes=[
                Route("/sse", endpoint=self._handle_sse),
                Route("/health", endpoint=self._handle_health),
                Mount("/messages/", app=self._sse.handle_post_message),
            ],
        )
        config = uvicorn.Config(
            app,
            host=self._host,
            port=self._port,
            loop="asyncio",
            http="h11",
            log_level="debug" if self._debug else "info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def _start_stdio(self) -> None:
        "Start the server using standard input/output."
        await mcp.run_stdio_async()

    async def _handle_sse(self, request: Request) -> Response:
        "Handle incoming SSE requests."
        async with self._sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )

        return Response(status_code=204)

    async def _handle_health(self, request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "ok", "service": "plex-mcp-server"})
