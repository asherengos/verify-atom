# Reddit post draft (Founder's voice — starting point, not a script)

## Suggested title
I built a free API that gives you cryptographically signed proof a webpage said something

## Body
POST a URL, get back a proof packet: HTTP status, page title, body SHA-256,
DNS, TLS cert — timestamped and Ed25519-signed so anyone can verify it
independently, no account needed.

The use case I'm building toward: your AI agent claims "source X says Y" —
now it can attach proof instead of asking for trust. Also useful anywhere you
need "this page said this at this time" (it changed, it got deleted, someone
disputes it).

Free while I figure out what people actually use it for. There's a
machine-readable API doc at /llms.txt if you want to point an agent at it, and
an MCP server wrapper so MCP-compatible agents can call it as a tool.

Live: https://asheraistudios.duckdns.org
Try: `curl -s -X POST https://asheraistudios.duckdns.org/verify -H 'Content-Type: application/json' -d '{"type":"http_observation","url":"https://example.com"}'`

Honest status: one endpoint, no payments, no auth, rate-limited. Would love
brutal feedback on what's missing.

## Target subs (check each sub's current self-promo rules before posting)
- r/SideProject — use their feedback/self-promo format
- r/alphaandbetausers — beta-testers welcome; follow their template
- r/selfhosted — the code will be on GitHub; this crowd self-hosts
- r/Python — Flask + vendored Ed25519, zero-dep crypto angle
