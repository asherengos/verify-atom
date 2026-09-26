# Market Roadmap

**Status:** Active  
**Owner:** Asher  
**Last Updated:** 2026-09-26  
**Purpose:** Take the live verification endpoint from "it works" to "strangers use it" — through machine legibility (bots can find, understand, and call it) and human distribution (developers hear about it) — while keeping every claim honest and every dollar accounted for.

---

## Summary

The ATOM is live: `https://asheraistudios.duckdns.org` serves real Ed25519-signed proof packets over public HTTPS, and the first packet's signature has been independently verified. The engine runs. What does not exist yet is a single stranger who wants one.

This roadmap covers the MARKET phase: making the service legible to machines and visible to humans, recruiting the first pilot users, and then honestly evaluating whether anyone wants it.

It shows:

- Where the service currently stands
- What "discoverable" concretely means for bots and for humans
- What must be built, posted, and listed — and by whom
- How each phase is gated on observed evidence, not optimism
- When to keep going and when to kill or pivot

Target dates are planning tools, not promises. They may be adjusted whenever work, school, family responsibilities, health, finances, technical difficulty, or new information make a change necessary.

Progress is measured honestly, never used to create unnecessary pressure, and never fabricated.

This roadmap should always answer:

> Who can find the service today, who used it this week, and what must become true before we advance?

---

## Current Position

**Current Level:** ATOM live — public HTTPS, signed proof packets, independently verified  
**Current Phase:** MARKET-1 Machine Legibility  
**Current Milestone:** M1.1 complete (`/llms.txt` live); M1.2 in progress (MCP server)  
**Current Focus:** Make the service legible to any competent bot or crawler before asking any human to look at it  
**Revenue:** $0.00 (verified)  
**Stranger verifications to date:** 0  
**Evaluation clock:** Started 2026-09-26 at public launch. Zero stranger usage for 60–90 days means kill or pivot — Founder's call.

---

## Guiding Principles

### Honesty Before Growth

No fake users, no fake revenue, no simulated metrics presented as real. Every sample, estimate, and prototype label stays exactly where it is. The money counter moves only on verified revenue. A roadmap full of red gates is better than a dashboard full of invented green.

### Legibility Before Persuasion

We do not manipulate recommenders — human or machine — into suggesting the service. We make the service findable, accurately described, and trivially callable, so that any bot or person genuinely looking for "prove a webpage said X" can discover it on the merits. Discovery, not persuasion.

### Evidence Before Advancement

No phase advances on optimism. Each gate lists the exact evidence required: a URL that returns 200, a file that exists, a packet a stranger created. "Basis" notes record what each completion claim rests on.

### Founder Signs In

Accounts, posts, listings, and anything published under a human identity are Founder actions. The assistant prepares everything so each one is a single paste or click — and never impersonates the Founder.

### One Working Channel Before Ten

A single channel that produces one real stranger verification beats ten listings nobody visits. Prove one channel, then expand.

---

# Phase MARKET-1: Machine Legibility

## Purpose

Any competent bot or crawler that goes looking for web-verification tooling can find the service, understand what it does, and call it — without human help.

**Target Dates:** 2026-09-26 through 2026-10-03  
**Current Status:** In progress  
**Detailed artifacts:** `~/workspace/verify-service/mcp/`, `~/workspace/verify-service/static/`

### Required Milestones

#### Milestone 1.1: The Service Describes Itself to Machines

The public site serves a machine-readable API description at `/llms.txt`.

**Status:** Complete  
**Basis (2026-09-26):** live since deploy; verified reachable over public HTTPS.

Completed work:

- `/llms.txt` route serving the machine-readable API doc
- Endpoint contract, proof-packet schema, and trust model included

#### Milestone 1.2: The Service Is Callable as an Agent Tool

A Model Context Protocol (MCP) server wraps `/verify` so any MCP-compatible agent can call it as a tool. Zero new dependencies; stdio transport; calls the live public endpoint.

**Status:** Complete

Completed 2026-09-26. Full stdio handshake verified: `initialize` →
`tools/list` (exposes `verify_url`) → `tools/call` performed a REAL
verification against the public endpoint.

Evidence:
- Packet `VRF-20260926-b661a532`, verdict CONFIRMED, real example.com observation
- Signing key in packet matches the production public key
- Signature independently verified with local ed25519 code: valid
- One robustness fix during testing: retry-once on transient transport
  failures (egress proxy intermittently closes idle connections —
  `RemoteDisconnected` on first attempt, clean 200 on retry)

