"""Tests for the Streamable HTTP MCP transport (mcp_http_server.py).

The server is started in-process on localhost. One test performs a single
live tools/call against the public verification endpoint — the honest
end-to-end proof that the transport delivers real signed packets. All other
tests stay local (error paths never touch the network).
"""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import mcp_http_server
from mcp_http_server import MCPHandler

MCP_PATH = "/mcp"


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), MCPHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}{MCP_PATH}"
    httpd.shutdown()
    thread.join()


def post(url, payload, session_id=None):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    if session_id:
        req.add_header("Mcp-Session-Id", session_id)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


def parse_sse(body):
    """One JSON-RPC message per SSE `data:` payload."""
    events = []
    for chunk in body.split("\n\n"):
        data = "\n".join(
            line[5:].strip()
            for line in chunk.splitlines()
            if line.startswith("data:")
        )
        if data:
            events.append(json.loads(data))
    return events


@pytest.fixture(scope="module")
def session(server):
    status, headers, body = post(
        server,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
    )
    assert status == 200
    events = parse_sse(body)
    assert len(events) == 1
    assert events[0]["result"]["protocolVersion"] == "2025-11-25"
    sid = headers.get("Mcp-Session-Id")
    assert sid, "initialize must return Mcp-Session-Id"
    # follow the handshake: notifications/initialized -> 202, no body
    status, _, _ = post(
        server, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid
    )
    assert status == 202
    return sid


def test_initialize_negotiates_2025_11_25(session):
    assert session  # negotiated in fixture; reaching here is the assertion


def test_tools_list(server, session):
    status, _, body = post(
        server, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session
    )
    assert status == 200
    tools = parse_sse(body)[0]["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "verify_url" in names


def test_ping(server, session):
    status, _, body = post(
        server, {"jsonrpc": "2.0", "id": 3, "method": "ping"}, session
    )
    assert status == 200
    assert parse_sse(body)[0]["result"] == {}


def test_tools_call_live_signed_packet(server, session):
    """End-to-end: the transport returns a real Ed25519-signed proof packet."""
    status, _, body = post(
        server,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "verify_url",
                "arguments": {"url": "https://example.com"},
            },
        },
        session,
    )
    assert status == 200
    result = parse_sse(body)[0]["result"]
    packet = result["structuredContent"]
    assert packet["verdict"] == "CONFIRMED"
    assert packet["signature"], "packet must carry a real signature"
    assert packet["signing"]["algorithm"] == "Ed25519"
    assert result["isError"] is False


def test_unknown_tool_error(server, session):
    status, _, body = post(
        server,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        },
        session,
    )
    assert status == 200
    err = parse_sse(body)[0]["error"]
    assert err["code"] == -32602


def test_missing_url_param_error(server, session):
    status, _, body = post(
        server,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "verify_url", "arguments": {}},
        },
        session,
    )
    assert status == 200
    err = parse_sse(body)[0]["error"]
    assert err["code"] == -32602
    assert "url" in err["message"]


def test_bad_session_id_rejected(server):
    status, _, _ = post(
        server, {"jsonrpc": "2.0", "id": 7, "method": "tools/list"}, "bogus-session"
    )
    assert status == 404


def test_missing_session_id_rejected(server):
    status, _, _ = post(server, {"jsonrpc": "2.0", "id": 8, "method": "ping"})
    assert status == 400


def test_unknown_method_error(server, session):
    status, _, body = post(
        server, {"jsonrpc": "2.0", "id": 9, "method": "tools/bogus"}, session
    )
    assert status == 200
    assert parse_sse(body)[0]["error"]["code"] == -32601
