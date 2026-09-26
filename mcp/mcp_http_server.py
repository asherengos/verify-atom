#!/usr/bin/env python3
"""MCP server wrapping the public verification endpoint — Streamable HTTP transport.

Exposes the ATOM ("check this one thing for me, and prove you did") as a
Model Context Protocol server over Streamable HTTP (MCP 2025-11-25), with
zero third-party dependencies (stdlib only).

The server calls the LIVE public endpoint for every verification, so each
tool call produces a real, Ed25519-signed proof packet. Tool logic is reused
unchanged from mcp_server.py (stdio transport); only the transport differs.

Usage:
    VRF_BASE_URL=https://asheraistudios.duckdns.org VRF_MCP_HTTP_PORT=8899 \
        python3 mcp_http_server.py

Protocol: JSON-RPC 2.0 over HTTP (MCP 2025-11-25, Streamable HTTP).
Endpoint: POST /mcp (one SSE `message` event per JSON-RPC response).
"""

import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from mcp_server import SERVER_NAME, handle_call, tool_definition

PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25",)
SERVER_VERSION = "0.2.0"

HOST = os.environ.get("VRF_MCP_HTTP_HOST", "127.0.0.1")
PORT = int(os.environ.get("VRF_MCP_HTTP_PORT", "8899"))
MCP_PATH = "/mcp"

# session_id -> {"created": epoch}
_sessions: dict = {}
_sessions_lock = threading.Lock()


def _request_path(raw_path: str) -> str:
    return urlparse(raw_path).path


def _new_session() -> str:
    sid = secrets.token_urlsafe(24)
    with _sessions_lock:
        _sessions[sid] = {"created": time.time()}
    return sid


def _valid_session(sid: str | None) -> bool:
    if not sid:
        return False
    with _sessions_lock:
        return sid in _sessions


def _drop_session(sid: str) -> bool:
    with _sessions_lock:
        return _sessions.pop(sid, None) is not None


def _rpc_ok(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _rpc_err(msg_id, code: int, message: str) -> dict:
    out = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
    if msg_id is not None:
        out["id"] = msg_id
    return out


def dispatch(msg: dict):
    """Route one JSON-RPC message.

    Returns (response_dict_or_None, new_session_id_or_None).
    A None response means "notification": the HTTP layer answers 202.
    """
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        negotiated = (
            requested
            if requested in SUPPORTED_PROTOCOL_VERSIONS
            else PROTOCOL_VERSION
        )
        return (
            _rpc_ok(
                msg_id,
                {
                    "protocolVersion": negotiated,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            ),
            _new_session(),
        )

    if method is None or method.startswith("notifications/"):
        return None, None  # notification: no response body

    if method == "tools/list":
        return _rpc_ok(msg_id, {"tools": [tool_definition()]}), None
    if method == "tools/call":
        out = handle_call(params.get("name"), params.get("arguments"))
        if "error" in out:
            err = out["error"]
            return _rpc_err(msg_id, err.get("code", -32603), err.get("message", "tool error")), None
        return _rpc_ok(msg_id, out["result"]), None
    if method == "ping":
        return _rpc_ok(msg_id, {}), None
    if msg_id is not None:
        return _rpc_err(msg_id, -32601, f"method not found: {method}"), None
    return None, None


def _sse_body(responses: list) -> bytes:
    chunks = []
    for resp in responses:
        chunks.append("event: message\ndata: " + json.dumps(resp) + "\n\n")
    return "".join(chunks).encode("utf-8")


class MCPHandler(BaseHTTPRequestHandler):
    server_version = "verify-atom-mcp-http/" + SERVER_VERSION
    protocol_version = "HTTP/1.1"

    # -- helpers ---------------------------------------------------------
    def _send(self, status: int, body: bytes = b"", ctype: str = "application/json",
              extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _origin_ok(self) -> bool:
        # Lenient DNS-rebinding guard: only enforced when Origin is present.
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        try:
            ohost = (urlparse(origin).hostname or "").lower()
        except Exception:
            return False
        return ohost in (host, "localhost", "127.0.0.1", "::1")

    # -- verbs -----------------------------------------------------------
    def do_POST(self):
        if _request_path(self.path) != MCP_PATH:
            self._send(404, b'{"error":"not found"}')
            return
        if not self._origin_ok():
            self._send(403, b'{"error":"origin not allowed"}')
            return

        body = self._read_json()
        if body is None:
            self._send(400, json.dumps(
                _rpc_err(None, -32700, "parse error: body must be JSON")).encode())
            return
        messages = body if isinstance(body, list) else [body]
        if not messages or not all(isinstance(m, dict) for m in messages):
            self._send(400, json.dumps(
                _rpc_err(None, -32600, "invalid request")).encode())
            return

        session_id = self.headers.get("Mcp-Session-Id")
        is_init = any(m.get("method") == "initialize" for m in messages)
        if not is_init:
            if not session_id:
                self._send(400, b'{"error":"missing Mcp-Session-Id header"}')
                return
            if not _valid_session(session_id):
                self._send(404, b'{"error":"unknown session"}')
                return

        responses, new_sid = [], None
        for m in messages:
            resp, sid = dispatch(m)
            if resp is not None:
                responses.append(resp)
            if sid:
                new_sid = sid

        if not responses:
            self._send(202)  # notifications only: accepted, no content
            return

        headers = {}
        if new_sid:
            headers["Mcp-Session-Id"] = new_sid
        elif session_id:
            headers["Mcp-Session-Id"] = session_id
        self._send(200, _sse_body(responses),
                   ctype="text/event-stream", extra=headers)

    def do_GET(self):
        if _request_path(self.path) == MCP_PATH:
            # Standalone SSE streams not supported; POST carries everything.
            self.send_response(405)
            self.send_header("Allow", "POST, DELETE")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._send(404, b'{"error":"not found"}')

    def do_DELETE(self):
        if _request_path(self.path) != MCP_PATH:
            self._send(404, b'{"error":"not found"}')
            return
        session_id = self.headers.get("Mcp-Session-Id")
        if not session_id or not _valid_session(session_id):
            self._send(404, b'{"error":"unknown session"}')
            return
        _drop_session(session_id)
        self._send(200, b'{"ok":true}')

    def log_message(self, fmt, *args):  # keep default stderr logging
        super().log_message(fmt, *args)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MCPHandler)
    print(
        f"verify-atom MCP (Streamable HTTP, {PROTOCOL_VERSION}) on "
        f"http://{HOST}:{server.server_address[1]}{MCP_PATH}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
