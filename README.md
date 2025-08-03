# Plex MCP Server

> **Notice:**
> This repository is heavily based on [vladimir-tutin/plex-mcp-server](https://github.com/vladimir-tutin/plex-mcp-server). Significant portions of the design, structure, and functionality are derived from the original project.

A powerful Model-Controller-Protocol server for interacting with Plex Media Server, providing a standardized JSON-based interface for automation, scripting, and integration with other tools.

## Overview

Plex MCP Server creates a unified API layer on top of the Plex Media Server API, offering:

- **Standardized JSON responses** for compatibility with automation tools, AI systems, and other integrations
- **Multiple transport methods** (stdio and SSE) for flexible integration options
- **Rich command set** for managing libraries, collections, playlists, media, users, and more
- **Error handling** with consistent response formats
- **Easy integration** with automation platforms (like n8n) and custom scripts

## Installation

Use the supplied `docker-compose.yml` file to deploy the server easily.

### Environment Variables

You can configure the server using environment variables. The following variables are available:

| Variable | Description |
| -------- | ----------- |
| `PLEX_URL` | The URL of your Plex Media Server (e.g., `http://localhost:32400`) |
| `PLEX_TOKEN` | Your Plex authentication token |
| `PLEX_USERNAME` | The username of the Plex user to use for requests (optional) |
| `PERMISSIONS` | Permissions to grant (`read`, `write` or `delete`, higher permission includes the previous permissions) |
| `HOST` | The host to bind the server to (default: `0.0.0.0`) |
| `PORT` | The port to run the server on (default: `8000`) |
| `TRANSPORT` | The transport method to use (`stdio` or `sse`, default: `sse`) |
| `DEBUG` | Enable debug logging (default: `false`) |

## Response Format

All commands return standardized JSON responses for maximum compatibility with various tools, automation platforms, and AI systems. This consistent structure makes it easy to process responses programmatically.

For successful operations, the response typically includes:

```json
{
  "success_field": true,
  "relevant_data": "value",
  "additional_info": {}
}
```

For errors, the response format is:

```json
{
  "error": "Error message describing what went wrong"
}
```

For multiple matches (when searching by title), results are returned as an array of objects with identifying information:

```json
[
  {
    "title": "Item Title",
    "id": 12345,
    "type": "movie",
    "year": 2023
  },
  {
    "title": "Another Item",
    "id": 67890,
    "type": "show",
    "year": 2022
  }
]
```
