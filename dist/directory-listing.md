# API directory listing draft (RapidAPI / Postman Public API Network)

## Name
Verification Endpoint ("the atom")

## Tagline
Cryptographically signed proof of what a webpage showed. Check it, prove it.

## Description
POST a URL, receive a signed proof packet: HTTP status, page title, body
SHA-256, DNS resolution, TLS certificate details — timestamped and
Ed25519-signed so anyone can verify it independently, no account or API key
required.

Built for AI agents and developers who need verifiable web observations:
attach proof to "source X says Y" instead of asking for trust. Every
verification is inscribed on a public append-only board.

Machine-readable API doc: https://asheraistudios.duckdns.org/llms.txt
MCP server available for agent tool use.

## Tags
verification, web-scraping, fact-checking, ai-agents, cryptography, ed25519,
audit-trail, developer-tools

## Endpoints
- POST /verify — body: {"type":"http_observation","url":"https://..."}
  → 200 + signed proof packet (429 when rate-limited: 30/min/IP)
- GET /verify/{id} — retrieve a past packet
- GET /board/feed — the public append-only ledger
- GET /key — the Ed25519 public key (verify signatures offline)
- GET /health — service status (payments_enabled: false in v1)
- GET /llms.txt — machine-readable API documentation

## Honesty note (keep on the listing)
Free during the learning period. No auth, no payments in v1. One endpoint,
one job: observe a URL and prove it.
