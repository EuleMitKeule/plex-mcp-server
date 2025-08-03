from datetime import datetime

from plexapi.library import Library
from plexapi.server import PlexServer

from plex_mcp_server.const import CONNECTION_TIMEOUT, SESSION_TIMEOUT


class PlexClient:
    def __init__(self, plex_url: str, plex_token: str) -> None:
        self._plex_url = plex_url
        self._plex_token = plex_token
        self._connection: PlexServer | None = None
        self._last_connection_time: float = 0.0

    def _connect(self) -> None:
        """Establish a connection to the Plex server."""
        try:
            self._connection = PlexServer(
                self._plex_url, self._plex_token, timeout=CONNECTION_TIMEOUT
            )
            library: Library = self._connection.library
            _ = library.sections()
        except Exception as e:
            self._connection = None
            self._last_connection_time = 0.0
            raise ConnectionError(
                f"Failed to connect to Plex server at {self._plex_url}: {e}"
            ) from e
        else:
            self._last_connection_time = datetime.now().timestamp()

    @property
    def connection(self) -> PlexServer:
        """Get the current Plex connection."""
        if self._connection is None or (
            datetime.now().timestamp() - self._last_connection_time > SESSION_TIMEOUT
        ):
            self._connect()

        if self._connection is None:
            raise ConnectionError("Failed to connect to Plex server.")

        return self._connection
