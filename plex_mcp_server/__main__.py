from typing import Annotated

import typer
from dotenv import load_dotenv

from plex_mcp_server.common import app
from plex_mcp_server.const import (
    DEFAULT_DEBUG,
    DEFAULT_HOST,
    DEFAULT_PERMISSIONS,
    DEFAULT_PORT,
    DEFAULT_TRANSPORT,
    ENV_DEBUG,
    ENV_HOST,
    ENV_PERMISSIONS,
    ENV_PLEX_TOKEN,
    ENV_PLEX_URL,
    ENV_PLEX_USERNAME,
    ENV_PORT,
    ENV_TRANSPORT,
    PermissionsType,
    TransportType,
)
from plex_mcp_server.server import PlexMcpServer


@app.async_command()
async def main(
    plex_url: Annotated[
        str,
        typer.Option(
            help="Plex URL to connect to.",
            envvar=ENV_PLEX_URL,
        ),
    ],
    plex_token: Annotated[
        str,
        typer.Option(
            help="Plex token for authentication.",
            envvar=ENV_PLEX_TOKEN,
        ),
    ],
    plex_username: Annotated[
        str | None,
        typer.Option(
            help="Plex username for user-specific operations.",
            envvar=ENV_PLEX_USERNAME,
        ),
    ] = None,
    permissions: Annotated[
        PermissionsType,
        typer.Option(
            help="Permissions for the server.",
            envvar=ENV_PERMISSIONS,
        ),
    ] = DEFAULT_PERMISSIONS,
    host: Annotated[
        str,
        typer.Option(help="Host to bind to.", envvar=ENV_HOST),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option(help="Port to listen on.", envvar=ENV_PORT),
    ] = DEFAULT_PORT,
    transport: Annotated[
        TransportType,
        typer.Option(help="Transport method to use.", envvar=ENV_TRANSPORT),
    ] = DEFAULT_TRANSPORT,
    debug: Annotated[
        bool,
        typer.Option(help="Enable debug mode.", envvar=ENV_DEBUG),
    ] = DEFAULT_DEBUG,
) -> None:
    """Main entry point for the application."""

    typer.echo("Starting Plex MCP Server...")
    typer.echo(
        f"Connecting to Plex at {plex_url} with token {plex_token[:4] + '*' * (len(plex_token) - 4)}"
    )
    typer.echo(f"Using transport: {transport}")
    typer.echo(f"Binding to host: {host}")
    typer.echo(f"Listening on port: {port}")
    typer.echo(f"Debug mode: {'enabled' if debug else 'disabled'}")

    plex_mcp_server = PlexMcpServer(
        plex_url=plex_url,
        plex_token=plex_token,
        plex_username=plex_username,
        permissions=permissions,
        host=host,
        port=port,
        transport=transport,
        debug=debug,
    )

    await plex_mcp_server.start()


if __name__ == "__main__":
    load_dotenv()
    app()
