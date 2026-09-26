# $0 Go-Live Map — Verification Service v1

Principle: **live and learning, not live and earning (yet).**
Everything that costs money or moves money stays OFF.
The goal of go-live v1: prove the machine runs in public, measure true
per-verification costs on real infrastructure, accumulate REAL board
entries, and be ready the moment a buyer appears.

## What deploys where (all $0)

- **Compute: Oracle Cloud Always Free ARM VM** — 2 cores / 12 GB RAM /
  200 GB storage / 10 TB egress, free forever, never sleeps. Card required
  at signup for identity verification; free-tier usage is never charged.
  Honest caveats: provisioning frequently hits "out of capacity" (retry
  over days); idle instances can be reclaimed by Oracle. Backup option:
  GCP e2-micro (always-free tier).
- **Rejected for $0 always-on:** Fly.io (no free tier for new users —
  trial/card only), Railway ($1/mo minimum), Render free (sleeps after
  15 min), PythonAnywhere free (100 CPU-sec/day, not 24/7), Cloudflare
  Workers free (proprietary runtime — our Flask app won't run there),
  Vercel free (non-commercial only). Terms checked 2026-09-26; re-check
  before committing, free tiers move.
- **TLS:** Caddy as reverse proxy (automatic HTTPS, free) or
  Let's Encrypt certs.
- **Domain:** start on the provider's free subdomain ($0). Buy a real
  domain (~$12/yr) only after the first stranger shows interest.
  $0 until signal.
- **The service:** ~/workspace/verify-service as built — waitress,
  `payments.enabled=false`, a FRESH production Ed25519 keypair generated
  on first boot (never reuse the dev keypair in `data/`).
- **Monitoring:** UptimeRobot free tier against `/health`, plus VM logs.

## What stays switched OFF

- Payments: no Stripe keys on the server; the fail-closed startup guard
  stays. Price quotes display as QUOTES, never charges.
- Verified-revenue counter: $0.00 until a real payment clears.
- No paid add-ons, no auto-scaling, no metering changes.

## What it costs

- Money: $0. The real budget is human time on the demand side.
- Marginal cost per verification on the free VM: a fraction of a cent
  (measured by the service's own cost accounting).

## Before go-live: two small builds (both $0, both mine)

1. **Rate limiting** on POST /verify (abuse guard — README flags it
   missing; a free public endpoint without it is a donation to bots).
2. **Machine-readable docs** (llms.txt-style API doc) so agents and
   developers can discover and use the endpoint.

## The demand side (human-tool work, $0)

- v1 is FREE to use (payments off). The goal is USAGE + feedback +
  real board entries + true cost calibration — not revenue.
- First-buyer plays: post the endpoint in developer communities,
  recruit 5 pilot developers for free verifications in exchange for
  feedback, list in API directories, publish the "proof packet"
  explainer.
- The rule stands: no real budget until strangers pay.

## Go-live sequence

1. Assistant builds the deploy bundle (systemd unit, Caddyfile,
   runbook, rate limiting, llms.txt).
2. Human signs up for Oracle Cloud (their identity + card for
   verification only).
3. Deploy via runbook (human runs it, or grants SSH — their call).
4. Free subdomain + TLS; public `/health` check; one public
   verification end-to-end.
5. Demand work begins.

## Kill criteria (the loop's verdict, not feelings)

60–90 days after go-live with zero usage → kill or pivot.
The ledger decides.

## When payments get wired (later, explicit approval only)

Stripe metered billing via the current Meters API: create a Meter
(event `verification`), attach a metered Price, report one meter event
per verification, Stripe aggregates and invoices monthly. Sub-cent
per-unit prices work because Stripe bills the aggregate (minimum
$0.50/invoice). Honest fee math: 2.9% + $0.30 per invoice means a
$1/mo customer costs ~$0.33 in fees — viable customers generate a few
dollars/mo minimum. Alternative: prepaid credits.
(API notes: the old `createUsageRecord` API was deprecated in 2025;
use Billing Meters. Stripe Billing itself costs 0.5–0.8% of recurring
on top of processing.)
