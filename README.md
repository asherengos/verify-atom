# Verification Service ("the atom") — v1 backend

The production backend for the verification atom: **"check this one thing
for me, and prove you did."** A client POSTs one question
(`http_observation` of a URL); the service performs a real observation and
returns a signed proof packet with transparent cost accounting. Every
verification is appended to a public, permanent ledger — the board.

**Honesty, up front:**

* `cost_usd` on every packet is an **operator-configured estimate**, not a
  metered cloud bill (`"cost_basis": "estimate"`). Recalibrate before pricing.
* **Payments are disabled.** There is no payment provider integration in v1,
  and the service refuses to start if `payments.enabled` is true without one.
* This service makes **no revenue claims**. Quoted prices are quotes; nothing
  is charged, because nothing can be charged yet.

## Architecture
## MCP server (`mcp/`)

This repo also ships a [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the verification atom as an MCP tool, so MCP-compatible agents can request signed proof packets directly.

- **Install:** `uvx verify-atom-mcp` (published on PyPI as `verify-atom-mcp`)
- **Listed in the official MCP registry** as `io.github.asherengos/verify-atom`
- **Transport:** stdio · **Tool:** `verify` — performs an HTTP observation of a URL and returns the Ed25519-signed proof packet
- Source: `mcp/mcp_server.py` (zero dependencies; `mcp/README.md` has the details)

| File | Role |
|---|---|
| `app.py` | Flask app: routes, SSRF-guarded HTTP observation, packet assembly |
| `signing.py` | Ed25519 key management + sign/verify (crypto core vendored from the Asher AI Studios Work Kernel, 2026-09-25; pure Python, RFC 8032, zero deps) |
| `costs.py` / `cost_model.yaml` | Per-verification usage measurement × operator-configured rates |
| `ledger.py` | Append-only JSONL ledger (`data/ledger.jsonl`): the board's source of truth and the honest loop's input |
| `mini_yaml.py` | Strict subset YAML reader (keeps deps to flask + waitress; not a general parser) |
| `config.yaml` | Service config: port, data dir, price, guardrails, payments switch |
| `tests/test_service.py` | Hermetic pytest suite (local stub server; no external network) |

A verification flows: `POST /verify` → SSRF guard → real socket-level HTTP
fetch (single DNS resolution; the checked address is the connected address;
redirects never followed) → observation + evidence → cost accounting →
Ed25519 signature over canonical JSON → append to ledger → proof packet.

## Quick start

```bash
cd ~/workspace/verify-service
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # flask + waitress only; free
.venv/bin/python app.py                     # serves on 127.0.0.1:5057 via waitress
```

First run generates an Ed25519 keypair under `data/keys/` (0600). `data/`
is gitignored: ledger, keys, and runtime state never enter the repo.

Development (Flask built-in server, do not use in production):

```bash
.venv/bin/python -m flask --app app:create_app run -p 5057
```

## API reference

### POST /verify — perform a verification

```bash
curl -s -X POST http://127.0.0.1:5057/verify \
  -H 'Content-Type: application/json' \
  -d '{"type":"http_observation","url":"https://example.com"}' | python3 -m json.tool
```

Response: a signed proof packet.

```json
{
  "id": "VRF-20260926-3f9a2c1d",
  "type": "http_observation",
  "verdict": "CONFIRMED",
  "target": {"url": "https://example.com"},
  "observation": {
    "reachable": true,
    "http_status": 200,
    "page_title": "Example Domain",
    "body_sha256": "…",
    "tls": {"subject": "…", "issuer": "…", "not_after": "…"},
    "dns": {"host": "example.com", "addresses": ["93.184.216.34"]}
  },
  "evidence": [{"kind": "http_status", "value": 200}, …],
  "timestamp_utc": "2026-09-26T02:30:00Z",
  "usage": {"wall_time_s": 0.41, "bytes_in": 1830, "http_requests": 1},
  "cost_usd": 0.0000109,
  "cost_basis": "estimate",
  "price_quote_usd": 0.005,
  "margin_usd": 0.0049891,
  "below_cost": false,
  "signature": "<64-byte ed25519 hex>",
  "signing": {"algorithm": "Ed25519", "public_key_hex": "…",
              "signed_fields": "all fields except 'signature' and 'signing'"}
}
```

Verdicts: `CONFIRMED` (fetched, HTTP 2xx), `UNCONFIRMED` (fetched, other
status — a real negative observation), `ERROR` (refused or failed; the
`observation.reason` explains why). Unknown `type` → `400 unknown_type`.

Spot-checking a packet (no trust required):

```bash
# fetch the service public key, then verify the signature offline:
curl -s http://127.0.0.1:5057/key
```

The signature covers the canonical JSON (sorted keys, compact separators)
of every packet field except `signature` and `signing`. Recompute it and
verify with any Ed25519 implementation.

### GET /verify/<id> — retrieve a stored proof packet (404 if unknown)

```bash
curl -s http://127.0.0.1:5057/verify/VRF-20260926-3f9a2c1d | python3 -m json.tool
```

### GET /board/feed — public append-only feed, oldest first

```bash
curl -s http://127.0.0.1:5057/board/feed | python3 -m json.tool
```

Each entry: `{id, timestamp_utc, type, verdict, url}`.

### GET /health

```bash
curl -s http://127.0.0.1:5057/health
# {"status":"ok","version":"0.1.0","payments_enabled":false}
```

### GET /key — the service's Ed25519 public key

```bash
curl -s http://127.0.0.1:5057/key
# {"algorithm":"Ed25519","public_key_hex":"…"}
```

The private key is never logged, never served, never leaves `signing.py`.

## Configuration (`config.yaml`)

| Key | Default | Meaning |
|---|---|---|
| `service.port` | 5057 | Listen port |
| `service.data_dir` | `data` | Runtime state (ledger, keys); gitignored |
| `verify.base_price_usd` | 0.005 | Quoted price per verification (a quote, not a charge) |
| `verify.timeout_s` | 10 | Network timeout per observation |
| `verify.max_body_bytes` | 2097152 | 2 MB body cap; overage → ERROR verdict |
| `verify.allow_private` | false | **Never true in production.** Lets the hermetic tests use a 127.0.0.1 stub |
| `cost_model` | `cost_model.yaml` | Path to operator-configured rates |
| `payments.enabled` | false | Master switch. `true` without a configured provider → **refuse to start** |

## Key management

* First run: `KeyStore` generates an Ed25519 keypair into
  `data/keys/{private.key,public.key}` (directory 0700, files 0600; refuses
  to overwrite an existing key).
* Back up `private.key` offline; losing it orphans the board's trust chain
  (old packets still verify against the published public key, but the
  service can no longer sign).
* Rotation (not automated in v1): generate a new keypair, publish the new
  public key at `/key` with a `key_id`, keep the old public key published
  for historical verification. See go-live checklist.

## Deployment notes

The `$0` go-live bundle lives in `deploy/`:

| File | Role |
|---|---|
| `deploy/verify-service.service` | Hardened systemd unit (unprivileged `verify` user, `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, restart on failure) |
| `deploy/Caddyfile` | Reverse proxy with automatic TLS; forwards the real client IP (`X-Forwarded-For`) — the app trusts that header **only** from 127.0.0.1/::1 |
| `deploy/DEPLOY.md` | Ordered runbook for a non-expert: Oracle Cloud Always Free ARM VM, hardening, first-boot keypair, systemd, Caddy, DNS, go-live checks |

Built-in abuse guard: `POST /verify` is rate-limited per client IP
(sliding 60s window, `verify.rate_limit_per_minute`, default 30/min).
Over the cap → `429` JSON with a `Retry-After` header. Set
`rate_limit_per_minute: 0` to disable (never disable on a public endpoint).

Run one worker per data directory (v1 has no cross-process locking on the
ledger). The service binds 127.0.0.1 only; public traffic arrives via the
reverse proxy.

Machine-readable docs for humans and agents: `GET /llms.txt`
(`text/plain`) — endpoint contract, proof-packet fields, how to verify a
signature offline, and the honesty notes.

### Known v1 limitations (stated plainly)

* HTTP/1.1 only; redirects are never followed (recorded as UNCONFIRMED).
* No HTTP/2, no JavaScript rendering: the observation is the raw HTTP
  response, which is exactly what is hashed and signed.
* DNS is resolved once per verification; a hostile DNS that flips answers
  between resolution and connect within milliseconds is out of scope for
  v1 (documented, not mitigated beyond the single-resolution design).
* Single worker; ledger scans are O(n).
* Pure-Python Ed25519: correct, but slower than a C implementation —
  fine at v1 volumes; adopt a vetted C library before scaling.

## Go-live checklist

- [x] **Deploy bundle** (`deploy/`, built 2026-09-26): hardened systemd
      unit, Caddyfile with automatic TLS, `DEPLOY.md` runbook (Oracle
      Cloud Always Free ARM VM, human steps marked), in-app per-IP rate
      limiting on `POST /verify` (30/min default, `429` + `Retry-After`),
      `/llms.txt` machine-readable API docs. All $0, stdlib-only, no
      payment code paths. Tests: 26/26 green.
- [ ] **Hosting**: provision the VM per `deploy/DEPLOY.md`; decide the
      data-dir backup story (ledger + key backup are in the runbook).
- [ ] **Payment provider integration**: NOT BUILT. Implement the charge
      flow, wire it to `payments.provider`, then flip `enabled: true`.
- [ ] **Fresh production keypair**: generated on first boot per the
      runbook (never copy `data/` from dev); publish the public key;
      back up the private key offline.
- [ ] **Real cost calibration**: replace `cost_model.yaml` estimates with
      metered values; run a calibration batch; confirm `margin_usd > 0`
      before quoting real prices.
- [ ] **Terms & abuse policy**: acceptable use, refund policy for failed
      (ERROR) verifications — written and published. (Rate limiting itself
      is now built in; the edge policy is the remaining piece.)
- [ ] **TLS + reverse proxy**: covered by `deploy/Caddyfile`; replace the
      placeholder domain, validate, reload.
- [ ] **Key rotation procedure** documented and rehearsed.
- [ ] **Monitoring**: UptimeRobot free monitor on `/health`; ledger
      growth, `below_cost` counts, error rates — the honest loop must page
      someone when the loop turns red.
