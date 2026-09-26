# verify-atom MCP server — Glama / generic container build
# stdio transport: the checker starts this container and speaks MCP over stdin/stdout.
FROM python:3.12-slim

# Install the released package (zero dependencies)
RUN pip install --no-cache-dir verify-atom-mcp

ENTRYPOINT ["verify-atom-mcp"]
