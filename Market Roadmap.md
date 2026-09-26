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

**Status:** Complete — repo public at https://github.com/asherengos/verify-atom (2026-09-26)

Pushed by the Founder: commit `28ecc80` on `main`, 27 tracked files, clean
history. Publicly verified: visibility Public, README renders, all root
files present. Local-only folders (`data/`, `.pytest_cache`,
`__pycache__`) were removed from the working copy before push; the pushed
tree matches the clean tracked set exactly.

Git repo initialized in `~/workspace/verify-service`: single commit on `main`
(27 files), `.gitignore` verified clean — no keys, no `data/`, no venv, no
caches. Zipped (with `.git`) and uploaded to Muse storage; Founder downloads,
creates the empty public repo on github.com, then `git remote add origin`
+ `git push -u origin main`. Suggested name: `verify-atom`.

Assistant prepares:

- Repository file layout and `.gitignore` (no secrets, no data dir, no keys)
- `README.md` written for both humans and crawlers (what it is, live URL, verify-yourself instructions, honesty labels)

Founder does (one session):

- Create the repository under their account
- Push the prepared tree

Evidence required: public repo URL returning 200, README rendering, no secret material in history.

#### Milestone 1.4: Crawler Hygiene

Search and AI crawlers can reach the descriptive pages without obstruction.

**Status:** Complete (2026-09-26)

Deployed live via paste-safe base64 one-liners. Public verification:
`/` → 200 (landing page, correct title), `/robots.txt` → 200,
`/sitemap.xml` → 200, `/llms.txt` → 200, `POST /verify` → 200 with a fresh
CONFIRMED packet (`VRF-20260926-13b1d042`). Caddy validated clean
("Valid configuration") before reload; the app behind the proxy is unaffected.

The bundle carries everything (`deploy/Caddyfile` handle blocks,
`deploy/static/robots.txt` + `sitemap.xml`, installer step). Live deployment
was deferred 2026-09-26 after paste instability in the terminal session made
multi-line edits unreliable at 1 AM. This blocks nothing: with no robots.txt
present, the default is allow-all, so no crawler is obstructed. The
machine-readable doc that matters (`/llms.txt`, correct domain) is live.

Update 2026-09-26 morning: a human **landing page** was added
(`deploy/static/index.html` — domain-agnostic, fills host via JS) plus a
`handle /` block in the Caddyfile so `/` serves it while everything else still
proxies to the app. Verified against official Caddy docs: v2 path matching is
exact, so `handle /` matches only the root. Paste-ready base64 one-liners for
all four files (robots.txt, sitemap.xml, index.html, full Caddyfile) were
prepared for the Founder's terminal session — backup, validate, reload, verify.

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

All four required. **Gate G1: 100% COMPLETE (2026-09-26)** — /llms.txt live ✓,
MCP end-to-end ✓, GitHub public ✓, robots.txt + sitemap.xml live ✓.
MARKET-2 is now open.

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

