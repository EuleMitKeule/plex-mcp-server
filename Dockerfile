FROM ghcr.io/astral-sh/uv:python3.13-alpine

WORKDIR /app

COPY plex_mcp_server /app/plex_mcp_server
COPY pyproject.toml /app/
COPY README.md /app/
COPY LICENSE.md /app/

RUN uv sync

ENV PLEX_URL=""
ENV PLEX_TOKEN=""
ENV PLEX_USERNAME=""
ENV PERMISSIONS="read"
ENV HOST="0.0.0.0"
ENV PORT="8000"
ENV TRANSPORT="sse"
ENV DEBUG="false"

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "plex_mcp_server"]
