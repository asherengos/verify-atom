# Show HN draft (Founder posts)

## Title
Show HN: Signed proof packets for web observations (free API + MCP server)

## First comment
I built a tiny API around one question: "check this URL for me, and prove
you did."

POST a URL and you get back a proof packet — HTTP status, title, body
SHA-256, DNS, TLS cert, timestamp — signed with Ed25519 so anyone can verify
it offline without trusting me. Every verification also lands on a public
append-only board.

Why: agents that browse the web can only *claim* what sources say. A signed
packet turns "source X says Y" into something checkable. Same primitive works
for "this page said this before it was edited/deleted."

Stack: Flask, vendored zero-dependency Ed25519, Caddy, one Oracle free-tier
ARM VM. Machine-readable docs at /llms.txt, plus an MCP server wrapper so
agents can call it as a tool.

Status is honest: $0 revenue, no auth, no payments, rate-limited per IP. Free
while I learn what it's actually good for. Tear it apart — what's missing?

https://asheraistudios.duckdns.org
