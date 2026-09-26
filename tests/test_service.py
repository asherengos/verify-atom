"""Hermetic test suite for the verification service.

No test touches the external network: the happy-path test runs a stub
HTTP server on 127.0.0.1 with ``allow_private: true`` in a throwaway
config, while the SSRF tests assert the default config refuses
loopback outright (before any connection is attempted).
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

import signing
from app import SERVICE_ROOT, create_app
from costs import Usage, compute_cost, load_rates
from mini_yaml import MiniYAMLError, loads as yaml_loads

STUB_BODY = (
    b"<html><head><title>Stub Page</title></head>"
    b"<body>hello verifier</body></html>"
)


class StubHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(STUB_BODY)))
        self.end_headers()
        self.wfile.write(STUB_BODY)

    def log_message(self, *args):  # silence the stub
        pass


@pytest.fixture()
def stub_port():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    thread.join(timeout=5)


def write_config(tmp_path: Path, *, allow_private=False, payments_enabled=False,
                 provider=False, rate_limit_per_minute=None) -> Path:
    data_dir = tmp_path / "data"
    lines = [
        "service:",
        '  version: "0.1.0-test"',
        "  port: 5057",
        f'  data_dir: "{data_dir}"',
        "verify:",
        "  base_price_usd: 0.005",
        "  timeout_s: 10",
        "  max_body_bytes: 2097152",
        "  max_url_length: 2048",
        f"  allow_private: {'true' if allow_private else 'false'}",
    ]
    if rate_limit_per_minute is not None:
        lines.append(f"  rate_limit_per_minute: {rate_limit_per_minute}")
    lines += [
        f'cost_model: "{SERVICE_ROOT / "cost_model.yaml"}"',
        "payments:",
        f"  enabled: {'true' if payments_enabled else 'false'}",
    ]
    if provider:
        lines += [
            "  provider:",
            '    name: "example"',
            "    credentials_configured: true",
        ]
    path = tmp_path / "config.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def app(tmp_path):
    return create_app(write_config(tmp_path, allow_private=True))


@pytest.fixture()
def client(app):
    return app.test_client()


# --- signing ------------------------------------------------------------------

def test_sign_verify_round_trip(tmp_path):
    keystore = signing.KeyStore(tmp_path / "keys")
    record = {"id": "VRF-20200101-deadbeef", "verdict": "CONFIRMED", "n": 3}
    signature = keystore.sign_record(record)
    assert len(signature) == 128
    signed = {**record, "signature": signature}
    assert signing.verify_record(keystore.public_key_hex, signed)


def test_tampered_record_fails_verification(tmp_path):
    keystore = signing.KeyStore(tmp_path / "keys")
    record = {"id": "VRF-20200101-deadbeef", "verdict": "CONFIRMED"}
    signed = {**record, "signature": keystore.sign_record(record)}
    tampered = {**signed, "verdict": "UNCONFIRMED"}
    assert not signing.verify_record(keystore.public_key_hex, tampered)
    wrong_key = signing.KeyStore(tmp_path / "other-keys")
    assert not signing.verify_record(wrong_key.public_key_hex, signed)
    bad_sig = {**signed, "signature": "00" * 64}
    assert not signing.verify_record(keystore.public_key_hex, bad_sig)


def test_key_files_are_owner_only(tmp_path):
    keystore = signing.KeyStore(tmp_path / "keys")
    import os, stat
    mode = stat.S_IMODE(os.stat(keystore.private_path).st_mode)
    assert mode == 0o600


# --- /verify happy path (hermetic) --------------------------------------------

def test_verify_happy_path(client, stub_port):
    import hashlib
    response = client.post("/verify", json={
        "type": "http_observation",
        "url": f"http://127.0.0.1:{stub_port}/page",
    })
    assert response.status_code == 200
    packet = response.get_json()
    assert packet["verdict"] == "CONFIRMED"
    assert packet["type"] == "http_observation"
    assert packet["id"].startswith("VRF-")
    obs = packet["observation"]
    assert obs["http_status"] == 200
    assert obs["page_title"] == "Stub Page"
    assert obs["body_sha256"] == hashlib.sha256(STUB_BODY).hexdigest()
    assert obs["reachable"] is True
    assert packet["evidence"], "a proof packet must carry evidence"
    # cost accounting is present, transparent, and labeled an estimate
    assert packet["cost_basis"] == "estimate"
    assert packet["cost_usd"] >= 0
    assert packet["price_quote_usd"] == 0.005
    assert packet["margin_usd"] == pytest.approx(0.005 - packet["cost_usd"])
    assert isinstance(packet["below_cost"], bool)
    # the packet's own signature verifies against the advertised public key
    assert signing.verify_record(packet["signing"]["public_key_hex"], packet)


def test_get_verification_round_trip(client, stub_port):
    created = client.post("/verify", json={
        "type": "http_observation",
        "url": f"http://127.0.0.1:{stub_port}/",
    }).get_json()
    fetched = client.get(f"/verify/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["id"] == created["id"]
    assert client.get("/verify/VRF-20200101-deadbeef").status_code == 404
    assert client.get("/verify/not-an-id").status_code == 404


def test_ledger_appends_and_feed_is_oldest_first(client, stub_port):
    first = client.post("/verify", json={
        "type": "http_observation", "url": f"http://127.0.0.1:{stub_port}/a",
    }).get_json()
    second = client.post("/verify", json={
        "type": "http_observation", "url": f"http://127.0.0.1:{stub_port}/b",
    }).get_json()
    feed = client.get("/board/feed").get_json()
    assert [entry["id"] for entry in feed] == [first["id"], second["id"]]
    assert feed[0]["verdict"] == "CONFIRMED"
    assert feed[0]["url"] == f"http://127.0.0.1:{stub_port}/a"
    assert set(feed[0]) == {"id", "timestamp_utc", "type", "verdict", "url"}


# --- SSRF guard -----------------------------------------------------------------

@pytest.mark.parametrize("url", ["http://127.0.0.1:9/", "http://localhost:9/"])
def test_ssrf_guard_blocks_loopback(tmp_path, url):
    app = create_app(write_config(tmp_path))  # allow_private defaults false
    client = app.test_client()
    response = client.post("/verify", json={"type": "http_observation", "url": url})
    assert response.status_code == 200  # the check ran; the observation failed
    packet = response.get_json()
    assert packet["verdict"] == "ERROR"
    assert "ssrf_refused" in packet["observation"]["reason"]
    assert packet["observation"]["reachable"] is False


def test_ssrf_guard_blocks_non_http_scheme(tmp_path):
    app = create_app(write_config(tmp_path))
    client = app.test_client()
    packet = client.post("/verify", json={
        "type": "http_observation", "url": "file:///etc/passwd",
    }).get_json()
    assert packet["verdict"] == "ERROR"
    assert "ssrf_refused" in packet["observation"]["reason"]


# --- request validation ---------------------------------------------------------

def test_unknown_verify_type_is_400(client):
    response = client.post("/verify", json={"type": "telepathy", "url": "http://x/"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "unknown_type"


def test_missing_url_is_400(client):
    assert client.post("/verify", json={"type": "http_observation"}).status_code == 400
    assert client.post("/verify", data="not json",
                       content_type="application/json").status_code == 400


# --- payments fail-closed ---------------------------------------------------------

def test_payments_enabled_without_provider_refuses_startup(tmp_path):
    with pytest.raises(RuntimeError, match="Refusing to start"):
        create_app(write_config(tmp_path, payments_enabled=True))


def test_health_reports_payments_disabled(client):
    health = client.get("/health").get_json()
    assert health["status"] == "ok"
    assert health["payments_enabled"] is False


# --- /key -------------------------------------------------------------------------

def test_key_endpoint_never_leaks_private_key(tmp_path):
    app = create_app(write_config(tmp_path, allow_private=True))
    keystore = app.config["VRF_KEYSTORE"]
    response = app.test_client().get("/key")
    payload = response.get_json()
    assert payload["algorithm"] == "Ed25519"
    assert payload["public_key_hex"] == keystore.public_key_hex
    assert len(payload["public_key_hex"]) == 64
    text = response.get_data(as_text=True).lower()
    assert "private" not in text
    private_hex = (keystore.keys_dir / "private.key").read_text().strip()
    assert private_hex not in text


# --- costs --------------------------------------------------------------------------

def test_cost_model_loads_and_computes():
    rates = load_rates(SERVICE_ROOT / "cost_model.yaml")
    usage = Usage(wall_time_s=2.0, bytes_in=1024 * 1024, http_requests=3)
    expected = (2.0 * rates["per_second_compute_usd"]
                + 3 * rates["per_http_request_usd"]
                + 1.0 * rates["per_mb_egress_usd"])
    assert compute_cost(usage, rates) == pytest.approx(round(expected, 9))
    assert compute_cost(Usage(0, 0, 0), rates) == 0.0


def test_cost_model_rejects_bad_rates(tmp_path):
    bad = tmp_path / "cost_model.yaml"
    bad.write_text("rates:\n  per_second_compute_usd: -1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing rates"):
        load_rates(bad)


# --- mini_yaml ------------------------------------------------------------------------

def test_mini_yaml_subset():
    doc = yaml_loads("""
