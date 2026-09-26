"""Verification service ("the atom") -- production backend, v1.

Real verification logic: POST /verify performs a genuine HTTP observation
of a URL (reachability, status, title, body hash, TLS summary, DNS) and
returns a signed proof packet with transparent estimated cost accounting.

Payments are HARD-DISABLED in v1: the service refuses to start if
``payments.enabled`` is true without a configured provider, and there is
no provider integration to configure. See config.yaml.

Security posture (v1):
* SSRF guard: only http/https, every resolved address must be globally
  routable (no private/loopback/link-local/multicast/reserved), the
  checked address is the connected address (DNS resolved once), redirects
  are never followed, and only ports 80/443 are allowed in production.
* 10s network timeout, 2MB body cap, fail closed with ERROR verdict.
* The private signing key is never logged and never leaves signing.py.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import secrets
import socket
import ssl
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, request

import costs
import ledger as ledger_module
import mini_yaml
import rate_limit
import signing
from costs import Usage

SERVICE_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = SERVICE_ROOT / "config.yaml"

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_RECORD_ID_RE = re.compile(r"^VRF-\d{8}-[0-9a-f]{8}$")
_USER_AGENT = "verify-service"

LLMS_TXT = """\
# Verification Service ("the atom") -- API for humans and agents

What this is: POST one question ("check this URL for me") and get back a
signed, timestamped proof packet with evidence attached. Every verification
is appended to a public, permanent ledger (the board).

Base URL: https://YOUR-DOMAIN-HERE

## POST /verify -- perform a verification

Request (JSON): {"type": "http_observation", "url": "https://example.com"}
Only "http_observation" is supported in v1. SSRF-guarded: public http/https
URLs only, ports 80/443, redirects are never followed, 10s timeout, 2MB cap.

Response: a signed proof packet with these fields:
- id ("VRF-YYYYMMDD-xxxxxxxx"), type, verdict
  (CONFIRMED = fetched with HTTP 2xx; UNCONFIRMED = fetched, other status;
   ERROR = refused or failed, see observation.reason)
- target.url, observation {reachable, http_status, page_title, body_sha256,
  tls {subject, issuer, not_after}, dns {host, addresses}}, evidence [...]
- timestamp_utc, usage {wall_time_s, bytes_in, http_requests}
- cost_usd with cost_basis "estimate" (an operator-configured estimate,
  NOT a metered cloud bill), price_quote_usd (a QUOTE, not a charge),
  margin_usd, below_cost
- signature: Ed25519 hex signature over the canonical JSON of every field
  except "signature" and "signing";
  signing: {algorithm "Ed25519", public_key_hex, signed_fields}

Errors: 400 invalid_json | unknown_type | missing_url | url_too_long;
429 rate_limited when over the per-IP limit (see Retry-After header).

Example:
  curl -s -X POST https://YOUR-DOMAIN-HERE/verify \\
    -H 'Content-Type: application/json' \\
    -d '{"type":"http_observation","url":"https://example.com"}'

## Verify a signature yourself (no trust required)

1. GET /key -> the service's Ed25519 public_key_hex.
2. Take the packet, remove the "signature" and "signing" fields, serialize
   the rest as canonical JSON (keys sorted, compact separators, UTF-8).
3. Ed25519-verify the 64-byte signature against the public key with any
   Ed25519 implementation. A tampered packet fails verification.

## GET /verify/<id> -- retrieve one stored proof packet (404 if unknown)

## GET /board/feed -- the public board: append-only feed, oldest first
Entries: {id, timestamp_utc, type, verdict, url}

## GET /health -- {"status", "version", "payments_enabled"}
## GET /key -- the service's Ed25519 PUBLIC key (the private key never
   leaves the server and is never served)

## Honesty notes (read before building on this)
- price_quote_usd is a quote, not a charge. PAYMENTS ARE DISABLED:
  /health reports payments_enabled:false and the service cannot charge
  anyone. Nothing here is for sale yet.
