from enum import StrEnum


class TransportType(StrEnum):
    """Enum for transport types used in the MCP server."""

    SSE = "sse"
    STDIO = "stdio"


class PermissionsType(StrEnum):
    """Enum for permissions types used in the MCP server."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"


ENV_PLEX_URL = "PLEX_URL"
ENV_PLEX_TOKEN = "PLEX_TOKEN"
ENV_PLEX_USERNAME = "PLEX_USERNAME"
ENV_HOST = "HOST"
ENV_PORT = "PORT"
ENV_TRANSPORT = "TRANSPORT"
ENV_DEBUG = "DEBUG"
ENV_PERMISSIONS = "PERMISSIONS"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_TRANSPORT = TransportType.SSE
DEFAULT_DEBUG = False
DEFAULT_PERMISSIONS = PermissionsType.READ

CONNECTION_TIMEOUT = 5  # seconds
SESSION_TIMEOUT = 60 * 30  # seconds