# a comment
service:
  port: 5057 # trailing comment
  name: "verify"
  flag: true
  ratio: 0.005
  nothing: null
""")
    assert doc == {"service": {"port": 5057, "name": "verify", "flag": True,
                               "ratio": 0.005, "nothing": None}}


def test_mini_yaml_rejects_non_subset():
    with pytest.raises(MiniYAMLError):
        yaml_loads("key:\n\tindented: 1\n")  # tabs
    with pytest.raises(MiniYAMLError):
        yaml_loads("items:\n  - one\n")  # lists


def test_shipped_configs_parse():
    from app import load_config
    cfg = load_config(SERVICE_ROOT / "config.yaml")
    assert cfg["service"]["port"] == 5057
    assert cfg["payments"]["enabled"] is False
    assert cfg["verify"]["rate_limit_per_minute"] == 30
    load_rates(SERVICE_ROOT / "cost_model.yaml")


# --- rate limiting --------------------------------------------------------------

# These use an SSRF-refused URL (allow_private=false, loopback target) so
# each POST is fast and hermetic: the check runs, the observation is
# refused, and the limiter still counts the attempt.
_REFUSED = {"type": "http_observation", "url": "http://127.0.0.1:9/"}


def test_limiter_defaults_to_30_per_minute(tmp_path):
    app = create_app(write_config(tmp_path))  # no rate_limit key in config
    limiter = app.config["VRF_LIMITER"]
    assert limiter is not None
    assert limiter.max_requests == 30


def test_rate_limit_allows_under_cap(tmp_path):
    app = create_app(write_config(tmp_path, rate_limit_per_minute=5))
    client = app.test_client()
    for _ in range(5):
        assert client.post("/verify", json=_REFUSED).status_code == 200


def test_rate_limit_denies_over_cap_with_retry_after(tmp_path):
    app = create_app(write_config(tmp_path, rate_limit_per_minute=2))
    client = app.test_client()
    assert client.post("/verify", json=_REFUSED).status_code == 200
    assert client.post("/verify", json=_REFUSED).status_code == 200
    denied = client.post("/verify", json=_REFUSED)
    assert denied.status_code == 429
    payload = denied.get_json()
    assert payload["error"] == "rate_limited"
    assert payload["retry_after_s"] >= 1
    assert denied.headers["Retry-After"] == str(payload["retry_after_s"])


def test_rate_limit_is_per_ip(tmp_path):
    app = create_app(write_config(tmp_path, rate_limit_per_minute=1))
    client = app.test_client()
    assert client.post("/verify", json=_REFUSED).status_code == 200
    assert client.post("/verify", json=_REFUSED).status_code == 429
    # A different client IP (seen via the proxy header) gets its own budget.
    other = {"X-Forwarded-For": "203.0.113.7"}
    assert client.post("/verify", json=_REFUSED, headers=other).status_code == 200
    assert client.post("/verify", json=_REFUSED, headers=other).status_code == 429


def test_rate_limit_window_slides():
    from rate_limit import RateLimiter
    limiter = RateLimiter(2, window_s=60.0)
    assert limiter.check("1.2.3.4", 1000.0) == (True, 0.0)
    assert limiter.check("1.2.3.4", 1001.0) == (True, 0.0)
    allowed, retry_after = limiter.check("1.2.3.4", 1002.0)
    assert allowed is False
    assert retry_after > 0
    # Once the window slides past the first hit, capacity returns.
    assert limiter.check("1.2.3.4", 1061.0) == (True, 0.0)


def test_rate_limit_disabled_at_zero(tmp_path):
    app = create_app(write_config(tmp_path, rate_limit_per_minute=0))
    assert app.config["VRF_LIMITER"] is None


# --- /llms.txt --------------------------------------------------------------------

def test_llms_txt_served_as_plain_text(client):
    response = client.get("/llms.txt")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    text = response.get_data(as_text=True)
    assert "POST /verify" in text
    assert "PAYMENTS ARE DISABLED" in text
    assert "GET /board/feed" in text
    assert "YOUR-DOMAIN-HERE" in text
