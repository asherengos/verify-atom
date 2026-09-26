# Bot discovery: MCP registry + directory submissions

Goal: the verify-atom MCP server should be findable where agent developers
look. All of these are pull-based discovery (developers choosing tools),
not push — no fake reviews, no injected recommendations, no astroturf.

## 1. awesome-mcp-servers (do first — highest visibility per effort)

Canonical list: https://github.com/punkpeye/awesome-mcp-servers
Method: pull request from the founder's GitHub account.
Their rules: anyone may submit their own project; no minimum stars or age;
the bar is "real, working, maintained" — which we clear (live service,
26/26 tests, public repo).

**Exact line to add** (format: `- [Name](link) - Description.`):

```md
- [verify-atom](https://github.com/asherengos/verify-atom) - MCP server giving AI agents cryptographically signed proof of web observations (Ed25519-signed proof packets for URL checks).
```

**Steps:**
1. Fork punkpeye/awesome-mcp-servers, branch off main.
2. Read their CONTRIBUTING.md (quality standards + what is not accepted).
3. Add the line under the most fitting category — likely "Developer Tools"
   (confirm the exact category name in their README; keep alphabetical order
   within the section).
4. Open the PR, fill in their template including the affiliation question
   (answer honestly: own project).

Evidence: PR URL, then merge.

## 2. Official MCP registry (packaging DONE 2026-09-26 — publish is Founder's)

Registry: https://registry.modelcontextprotocol.io
Schema: https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json
Our future name: `io.github.asherengos/verify-atom`

**Packaging complete (assistant, 2026-09-26):**
- `mcp/pyproject.toml` — project `verify-atom-mcp` v0.1.0, console script
  `verify-atom-mcp`, zero dependencies, `requires-python >= 3.10`.
- `mcp/LICENSE` — MIT (provisional default; Founder can change before publish).
- `mcp/README.md` — now the PyPI long description; carries the
  `<!-- mcp-name: io.github.asherengos/verify-atom -->` ownership marker and
  install-from-source instructions.
- `mcp/server.json` — registry manifest draft (name, title, honest
  description, repository, PyPI stdio package entry).
- Verified: `python -m build` succeeds; wheel installs clean in a fresh venv;
  installed `verify-atom-mcp` answers the MCP initialize + tools/list
  handshake correctly.

**Remaining (Founder, needs their accounts):**
1. PyPI account + `pip install build twine`; `python -m build`; `twine upload dist/*`.
2. Install `mcp-publisher`; `mcp-publisher login github` (proves ownership of
   the `io.github.asherengos/*` namespace — namespace is case-sensitive and
   matches the login exactly); `mcp-publisher validate`; `mcp-publisher publish`.
3. Verify: `curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.asherengos/verify-atom"`.

Once listed, aggregators (Glama, Smithery, mcp.so, PulseMCP) pick it up
automatically — this is the one submission that feeds the others.

## 3. Directories (founder's clicks, ~10 minutes total)

| Directory | How | Note |
|-----------|-----|------|
| Smithery (smithery.ai) | Sign in with GitHub, import the repo | Prefers a `smithery.yaml`; can import without |
| Glama (glama.ai/mcp/servers) | Auto-discovers public GitHub MCP repos — claim the listing | Claiming lets you fix metadata |
| mcp.so | Submit form with the GitHub repo URL | Manual review |
| PulseMCP (pulsemcp.com) | "Add a server" form | Ingests the official registry once we're on it |

## 4. The long game (already in motion)

- **Training data:** the public repo, README, /llms.txt, and docs are crawlable.
  Future models may know verify-atom natively. Nothing to do but keep the
  repo public, documented, and honest.
- **/llms.txt + MCP wrapper:** already live. Any agent pointed at the domain
  can self-serve today with zero auth.

## What we will NOT do

- No fabricated bot testimonials or reviews.
- No injecting recommendations into other agents' conversations.
- No spamming registries with misleading descriptions.
Discovery must be pull (developers finding a genuinely useful tool), never push.
