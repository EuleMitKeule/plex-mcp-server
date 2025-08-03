from async_typer import AsyncTyper
from mcp.server import FastMCP

mcp = FastMCP("plex", warn_on_duplicate_tools=False)
app = AsyncTyper()
