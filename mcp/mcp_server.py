#!/usr/bin/env python3
"""MCP server wrapping the public verification endpoint.

Exposes the ATOM ("check this one thing for me, and prove you did") as a
Model Context Protocol tool over stdio, with zero third-party dependencies.

The server calls the LIVE public endpoint for every verification, so each
tool call produces a real, Ed25519-signed proof packet.

Usage:
    VRF_BASE_URL=https://asheraistudios.duckdns.org python3 mcp_server.py

Protocol: JSON-RPC 2.0 over stdio (MCP 2024-11-05).
"""

import json
import os
import sys
import urllib.request

BASE_URL = os.environ.get("VRF_BASE_URL", "https://asheraistudios.duckdns.org").rstrip("/")
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "verify-atom"
SERVER_VERSION = "0.1.0"


def rpc_request(url: str, payload: dict, timeout: int = 60) -> dict:
    """POST JSON and return the decoded response.

    Retries once on transient transport failures (e.g. a proxy closing an
    idle connection mid-handshake). Requesting a verification is idempotent
    enough for one retry: the worst case is two separately-signed packets.
    """
    import http.client

    data = json.dumps(payload).encode()
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except (
            urllib.error.URLError,
            http.client.RemoteDisconnected,
            http.client.HTTPException,
            ConnectionError,
            TimeoutError,
        ) as exc:
            last_exc = exc
    raise last_exc  # type: ignore[misc]


def tool_definition() -> dict:
    return {
        "name": "verify_url",
        "description": (
            "Observe a public web page and return a cryptographically signed proof "
            "packet: HTTP status, page title, body SHA-256, DNS resolution, and TLS "
            "certificate details, timestamped and Ed25519-signed. Use when you need "
            "verifiable evidence of what a webpage contained — e.g. to back a claim "
            "with proof instead of asking to be trusted. Anyone can independently "
            "verify the packet's signature against the service's published public key."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The public http(s) URL to observe and prove.",
                }
            },
            "required": ["url"],
        },
    }


def handle_call(name: str, arguments: dict) -> dict:
    if name != "verify_url":
        return {"error": {"code": -32602, "message": f"unknown tool: {name}"}}
    url = (arguments or {}).get("url")
    if not isinstance(url, str) or not url:
        return {"error": {"code": -32602, "message": "'url' is required"}}
    try:
        packet = rpc_request(
            f"{BASE_URL}/verify",
            {"type": "http_observation", "url": url},
        )
    except Exception as exc:  # transport-level failure -> JSON-RPC error
        return {"error": {"code": -32000, "message": f"verify request failed: {exc}"}}

    obs = packet.get("observation", {})
    summary = (
        f"Proof packet {packet.get('id')} — verdict: {packet.get('verdict')}\n"
        f"URL: {obs.get('final_url', url)} | HTTP {obs.get('http_status')} | "
        f"title: {obs.get('page_title')!r}\n"
        f"body_sha256: {obs.get('body_sha256')}\n"
        f"signature ({packet.get('signing', {}).get('algorithm')}): "
        f"{str(packet.get('signature'))[:32]}...\n"
        f"Verify independently against public key "
        f"{packet.get('signing', {}).get('public_key_hex')}."
    )
    return {
        "result": {
            "content": [
                {"type": "text", "text": summary},
                {
                    "type": "text",
                    "text": "Full proof packet:\n" + json.dumps(packet, indent=2),
                },
            ],
            "structuredContent": packet,
            "isError": packet.get("verdict") == "ERROR",
        }
    }


def handle_message(msg: dict):
    method = msg.get("method")
    msg_id = msg.get("id")

    def respond(result=None, error=None):
        out = {"jsonrpc": "2.0", "id": msg_id}
        if error is not None:
            out["error"] = error
        else:
            out["result"] = result
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()

    if method == "initialize":
        respond(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        )
    elif method == "notifications/initialized":
        return  # notification: no response
    elif method == "tools/list":
        respond({"tools": [tool_definition()]})
    elif method == "tools/call":
        params = msg.get("params", {})
        out = handle_call(params.get("name"), params.get("arguments"))
        if "error" in out:
            respond(error=out["error"])
        else:
            respond(out["result"])
    elif method == "ping":
        respond({})
    elif msg_id is not None:
        respond(error={"code": -32601, "message": f"method not found: {method}"})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle_message(json.loads(line))
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    main()