- cost_usd is an operator-configured estimate, not a metered bill.
- Public use is free and rate-limited per IP; abuse is blocked.
"""



# --- configuration ------------------------------------------------------------

def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_config(config_path: Path | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    try:
        cfg = mini_yaml.load(path)
    except mini_yaml.MiniYAMLError as exc:
        raise RuntimeError(f"cannot parse config {path}: {exc}") from exc
    if not isinstance(cfg, dict):
        raise RuntimeError(f"config {path} must be a mapping")
    return cfg


def _payments_guard(cfg: dict) -> None:
    """Fail closed: payments on without a provider refuses startup."""
    payments = cfg.get("payments", {}) or {}
    if payments.get("enabled"):
        provider = payments.get("provider") or {}
        if not provider.get("credentials_configured"):
            raise RuntimeError(
                "Refusing to start: payments.enabled is true but no payment "
                "provider is configured. Add a provider section with "
                "credentials and implement the charge flow, or set "
                "payments.enabled: false. (No provider integration ships "
                "in v1 by design.)"
            )


def create_app(config_path: Path | None = None) -> Flask:
    cfg = load_config(config_path)
    _payments_guard(cfg)

    service = cfg.get("service", {}) or {}
    verify_cfg = cfg.get("verify", {}) or {}
    data_dir = _resolve(SERVICE_ROOT, service.get("data_dir", "data"))
    cost_model_path = _resolve(SERVICE_ROOT, cfg.get("cost_model", "cost_model.yaml"))
    rates = costs.load_rates(cost_model_path)

    keystore = signing.KeyStore(data_dir / "keys")
    ledger = ledger_module.Ledger(data_dir / "ledger.jsonl")

    # Abuse guard: per-IP sliding-window rate limit on POST /verify.
    # 0 / negative / missing-but-None disables it; default 30 req/min/IP.
    rate_per_min = verify_cfg.get("rate_limit_per_minute", 30)
    limiter = None
    if rate_per_min is not None and int(rate_per_min) > 0:
        limiter = rate_limit.RateLimiter(int(rate_per_min), window_s=60.0)

    app = Flask(__name__)
    app.config["VRF_CFG"] = cfg
    app.config["VRF_VERIFY"] = verify_cfg
    app.config["VRF_RATES"] = rates
    app.config["VRF_KEYSTORE"] = keystore
    app.config["VRF_LEDGER"] = ledger
    app.config["VRF_LIMITER"] = limiter
    app.config["VRF_VERSION"] = str(service.get("version", "0.1.0"))

    # --- helpers --------------------------------------------------------------

    def utc_now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def new_id() -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"VRF-{stamp}-{secrets.token_hex(4)}"

    def finish_packet(packet: dict, usage: Usage) -> dict:
        """Attach cost accounting, sign, ledger, and return the packet."""
        cost = costs.compute_cost(usage, app.config["VRF_RATES"])
        price = float(app.config["VRF_VERIFY"].get("base_price_usd", 0.0))
        packet["usage"] = {
            "wall_time_s": round(usage.wall_time_s, 3),
            "bytes_in": usage.bytes_in,
            "http_requests": usage.http_requests,
        }
        packet["cost_usd"] = cost
        packet["cost_basis"] = "estimate"  # operator-configured, NOT metered
        packet["price_quote_usd"] = price
        packet["margin_usd"] = round(price - cost, 9)
        packet["below_cost"] = cost > price
        packet["signature"] = app.config["VRF_KEYSTORE"].sign_record(packet)
        packet["signing"] = {
            "algorithm": "Ed25519",
            "public_key_hex": app.config["VRF_KEYSTORE"].public_key_hex,
            "signed_fields": "all fields except 'signature' and 'signing'",
        }
        app.config["VRF_LEDGER"].append(packet)
        return packet

    def base_packet(record_type: str, target_url: str | None) -> dict:
        return {
            "id": new_id(),
            "type": record_type,
            "verdict": "ERROR",
            "target": {"url": target_url},
            "observation": {},
            "evidence": [],
            "timestamp_utc": utc_now(),
        }

    def client_ip() -> str:
        """Best-effort client IP for rate limiting.

        X-Forwarded-For is trusted ONLY when the immediate peer is this
        host itself (127.0.0.1 / ::1) -- i.e. our own reverse proxy
        (see deploy/Caddyfile). Direct clients cannot spoof it.
        """
        remote = request.remote_addr or "unknown"
        if remote in ("127.0.0.1", "::1"):
            first = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if first:
                return first
        return remote

    def rate_limit_check():
        """Deny over-limit POST /verify callers with 429 + Retry-After."""
        limiter = app.config["VRF_LIMITER"]
        if limiter is None:
            return None
        allowed, retry_after = limiter.check(client_ip(), time.monotonic())
        if allowed:
            return None
        wait = max(1, int(retry_after + 0.999))  # ceil, minimum 1s
        resp = jsonify({
            "error": "rate_limited",
            "detail": (
                f"more than {limiter.max_requests} verifications per "
                f"{int(limiter.window_s)}s from this IP"
            ),
            "retry_after_s": wait,
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(wait)
        return resp

    # --- SSRF-guarded observation ---------------------------------------------

    def resolve_checked(host: str, allow_private: bool):
        """Resolve once; refuse unless EVERY address is globally routable."""
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            return None, f"dns_resolution_failed: {exc}"
        addresses: list[str] = []
        for _, _, _, _, sockaddr in infos:
            try:
                ip = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                return None, f"ssrf_refused: unparseable address for {host}"
            if not allow_private and not ip.is_global:
                return None, (
                    f"ssrf_refused: {host} resolves to non-public address {ip}"
                )
            addresses.append(str(ip))
        if not addresses:
            return None, "dns_resolution_failed: no addresses returned"
        return addresses, None

    def read_chunked(reader, max_bytes: int):
        body = bytearray()
        while True:
            line = reader.readline(256).strip().split(b";")[0]
            try:
                size = int(line, 16)
            except ValueError:
                raise ValueError(f"bad chunk size {line!r}")
            if size == 0:
                reader.readline(256)
                while True:  # trailers
                    trailer = reader.readline(8192)
                    if trailer in (b"\r\n", b"\n", b""):
                        break
                break
            remaining = size
            while remaining > 0:
                chunk = reader.read(min(remaining, 65536))
                if not chunk:
                    raise ValueError("truncated chunked body")
                if len(body) + len(chunk) > max_bytes:
                    return bytes(body), True
                body += chunk
                remaining -= len(chunk)
            reader.readline(256)
        return bytes(body), False

    def read_bounded(reader, length: int | None, max_bytes: int):
        body = bytearray()
        remaining = length
        while remaining is None or remaining > 0:
            want = 65536 if remaining is None else min(remaining, 65536)
            chunk = reader.read(want)
            if not chunk:
                break
            if len(body) + len(chunk) > max_bytes:
                return bytes(body), True
            body += chunk
            if remaining is not None:
                remaining -= len(chunk)
        return bytes(body), False

    def summarize_cert(cert: dict) -> dict:
        def name(part):
            return ",".join(f"{k}={v}" for seq in part for k, v in seq)

        return {
            "subject": name(cert.get("subject", [])),
            "issuer": name(cert.get("issuer", [])),
            "not_after": cert.get("notAfter"),
        }

    def perform_observation(url: str):
        """Real HTTP observation. Returns (observation, evidence, usage, err).

        ``err`` is None on a completed fetch (verdict derived from status);
        otherwise the observation failed and ``err`` explains why.
        """
        started = time.monotonic()
        verify_cfg = app.config["VRF_VERIFY"]
        timeout = float(verify_cfg.get("timeout_s", 10))
        max_body = int(verify_cfg.get("max_body_bytes", 2 * 1024 * 1024))
        allow_private = bool(verify_cfg.get("allow_private", False))

        def usage_of(bytes_in: int, requests: int) -> Usage:
            return Usage(
                wall_time_s=time.monotonic() - started,
                bytes_in=bytes_in,
                http_requests=requests,
            )

        def refused(reason: str, requests: int = 0):
            """Fail-closed observation: nothing was fetched, nothing is claimed."""
            return {"reachable": False}, [], usage_of(0, requests), reason

        try:
            parsed = urllib.parse.urlsplit(url)
        except ValueError as exc:
            return refused(f"unparseable_url: {exc}")
        if parsed.scheme not in ("http", "https"):
            return refused("ssrf_refused: only http/https allowed")
        host = parsed.hostname
        if not host or parsed.username or parsed.password:
            return refused("ssrf_refused: bad host or userinfo in URL")
        default_port = 443 if parsed.scheme == "https" else 80
        port = parsed.port or default_port
        if not allow_private and port not in (80, 443):
            return refused("ssrf_refused: only ports 80/443 in production")

        addresses, err = resolve_checked(host, allow_private)
        if err:
            return refused(err)

        raw_sock = None
        try:
            raw_sock = socket.create_connection((addresses[0], port), timeout=timeout)
            raw_sock.settimeout(timeout)
            tls_summary = None
            sock = raw_sock
            if parsed.scheme == "https":
                context = ssl.create_default_context()
                sock = context.wrap_socket(raw_sock, server_hostname=host)
                tls_summary = summarize_cert(sock.getpeercert() or {})

            target_path = parsed.path or "/"
            if parsed.query:
                target_path += "?" + parsed.query
            request_line = (
                f"GET {target_path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"User-Agent: {_USER_AGENT}/{app.config['VRF_VERSION']}\r\n"
                "Connection: close\r\nAccept: */*\r\n\r\n"
            ).encode("utf-8")
            sock.sendall(request_line)
            bytes_out = len(request_line)

            reader = sock.makefile("rb")
            status_line = reader.readline(8192)
            header_block = bytearray(status_line)
            parts = status_line.decode("iso-8859-1").strip().split(" ", 2)
            if len(parts) < 2 or not parts[1].isdigit():
                raise ValueError(f"bad status line {status_line!r}")
            status = int(parts[1])
            headers: dict[bytes, bytes] = {}
            while True:
                line = reader.readline(8192)
                header_block += line
                if line in (b"\r\n", b"\n", b""):
                    break
                name, _, value = line.partition(b":")
                headers[name.strip().lower()] = value.strip()

            if headers.get(b"transfer-encoding") == b"chunked":
                body, truncated = read_chunked(reader, max_body)
            else:
                raw_length = headers.get(b"content-length", b"").strip()
                length = int(raw_length) if raw_length.isdigit() else None
                body, truncated = read_bounded(reader, length, max_body)

            bytes_in = bytes_out + len(header_block) + len(body)
            usage = usage_of(bytes_in, 1)

            if truncated:
                return (
                    {"reachable": True, "truncated_at_cap": True,
                     "cap_bytes": max_body},
                    [],
                    usage,
                    "body_cap_exceeded: response larger than max_body_bytes",
                )

            text = body.decode("utf-8", errors="replace")
            title_match = _TITLE_RE.search(text)
            title = title_match.group(1).strip()[:300] if title_match else None
            observation = {
                "reachable": True,
                "http_status": status,
                "final_url": url,  # redirects are never followed in v1
                "redirect_followed": False,
                "page_title": title,
                "content_type": headers.get(b"content-type", b"").decode(
                    "iso-8859-1", errors="replace")[:200] or None,
                "body_bytes": len(body),
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "tls": tls_summary,
                "dns": {"host": host, "addresses": addresses},
            }
            evidence = [
                {"kind": "http_status", "value": status},
                {"kind": "body_sha256", "value": observation["body_sha256"]},
                {"kind": "dns_resolution",
                 "value": f"{host} -> {', '.join(addresses)}"},
            ]
            if tls_summary:
                evidence.append({
                    "kind": "tls_certificate",
                    "value": (
                        f"subject={tls_summary['subject']}; "
                        f"issuer={tls_summary['issuer']}; "
                        f"not_after={tls_summary['not_after']}"
                    ),
                })
            if status in (301, 302, 303, 307, 308):
                observation["redirect_location"] = headers.get(
                    b"location", b"").decode("iso-8859-1", errors="replace")[:500]
            return observation, evidence, usage, None
        except (socket.timeout, TimeoutError):
            return refused("network_timeout", requests=1)
        except (socket.error, ssl.SSLError, ValueError) as exc:
            return refused(f"observation_failed: {exc}", requests=1)
        finally:
            try:
                if raw_sock is not None:
                    raw_sock.close()
            except OSError:
                pass

    # --- routes ---------------------------------------------------------------

    @app.get("/health")
    def health():
        payments = app.config["VRF_CFG"].get("payments", {}) or {}
        return jsonify({
            "status": "ok",
            "version": app.config["VRF_VERSION"],
            "payments_enabled": bool(payments.get("enabled", False)),
        })

    @app.get("/key")
    def key():
        # PUBLIC key only. The private key never leaves signing.KeyStore.
        return jsonify({
            "algorithm": "Ed25519",
            "public_key_hex": app.config["VRF_KEYSTORE"].public_key_hex,
        })

    @app.get("/llms.txt")
    def llms_txt():
        # Machine-readable API doc for humans and agents.
        return Response(LLMS_TXT, mimetype="text/plain")

    @app.get("/board/feed")
    def board_feed():
        return jsonify(app.config["VRF_LEDGER"].feed())

    @app.get("/verify/<record_id>")
    def get_verification(record_id: str):
        if not _RECORD_ID_RE.match(record_id):
            return jsonify({"error": "not_found"}), 404
        packet = app.config["VRF_LEDGER"].get(record_id)
        if packet is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify(packet)

    @app.post("/verify")
    def post_verify():
        denied = rate_limit_check()
        if denied is not None:
            return denied
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "invalid_json",
                            "detail": "body must be a JSON object"}), 400
        record_type = body.get("type")
        if record_type != "http_observation":
            return jsonify({
                "error": "unknown_type",
                "detail": "v1 supports only 'http_observation'",
                "received": record_type,
            }), 400
        url = body.get("url")
        if not isinstance(url, str) or not url:
            return jsonify({"error": "missing_url",
                            "detail": "'url' is required"}), 400
        max_url = int(app.config["VRF_VERIFY"].get("max_url_length", 2048))
        if len(url) > max_url:
            return jsonify({"error": "url_too_long"}), 400

        packet = base_packet(record_type, url)
        observation, evidence, usage, err = perform_observation(url)
        packet["observation"] = observation
        packet["evidence"] = evidence
        if err is not None:
            packet["verdict"] = "ERROR"
            packet["observation"] = {**observation, "reason": err}
        else:
            status = observation.get("http_status", 0)
            packet["verdict"] = "CONFIRMED" if 200 <= status < 300 else "UNCONFIRMED"
        return jsonify(finish_packet(packet, usage))

    return app


if __name__ == "__main__":
    application = create_app()
    port = int(application.config["VRF_CFG"]["service"]["port"])
    from waitress import serve

    print(f"verify-service v{application.config['VRF_VERSION']} on 127.0.0.1:{port} "
          f"(payments_enabled=false)")
    serve(application, listen=f"127.0.0.1:{port}")
