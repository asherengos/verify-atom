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

## Streamable HTTP transport (MCP 2025-11-25)

`mcp_http_server.py` exposes the same `verify_url` tool over Streamable
HTTP — the transport required by the Alexa+ track of the Amazon "Build,
Ship, Shape" hackathon (self-hosted MCP server, spec 2025-11-25+). It
reuses `tool_definition()` and `handle_call()` from `mcp_server.py`
unchanged; only the transport differs.

```bash
VRF_MCP_HTTP_PORT=8899 python3 mcp_http_server.py
# verify-atom MCP (Streamable HTTP, 2025-11-25) on http://127.0.0.1:8899/mcp
```

(Env: `VRF_MCP_HTTP_HOST` default `127.0.0.1`, `VRF_MCP_HTTP_PORT`
default `8899`, `VRF_BASE_URL` default the public deployment. Installed
package exposes it as `verify-atom-mcp-http`.)

Full session with curl — initialize, handshake notification, list, call:

```bash
# 1. initialize -> 200 text/event-stream + Mcp-Session-Id response header
curl -s -i -X POST http://127.0.0.1:8899/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
       "params":{"protocolVersion":"2025-11-25","capabilities":{},
                 "clientInfo":{"name":"curl","version":"0"}}}' \
| tee /tmp/init.txt
# HTTP/1.1 200 OK
# Mcp-Session-Id: <session id>
# Content-Type: text/event-stream
#
# event: message
# data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25",
#   "capabilities":{"tools":{}},"serverInfo":{"name":"verify-atom","version":"0.2.0"}}}

SID=$(grep -i '^Mcp-Session-Id:' /tmp/init.txt | tr -d '\r' | cut -d' ' -f2)

# 2. notifications/initialized -> 202, no body
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8899/mcp \
  -H 'Content-Type: application/json' -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
# 202

# 3. tools/list -> verify_url
curl -s -X POST http://127.0.0.1:8899/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
# event: message
# data: {"jsonrpc":"2.0","id":2,"result":{"tools":[{...verify_url...}]}}

# 4. tools/call -> real signed proof packet (hits the live endpoint)
curl -s -X POST http://127.0.0.1:8899/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call",
       "params":{"name":"verify_url","arguments":{"url":"https://example.com"}}}'
# event: message
# data: {"jsonrpc":"2.0","id":3,"result":{"content":[...],
#   "structuredContent":{...signed packet...,"verdict":"CONFIRMED"},...}}
```

Session rules: every request after `initialize` must carry the
`Mcp-Session-Id` header (missing → 400, unknown → 404). Each JSON-RPC
response arrives as one SSE `message` event. Notifications get `202`
with no body. `DELETE /mcp` with the session header ends the session.
`GET /mcp` is `405` (no standalone SSE streams; POST carries everything).

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
