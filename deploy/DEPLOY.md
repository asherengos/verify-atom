# Deploy Runbook — verification service, $0 go-live

Goal: the service from this repo running publicly at `https://YOUR-DOMAIN`,
serving real verifications, accumulating real board entries — with payments
**OFF** and total spend **$0**.

Every step is marked **[HUMAN]** (you do it — it needs your identity, your
accounts, or your hands) or **[ASSISTANT]** (I can do it / it is scripted).
Nothing here deploys itself: this bundle is the plan and the files, not a
live server.

**Standing rules for this deploy** (do not skip):
- The $0 ceiling is in effect. Nothing here should cost money.
- Payments stay OFF. There is no payment code in v1; do not add any.
- `allow_private` stays `false` in production (it exists only for tests).
- The production keypair is generated FRESH on the VM. Never copy `data/`
  from a dev machine — it holds dev keys and test ledger residue.

---

## Phase 1 — Oracle Cloud account & VM [HUMAN]

1. Sign up at cloud.oracle.com. You will need an email, identity
   verification, and a credit card **for verification only** — Always Free
   resources are never charged. (If you are uncomfortable putting a card on
   file, stop here and say so; the backup is GCP's always-free e2-micro.)
2. Create a compartment, then a VCN with an internet gateway, a public
   subnet, and a security list / NSG opening **22 (SSH)**, **80 (HTTP)**,
   and **443 (HTTPS)**. Restrict port 22 to your own IP if you can.
3. Launch an instance:
   - Image: **Ubuntu 24.04** (Canonical)
   - Shape: **VM.Standard.A1.Flex** (ARM / Ampere) — 2 OCPUs, 12 GB RAM
     fits the Always Free allowance. (x86 `VM.Standard.E2.1.Micro` is the
     other Always Free shape if ARM gives you trouble.)
   - Add your SSH **public** key; assign a public IPv4 address.
   - **Expect "Out of host capacity" errors.** This is normal on the free
     tier — people retry for days, trying different times of day and
     regions. Do not pay to skip the queue; patience is the $0 strategy.
4. SSH in: `ssh -i <your-key> ubuntu@<PUBLIC-IP>`. You should get a shell.

> Backup plan: if Oracle will not provision after sustained retries,
> Google Cloud's **e2-micro** always-free tier is the fallback. The rest of
> this runbook is identical from Phase 2 on.

## Phase 2 — base hardening [HUMAN — run these on the VM]

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install unattended-upgrades ufw
sudo systemctl enable --now unattended-upgrades
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw --force enable && sudo ufw status
# service user: owns the code and data, cannot log in, has no sudo
sudo useradd -r -m -d /opt/verify-service -s /usr/sbin/nologin verify
```

## Phase 3 — copy the code [HUMAN]

From your own machine (not on the VM):

```bash
rsync -avz --exclude data --exclude .venv --exclude __pycache__ \
  ~/workspace/verify-service/ ubuntu@<PUBLIC-IP>:/tmp/verify-service/
```

Then on the VM:

```bash
sudo cp -a /tmp/verify-service/. /opt/verify-service/
sudo chown -R verify:verify /opt/verify-service
ls /opt/verify-service   # expect: app.py, config.yaml, deploy/, tests/, ...
```

**Never copy `data/`** — dev keys and the test ledger must not reach
production. Double-check it is absent: `ls /opt/verify-service/data`
should fail with "No such file or directory".

## Phase 4 — Python env + FIRST-BOOT keypair [HUMAN — on the VM]

```bash
sudo apt -y install python3-venv
sudo -u verify python3 -m venv /opt/verify-service/.venv
sudo -u verify /opt/verify-service/.venv/bin/pip install \
  -r /opt/verify-service/requirements.txt   # flask + waitress only; free
```

First boot — run it in the foreground once and watch it start:

```bash
sudo -u verify /opt/verify-service/.venv/bin/python /opt/verify-service/app.py
```

You should see `verify-service v0.1.0 on 127.0.0.1:5057
(payments_enabled=false)`. Press Ctrl-C to stop it.

This first run **generates the production Ed25519 keypair**. Confirm:

```bash
sudo -u verify ls -l /opt/verify-service/data/keys/
# -rw------- ... private.key     (0600 -- owner-only)
# -rw------- ... public.key
```

Now **back up `private.key` OFFLINE, immediately** — copy it to an
encrypted USB stick or your password manager, then delete the copy from
anywhere transient. Losing it orphans the board's trust chain (old packets
still verify against the published public key, but the service can never
sign again). Leaking it lets anyone forge "verified" packets in your name.

Sanity check that production config is safe:

```bash
grep -E 'allow_private|enabled' /opt/verify-service/config.yaml
# allow_private: false   <- must be false
# enabled: false         <- payments OFF; must be false
```

## Phase 5 — systemd [HUMAN — on the VM]

```bash
sudo cp /opt/verify-service/deploy/verify-service.service \
        /etc/systemd/system/verify-service.service
sudo systemctl daemon-reload
sudo systemctl enable --now verify-service
systemctl status verify-service     # active (running)
journalctl -u verify-service -f     # logs; Ctrl-C to exit
curl -s http://127.0.0.1:5057/health
# {"status":"ok","version":"0.1.0","payments_enabled":false}
```

If it fails to start, `journalctl -u verify-service -n 50` tells you why.
(Common cause: a typo'd config — the service fails closed and says so.)

## Phase 6 — Caddy (public HTTPS) [HUMAN]

1. Install Caddy (see https://caddyserver.com/docs/install — free and
   open source; use the official apt repo for Ubuntu).
2. Pick your domain:
   - **Day one ($0): a free DuckDNS subdomain** (e.g.
     `yourname.duckdns.org`) pointed at the VM's public IP. Oracle gives
     you a public IP but no free subdomain, so this is the honest $0 path.
     (Check DuckDNS's current terms before relying on it.)
   - **Later (~$12/yr): a real domain**, bought only after the first
     stranger shows interest. $0 until signal.
3. Edit `/etc/caddy/Caddyfile`: copy `deploy/Caddyfile` there and replace
   `verify.example.com` with your domain.
4. Validate and reload:
   ```bash
   sudo caddy validate --config /etc/caddy/Caddyfile
   sudo systemctl reload caddy
   ```
   Caddy fetches a public TLS certificate automatically (this is why ports
   80/443 must be open and DNS must already resolve to the VM).
5. Public check: `curl -s https://<YOUR-DOMAIN>/health` should return the
   same `{"status":"ok",...,"payments_enabled":false}`.

## Phase 7 — go-live verification [HUMAN]

1. **Payments OFF, confirmed twice:**
   ```bash
   curl -s https://<YOUR-DOMAIN>/health | grep payments_enabled
   # "payments_enabled": false
   ```
   and on the VM: `grep -A1 '^payments:' /opt/verify-service/config.yaml`
   shows `enabled: false`.
2. **One end-to-end public verification** (real network now — the sandbox
   limitation is gone on the VM):
   ```bash
   curl -s -X POST https://<YOUR-DOMAIN>/verify \
     -H 'Content-Type: application/json' \
     -d '{"type":"http_observation","url":"https://example.com"}' \
     | python3 -m json.tool
   ```
   Expect `verdict: CONFIRMED`, evidence, `cost_basis: "estimate"`,
   `price_quote_usd` (a quote, not a charge), and a `signature`.
3. **Spot-check the signature** (trust nothing): fetch
   `https://<YOUR-DOMAIN>/key`, strip `signature`/`signing` from the
   packet, and Ed25519-verify the canonical JSON. Any implementation
   works; a tampered packet must fail.
4. **Rate limit check (optional but recommended):** fire 35 quick POSTs;
   the tail should return `429` with a `Retry-After` header.
5. **Monitoring:** add a free UptimeRobot monitor on
   `https://<YOUR-DOMAIN>/health` (50 monitors free).

You are live. The board (`/board/feed`) now accumulates REAL entries.

## Phase 8 — operate [HUMAN, ongoing]

- **Logs:** `journalctl -u verify-service -f`.
- **Ledger:** `/opt/verify-service/data/ledger.jsonl` — append-only, the
  board's source of truth. Back it up (copy it off the VM regularly; it
  is small). Never edit it by hand.
- **Honest loop inputs:** watch `below_cost` counts and error rates in the
  ledger; they feed the cost-vs-revenue measurement.
- **Updates:** `sudo systemctl stop verify-service`, rsync the code
  (still excluding `data/`), `sudo systemctl start verify-service`.
  **Never run two instances against one data dir** (no cross-process
  ledger locking in v1).
- **Cost calibration:** after real traffic, measure actual resource use,
  update `cost_model.yaml` rates, restart. Quotes are only honest once
  the model is calibrated.
- **Kill criteria:** 60–90 days after go-live with zero usage → kill or
  pivot. The ledger decides, not feelings (see GO_LIVE_MAP.md).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Out of host capacity" on launch | Normal on Always Free — retry over days / other regions |
| Caddy gets no certificate | DNS not yet pointing at the VM, or 80/443 blocked in the security list |
| `502 Bad Gateway` from Caddy | service not running — `systemctl status verify-service`, then `journalctl -u verify-service -n 50` |
| Service refuses to start, "Refusing to start" | `payments.enabled` true without a provider, or bad config — fail-closed is working as designed |
| `429` on your own tests | The per-IP limiter doing its job; wait a minute or test from another IP |