**Status:** First attempt failed 2026-09-26 — the r/vibecoding post
(u/Thenightmancumeth, `1wqt2bn`) was removed by Reddit for content-policy
violation and the account was banned from the community. Likely causes:
the sub requires dev-tool posts to be pre-approved (rule 2: "Vibe coding
dev tools must be approved"; rule 3: "No shilling"), and Reddit's automated
filters are hostile to duckdns.org links (free dynamic-DNS domains are
heavily abused by spammers, so they get filtered on sight). Lessons for
the next attempts: get pre-approval where a sub requires it, lead with the
GitHub repo link (trusted domain) instead of the duckdns URL — the live
demo link already lives in the repo README — and follow each sub's showcase
format. Do not evade the ban with alt accounts (that risks sitewide
suspension). Next: r/SideProject in their format.

Prepared by assistant:

- `dist/reddit-post.md` — the post text
- Target subs with rules noted: r/SideProject (self-promo format), r/alphaandbetausers (beta rules), r/selfhosted, r/Python

Founder posts in their own words (the draft is a starting point, not a script).

Evidence: post URLs recorded.

#### Milestone 2.3: Show HN

**Status:** Blocked on platform — Hacker News is temporarily restricting
Show HN submissions (observed 2026-09-26 on news.ycombinator.com/showhn:
"a massive influx, mostly by users who aren't yet familiar with the site or
its culture"). This is platform-wide, not specific to us. Draft kept warm;
retry after the restriction lifts.

Prepared by assistant: `dist/hn-post.md` (title + first comment).

Evidence: HN item URL recorded.

#### Milestone 2.4: API Directories

**Status:** Blocked on Founder (account creation needs identity)

Targets: RapidAPI, Postman Public API Network.

Prepared by assistant: `dist/directory-listing.md` — name, tagline, description, tags, endpoint docs.

Evidence: listing URLs recorded.

#### Milestone 2.5: Bot Discovery (registries)

**Status:** Submission kit ready 2026-09-26; PyPI packaging DONE the same
day (assistant). Submissions + PyPI publish in Founder's hands.
**Date added:** 2026-09-26 — the founder asked how to reach "the other bots
of the world." Honest answer: bots don't browse ads; they discover tools
through registries their developers configure, machine-readable docs
(/llms.txt — done), MCP configs (done), and training data (public repo —
in motion). All discovery must be pull, never push: no fabricated bot
testimonials, no injected recommendations, no misleading descriptions.

Prepared by assistant:

- `dist/mcp-registry-submissions.md` — the full submission kit
- awesome-mcp-servers PR line (canonical punkpeye list, PR from Founder's account)
- `mcp/pyproject.toml` + `mcp/LICENSE` (MIT, provisional) + `mcp/server.json`
  — package `verify-atom-mcp` v0.1.0, console script `verify-atom-mcp`;
  build + clean-venv install + MCP handshake verified 2026-09-26.
  PyPI upload + `mcp-publisher publish` need the Founder's accounts.
- Smithery / Glama / mcp.so / PulseMCP claim-and-submit steps (Founder's clicks)

Evidence: PR URLs, PyPI page, registry listing URLs recorded.

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
| 2026-09-26 | M1.3 repo prepared: committed, secret-scanned, zip uploaded | Assistant | awaiting Founder push to github |
| 2026-09-26 | M1.4 deployed live: /, /robots.txt, /sitemap.xml all 200; /verify unaffected | Both | public curl verification |
| 2026-09-26 | M1.3 complete: repo public at github.com/asherengos/verify-atom | User + Assistant | public URL verified |
| 2026-09-26 | **Gate G1: 100% COMPLETE** — /llms.txt domain ✓, MCP real call ✓, GitHub public ✓, robots/sitemap live ✓ | — | gate closed |
| 2026-09-26 | MARKET-2 plan + all drafts (Reddit, Show HN, directory listing) reviewed and approved by Founder; posting now in their hands | User | this file |
| 2026-09-26 | M2.2 in flight: Reddit post live in r/vibecoding (u/Thenightmancumeth), awaiting mod approval | User | post URL TBD |
| 2026-09-26 | M2.3 blocked: HN temporarily restricting Show HNs platform-wide; draft held for retry | Assistant | news.ycombinator.com/showhn banner |
| 2026-09-26 | M2.2 setback: r/vibecoding post removed by Reddit + community ban; fallback plan set (GitHub-first links, pre-approval where required) | User + Assistant | reddit.com/r/vibecoding/comments/1wqt2bn/ |
| 2026-09-26 | M2.5 added: Bot Discovery (registries) — submission kit written; honest pull-not-push strategy recorded | Assistant | dist/mcp-registry-submissions.md |
| 2026-09-26 | M2.5 packaging DONE: verify-atom-mcp 0.1.0 (pyproject, MIT LICENSE provisional, server.json, mcp-name marker); build + clean-venv install + MCP handshake verified | Assistant | mcp/pyproject.toml, mcp/server.json |