Required artifacts:

- `mcp/mcp_server.py` — the server (zero dependencies, stdio JSON-RPC 2.0)
- `mcp/README.md` — setup and registration instructions

#### Milestone 1.3: The Code Is Where Crawlers Look

The service code lives in a public GitHub repository with a README that describes, in plain language, what a proof packet is and how to verify one.

**Status:** Blocked on Founder (requires Founder's GitHub identity)

Assistant prepares:

- Repository file layout and `.gitignore` (no secrets, no data dir, no keys)
- `README.md` written for both humans and crawlers (what it is, live URL, verify-yourself instructions, honesty labels)

Founder does (one session):

- Create the repository under their account
- Push the prepared tree

Evidence required: public repo URL returning 200, README rendering, no secret material in history.

#### Milestone 1.4: Crawler Hygiene

Search and AI crawlers can reach the descriptive pages without obstruction.

**Status:** Prepared in bundle; live deploy deferred

The bundle carries everything (`deploy/Caddyfile` handle blocks,
`deploy/static/robots.txt` + `sitemap.xml`, installer step). Live deployment
was deferred 2026-09-26 after paste instability in the terminal session made
multi-line edits unreliable at 1 AM. This blocks nothing: with no robots.txt
present, the default is allow-all, so no crawler is obstructed. The
machine-readable doc that matters (`/llms.txt`, correct domain) is live.

Required artifacts (prepared by assistant):

- `static/robots.txt` — allows `GPTBot`, `ClaudeBot`, `CCBot`, and general crawlers on descriptive paths
- `static/sitemap.xml` — lists `/`, `/llms.txt`, `/key`, `/board/feed`, `/health`
- `static/CADDY-SNIPPET.txt` — the three-line static-file addition plus reload command

Evidence required: `curl` 200s on `/robots.txt` and `/sitemap.xml` over public HTTPS.

### Gate G1: Legibility Gate

Advance to MARKET-2 only when:

| # | Criterion | Weight | Evidence |
|---|-----------|--------|----------|
| 1 | `/llms.txt` live | 20% | public 200 (observed 2026-09-26) |
| 2 | MCP server tested end-to-end | 30% | handshake log + verified packet |
| 3 | Public GitHub repo live | 25% | repo URL, clean history |
| 4 | robots.txt + sitemap.xml live | 25% | public 200s |

All four required. Partial credit is recorded but does not open the gate.

---

# Phase MARKET-2: Human Distribution

## Purpose

Developers who would genuinely benefit hear about the service, in the places they already look, in the Founder's own voice.

**Target Dates:** 2026-10-04 through 2026-10-18  
**Current Status:** Not started (drafts prepared in MARKET-1)

### Required Milestones

#### Milestone 2.1: The Explainer Exists

A plain-language document explains proof packets: what one is, what it proves, what it does NOT prove, and how to verify one without trusting us.

**Status:** Draft prepared by assistant

Required artifact:

- `dist/PROOF-PACKETS-EXPLAINED.md`

It must contain the "does NOT prove" section. Honesty is the product.

#### Milestone 2.2: Reddit

**Status:** Blocked on Founder (their account, their voice)

Prepared by assistant:

- `dist/reddit-post.md` — the post text
- Target subs with rules noted: r/SideProject (self-promo format), r/alphaandbetausers (beta rules), r/selfhosted, r/Python

Founder posts in their own words (the draft is a starting point, not a script).

Evidence: post URLs recorded.

#### Milestone 2.3: Show HN

**Status:** Blocked on Founder

Prepared by assistant: `dist/hn-post.md` (title + first comment).

Evidence: HN item URL recorded.

#### Milestone 2.4: API Directories

**Status:** Blocked on Founder (account creation needs identity)

Targets: RapidAPI, Postman Public API Network.

Prepared by assistant: `dist/directory-listing.md` — name, tagline, description, tags, endpoint docs.

Evidence: listing URLs recorded.

### Gate G2: Distribution Gate

| # | Criterion | Weight | Evidence |
|---|-----------|--------|----------|
| 1 | Explainer published (repo or site) | 20% | URL |
| 2 | ≥2 Reddit posts live | 30% | post URLs |
| 3 | Show HN live | 25% | HN item URL |
| 4 | ≥1 API directory listing live | 25% | listing URL |

---

# Phase MARKET-3: Pilot Users

## Purpose

Five developers who genuinely need verifiable web observations try the service and say what's missing. Their usage — not our hopes — teaches us what to build next.

**Target Dates:** 2026-10-18 through 2026-11-15  
**Current Status:** Not started

### Required Milestones

#### Milestone 3.1: Five Pilots Recruited

Five people, not affiliated with the project, each run at least one verification through the public endpoint.

Evidence per pilot: packet ID(s) in the public ledger (the ledger is the attendance sheet — it cannot be faked without a real request).

#### Milestone 3.2: Feedback Captured

For each pilot: what they tried, what worked, what was missing, whether they'd pay (and how much, in what form — credits, subscription, per-packet).

Recorded in: `dist/pilot-feedback.md` (no invented pilots; empty rows stay empty).

### Gate G3: Pilot Gate

Advance to evaluation with data when: 5 pilots complete OR 30 days elapse with documented outreach. The gate opens on evidence either way — silence is also data.

---

# Phase MARKET-4: The 60–90 Day Evaluation

## Purpose

Decide, on the record, whether the service earns its existence.

**Window:** 2026-09-26 through 2026-12-26 (90-day outer bound; 60-day checkpoint 2026-11-25)  
**Current Status:** Clock running

### The Rule

If, by the end of the window, **zero strangers** have used the service (a stranger = anyone other than the Founder and the assistant), the Founder chooses: **kill it or pivot it**. No extensions on hope. The decision and its reasons are recorded in this file.

Usage is counted from the append-only ledger: packet IDs whose requests did not originate with us.

### What Counts as Signal (any of these resets the conversation)

- One stranger verification
- One pilot who says they'd pay
- One inbound question from someone we didn't contact
- One integration attempt (MCP server configured against us by a third party)

### Standing Constraints (unchanged)

- $0 spending ceiling
- Payments stay off until strangers demonstrate willingness to pay AND the Founder explicitly lifts the ceiling
- Revenue counter moves only on verified real-world revenue: **$0.00**

---

## Approval Checkpoints

| Checkpoint | Decider | What |
|------------|---------|------|
| G1 Legibility Gate | Assistant (evidence) + Founder (repo creation) | All machine-legibility artifacts live |
| G2 Distribution Gate | Founder | Posts and listings published under Founder identity |
| G3 Pilot Gate | Founder | Pilots recruited, feedback recorded |
| Kill / Pivot | Founder | End of evaluation window, on the record |

The assistant builds everything buildable. The Founder is the hands for identity, money, public presence, and selling. Neither impersonates the other.

---

## Execution Log

| Date | Action | By | Evidence |
|------|--------|----|----------|
| 2026-09-26 | ATOM public launch | Both | health 200, cert valid |
| 2026-09-26 | First proof packet verified | Assistant | VRF-20260926-f31f2a73, signature valid, tamper rejected |
| 2026-09-26 | M1.1 `/llms.txt` confirmed live | Assistant | public 200 |
| 2026-09-26 | Market Roadmap written | Assistant | this file |
| 2026-09-26 | Found `YOUR-DOMAIN-HERE` placeholder live in `/llms.txt` | Assistant | public curl |
| 2026-09-26 | Fixed in source: install.sh now stamps domain into app.py llms.txt | Assistant | deploy/install.sh |
| 2026-09-26 | M1.2 MCP server built (`mcp/mcp_server.py`, zero-dep stdio) | Assistant | handshake + live-call test running |
| 2026-09-26 | M1.4 crawler files into bundle (Caddy handle blocks + static/) | Assistant | deploy/Caddyfile, deploy/static/ |
| 2026-09-26 | M2.1 explainer + M2.2/M2.3/M2.4 drafts written | Assistant | dist/ (5 files) |
| 2026-09-26 | Live VM patch prepared (llms.txt sed + crawler files + Caddy) | Assistant | awaiting Founder terminal session |
| 2026-09-26 | `/llms.txt` domain fix confirmed live on VM | Both | public curl: Base URL = asheraistudios.duckdns.org |
| 2026-09-26 | M1.2 MCP server test GREEN | Assistant | packet VRF-20260926-b661a532, signature valid |
| 2026-09-26 | M1.4 live deploy deferred (paste instability); bundle-ready | Assistant | no robots.txt = allow-all default, nothing blocked |
| 2026-09-26 | Gate G1 scored: 50% (M1.1+M1.2 complete; M1.3+M1.4 need Founder) | Assistant | this file |
