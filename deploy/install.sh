#!/usr/bin/env bash
# One-shot installer: verification service ("the atom") on Ubuntu 24.04 ARM.
#
# Run ON the VM as root, from the extracted tarball directory:
#     sudo bash install.sh <your-domain>
# Example:
#     sudo bash install.sh verify-demo.duckdns.org
#
# What it does (idempotent -- safe to re-run):
#   1. installs base packages + Caddy (official repo, automatic HTTPS)
#   2. creates the unprivileged `verify` user and installs the app to
#      /opt/verify-service (your dev data/keys are NEVER copied)
#   3. builds a venv and installs flask + waitress
#   4. installs + starts the hardened systemd unit
#      (fresh production Ed25519 keypair is generated on first boot)
#   5. installs the Caddyfile for <your-domain> and reloads Caddy
#   6. opens 80/443 in ufw if ufw is active (the Oracle VCN security
#      list was already opened during VM setup)
#   7. verifies /health and prints the production PUBLIC key
#
# Payments stay OFF: config.yaml ships with payments.enabled=false and
# the app refuses to start otherwise (fail-closed guard).
set -euo pipefail

DOMAIN="${1:?Usage: sudo bash install.sh <your-domain>   (e.g. verify-demo.duckdns.org)}"
APP_DIR=/opt/verify-service
APP_USER=verify
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Allow running as deploy/install.sh from the package root too.
if [ ! -f "$SCRIPT_DIR/app.py" ] && [ -f "$SCRIPT_DIR/../app.py" ]; then
    SCRIPT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

need() { command -v "$1" >/dev/null 2>&1 || { echo "MISSING: $1"; exit 1; }; }

echo "==> [1/7] Base packages"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-venv python3-pip curl gnupg apt-transport-https ca-certificates \
    > /dev/null
echo "    ok"

echo "==> [2/7] Caddy (official repo)"
if ! command -v caddy >/dev/null 2>&1; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq caddy > /dev/null
fi
echo "    caddy $(caddy version | head -1)"

echo "==> [3/7] App user + code -> $APP_DIR"
id -u "$APP_USER" >/dev/null 2>&1 || useradd -r -m -s /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"
# Copy code only -- never data/ (dev keys + ledger must NOT ship).
for f in app.py config.yaml cost_model.yaml costs.py ledger.py mini_yaml.py \
         rate_limit.py signing.py requirements.txt README.md GO_LIVE_MAP.md; do
    [ -f "$SCRIPT_DIR/$f" ] || { echo "tarball missing: $f"; exit 1; }
    cp "$SCRIPT_DIR/$f" "$APP_DIR/$f"
done
mkdir -p "$APP_DIR/deploy"
cp "$SCRIPT_DIR/deploy/verify-service.service" "$APP_DIR/deploy/"
cp "$SCRIPT_DIR/deploy/Caddyfile" "$APP_DIR/deploy/"
cp "$SCRIPT_DIR/deploy/DEPLOY.md" "$APP_DIR/deploy/" 2>/dev/null || true
# Fresh, empty data dir owned by the app user. First boot generates the
# PRODUCTION keypair here; nothing from dev is carried over.
rm -rf "$APP_DIR/data"
install -d -o "$APP_USER" -g "$APP_USER" -m 700 "$APP_DIR/data"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 755 "$APP_DIR"
echo "    code installed (data/ is fresh and empty)"
# Stamp the deploy domain into the machine-readable API doc.
sed -i "s|https://YOUR-DOMAIN-HERE|https://$DOMAIN|g" "$APP_DIR/app.py"
echo "    llms.txt stamped with https://$DOMAIN"
# Crawler hygiene: static robots.txt + sitemap.xml, served by Caddy
# (see the handle blocks in deploy/Caddyfile). Stamped with this domain.
for f in deploy/static/robots.txt deploy/static/sitemap.xml; do
    [ -f "$SCRIPT_DIR/$f" ] || { echo "tarball missing: $f"; exit 1; }
done
install -d -m 755 /var/www/verify-static
sed "s/VERIFY_DOMAIN_HERE/$DOMAIN/g" "$SCRIPT_DIR/deploy/static/sitemap.xml" \
    > /var/www/verify-static/sitemap.xml
sed "s/asheraistudios.duckdns.org/$DOMAIN/g" "$SCRIPT_DIR/deploy/static/robots.txt" \
    > /var/www/verify-static/robots.txt
cp "$SCRIPT_DIR/deploy/static/index.html" /var/www/verify-static/index.html
echo "    crawler files + landing page installed for $DOMAIN"

echo "==> [4/7] Python venv (flask + waitress)"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
fi
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
echo "    venv ready"

echo "==> [5/7] systemd service"
cp "$APP_DIR/deploy/verify-service.service" /etc/systemd/system/verify-service.service
systemctl daemon-reload
systemctl enable --now verify-service > /dev/null
# wait for the socket (up to 30s)
for i in $(seq 1 30); do
    if curl -sf -o /dev/null http://127.0.0.1:5057/health; then break; fi
    sleep 1
done
systemctl is-active --quiet verify-service \
    || { echo "SERVICE FAILED TO START:"; journalctl -u verify-service -n 30 --no-pager; exit 1; }
echo "    verify-service is active"

echo "==> [6/7] Caddy reverse proxy for $DOMAIN"
sed "s/verify.example.com/$DOMAIN/g" "$APP_DIR/deploy/Caddyfile" \
    > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl reload caddy
echo "    caddy reloaded (TLS certificate is fetched automatically)"

echo "==> [7/7] Firewall"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow 80,443/tcp > /dev/null
    echo "    ufw: 80/443 opened"
else
    echo "    ufw not active -- relying on the Oracle VCN security list (already open)"
fi

echo
echo "=========================== VERIFY ==========================="
echo "Local health:"
curl -s http://127.0.0.1:5057/health; echo
echo
echo "Public key (this is PUBLIC -- safe to share):"
curl -s http://127.0.0.1:5057/key; echo
echo
echo "Public URL (give DNS a minute, then open in a browser):"
echo "    https://$DOMAIN/health"
echo
echo "=========== IMPORTANT: BACK UP THE PRIVATE KEY ==============="
echo "A fresh production keypair was generated on first boot."
echo "Copy the private key OFF this machine right now and store it"
echo "somewhere safe (password manager / offline USB):"
echo "    sudo cat $APP_DIR/data/keys/private.key"
echo "If this key is lost, old proof packets can no longer be"
echo "re-issued under this identity. If it leaks, rotate it."
echo "=============================================================="
echo "Done. Logs: journalctl -u verify-service -f"
