FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY . .

RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 mcp && chown -R mcp:mcp /app
USER mcp

ENV MCP_SERVER_HOST=0.0.0.0 \
    MCP_SERVER_PORT=8000
EXPOSE 8000

ENTRYPOINT ["uv", "run", "--frozen", "--no-sync", "mcp-server-huaweicloud-rds-supabase"]
CMD ["-t", "streamable-http"]
