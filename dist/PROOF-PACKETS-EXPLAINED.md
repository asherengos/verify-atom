# Proof packets, explained

## What a proof packet is

You ask the service to check one thing: *"what does this URL show, right now?"*
It observes the page — for real, over the public internet — and hands you a
**proof packet**: a JSON document containing

- the final URL (after redirects) and HTTP status
- the page title and content type
- a SHA-256 hash of the response body
- the DNS resolution it saw (host → IP addresses)
- the TLS certificate details (subject, issuer, expiry)
- a timestamp of when the observation happened
- an **Ed25519 digital signature** over all of the above

Think of it as a notarized screenshot made of data instead of pixels.

## What it proves

That **at the recorded time, from the service's vantage point on the internet,
this URL returned this status, this title, and a body with this hash** — and
that the packet itself has not been altered since, because the signature would
break.

Anyone can verify the signature independently: fetch the public key from
`/key`, hash the packet's fields the canonical way, check the signature. No
account, no trust in us required. The math either checks out or it doesn't.

## What it does NOT prove

- That the page's *claims* are true (it proves the page *said* them, not that they're correct)
- That every visitor saw the same thing (pages personalize, A/B test, geotarget)
- That the content hasn't changed since (it proves a moment, not forever — re-verify for a new moment)
- Who wrote the page or whether the site itself is trustworthy

A proof packet is evidence of an observation, not a certificate of truth.

## Why agents want them

An AI agent that browses the web can currently only *claim* "source X says Y."
With a proof packet attached, the claim becomes checkable: the signature, the
body hash, and the timestamp let anyone — human or machine — re-verify what
was observed without re-running the browse. It's an audit trail for agent
research, and a defense against hallucinations dressed up as citations.

## The board

Every verification is appended to a public, permanent, append-only ledger —
the board (`/board/feed`). Once inscribed, a packet's existence is public
record. There is no edit button and no delete button.

## Try it

```bash
curl -s -X POST https://asheraistudios.duckdns.org/verify \
  -H 'Content-Type: application/json' \
  -d '{"type":"http_observation","url":"https://example.com"}'
```

Free while we're learning what people use it for. Machine-readable API doc for
agents: `https://asheraistudios.duckdns.org/llms.txt`.
