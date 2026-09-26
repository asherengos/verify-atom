<!-- mcp-name: io.github.asherengos/verify-atom -->
# verify_url — MCP server for the verification endpoint ("the atom")

Gives any MCP-compatible agent a `verify_url` tool: POST a URL, get back a
cryptographically signed proof packet (HTTP status, page title, body SHA-256,
DNS resolution, TLS certificate — timestamped and Ed25519-signed).

Every call hits the **live public endpoint**, so every tool result is a real
proof packet whose signature anyone can verify independently.

## Run it

From a checkout (no install needed):

```bash
VRF_BASE_URL=https://asheraistudios.duckdns.org python3 mcp_server.py
```

Or install it as a package (console script `verify-atom-mcp`):

```bash
pip install ./mcp          # from the repo root
VRF_BASE_URL=https://asheraistudios.duckdns.org verify-atom-mcp
```

(PyPI publication is pending — after that, `pip install verify-atom-mcp`
or `uvx verify-atom-mcp` will work directly.)

(`VRF_BASE_URL` defaults to the public deployment. stdio transport, zero
third-party dependencies — the MCP handshake is plain JSON-RPC 2.0.)

## Register it (Claude Code / Claude Desktop)

```json
{
  "mcpServers": {
    "verify-atom": {
      "command": "python3",
      "args": ["/path/to/mcp_server.py"],
      "env": { "VRF_BASE_URL": "https://asheraistudios.duckdns.org" }
    }
  }
}
```

## The tool

- **Name:** `verify_url`
- **Input:** `{ "url": "https://example.com" }`
- **Output:** human-readable summary + the full proof packet as
  `structuredContent` (+ `isError` when the observation itself failed).
- **Trust model:** the packet carries an Ed25519 signature and the signer's
  public key. Fetch the canonical public key from
  `https://asheraistudios.duckdns.org/key` and verify offline — you never
  have to trust the server, the transport, or this wrapper.

## Honesty notes

- Free while the operator is learning what people use it for. No payments,
  no accounts, no API keys in v1.
- Rate limit: 30 `POST /verify` per minute per IP (429 + `Retry-After`).
- Cost to the operator per verification is a small fraction of a cent;
  abuse will get rate-limited, not billed to you.

## Test it

```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"verify_url","arguments":{"url":"https://example.com"}}}' \
 | VRF_BASE_URL=https://asheraistudios.duckdns.org python3 mcp_server.py
```

The last response's `structuredContent` is a real signed packet — verify its
signature against the public key to prove the whole chain.
