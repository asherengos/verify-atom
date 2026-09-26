"""Ed25519 signing for verification proof packets.

CRYPTO CORE VENDORED WITH ATTRIBUTION
-------------------------------------
The elliptic-curve code below (curve parameters, point arithmetic,
key generation, RFC 8032 sign/verify, and the key-file helpers) is copied
from the Asher AI Studios Work Kernel, built 2026-09-25:

    ~/workspace/asher-review/work/work-kernel/src/work_kernel/attestation.py

That implementation is pure Python with zero dependencies, follows
RFC 8032 exactly, and was validated against RFC 8032 test vectors and a
reference library by the kernel's own test suite. Only the human-decision
attestation helpers were omitted; key-file handling is adapted below.

Everything after the "service key management" banner is written for this
service: keystore handling, canonical-JSON signing, and packet
verification.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

# --- Vendored curve parameters (RFC 8032, section 5.1) -------------------------

_Q = 2**255 - 19
_D = -121665 * pow(121666, _Q - 2, _Q) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BASE_Y = (4 * pow(5, _Q - 2, _Q)) % _Q
_BASE_X = _xrecover(_BASE_Y)
_L = 2**252 + 27742317777372353535851937790883648493


def _edwards_add(p: tuple[int, int], q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p
    x2, y2 = q
    x3 = (x1 * y2 + x2 * y1) * pow(1 + _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    y3 = (y1 * y2 + x1 * x2) * pow(1 - _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    return (x3 % _Q, y3 % _Q)


def _scalarmult(p: tuple[int, int], e: int) -> tuple[int, int]:
    result = (0, 1)
    addend = p
    while e:
        if e & 1:
            result = _edwards_add(result, addend)
        addend = _edwards_add(addend, addend)
        e >>= 1
    return result


_BASE = (_BASE_X, _BASE_Y)


def _encode_point(p: tuple[int, int]) -> bytes:
    x, y = p
    bits = bin(y)[2:].zfill(255)[::-1] + ("1" if x & 1 else "0")
    return int(bits[::-1], 2).to_bytes(32, "little")


def _decode_point(encoded: bytes) -> tuple[int, int] | None:
    if len(encoded) != 32:
        return None
    y = int.from_bytes(encoded, "little") & (2**255 - 1)
    x = _xrecover(y)
    if (x & 1) != (encoded[31] >> 7):
        x = _Q - x
    point = (x, y)
    if _encode_point(point) != encoded:
        return None
    return point


def _hash(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _clamp(secret: bytes) -> int:
    clamped = bytearray(_hash(secret)[:32])
    clamped[0] &= 248
    clamped[31] &= 63
    clamped[31] |= 64
    return int.from_bytes(bytes(clamped), "little")


KEY_BYTES = 32
SIGNATURE_BYTES = 64


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate a fresh (private_key, public_key) pair, 32 bytes each."""
    private_key = os.urandom(KEY_BYTES)
    public_key = _encode_point(_scalarmult(_BASE, _clamp(private_key)))
    return private_key, public_key


def sign(private_key: bytes, message: bytes) -> bytes:
    """Sign a message; returns the 64-byte signature (RFC 8032, 5.1.6)."""
    if len(private_key) != KEY_BYTES:
        raise ValueError("private key must be 32 bytes")
    hashed = _hash(private_key)
    secret_scalar = int.from_bytes(hashed[:32], "little")
    secret_scalar &= (1 << 254) - 8
    secret_scalar |= 1 << 254
    prefix = hashed[32:]
    public_key = _encode_point(_scalarmult(_BASE, _clamp(private_key)))
    nonce = int.from_bytes(_hash(prefix + message), "little") % _L
    commitment = _encode_point(_scalarmult(_BASE, nonce))
    challenge = int.from_bytes(_hash(commitment + public_key + message), "little") % _L
    response = (nonce + challenge * secret_scalar) % _L
    return commitment + response.to_bytes(32, "little")


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify a signature; False on any malformed input (RFC 8032, 5.1.7)."""
    if len(public_key) != KEY_BYTES or len(signature) != SIGNATURE_BYTES:
        return False
    point_a = _decode_point(public_key)
    if point_a is None:
        return False
    commitment = _decode_point(signature[:32])
    if commitment is None:
        return False
    if _scalarmult(point_a, _L) != (0, 1):
        return False
    response = int.from_bytes(signature[32:], "little")
    if response >= _L:
        return False
    challenge = (
        int.from_bytes(_hash(signature[:32] + public_key + message), "little") % _L
    )
    left = _scalarmult(_BASE, response)
    right = _edwards_add(commitment, _scalarmult(point_a, challenge))
    return left == right


# --- Vendored key-file helpers (adapted) ---------------------------------------

_PRIVATE_KEY_FILE_MODE = 0o600


def write_private_key_file(path: Path, private_key: bytes) -> None:
    """Write a 32-byte private key as hex, readable only by the owner."""
    if len(private_key) != KEY_BYTES:
        raise ValueError("private key must be 32 bytes")
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing key file: {path}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _PRIVATE_KEY_FILE_MODE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(private_key.hex() + "\n")
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    os.chmod(path, _PRIVATE_KEY_FILE_MODE)


def read_private_key_file(path: Path) -> bytes:
    """Read a hex private key file, rejecting wrong sizes and bad hex."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if len(text) != 2 * KEY_BYTES:
        raise ValueError(f"key file does not hold a 32-byte hex private key: {path}")
    try:
        return bytes.fromhex(text)
    except ValueError:
        raise ValueError(f"key file does not hold a 32-byte hex private key: {path}")


# --- Service key management ----------------------------------------------------
#
# SECURITY: the private key is NEVER logged, NEVER returned by any API, and
# NEVER leaves this module except as bytes passed to sign(). Grep for
# "private" in app.py: the only references are to the keystore object and
# the /key route serving the PUBLIC key.

SIGNATURE_EXCLUDED_KEYS = ("signature", "signing")
"""Keys excluded from the signed canonical bytes.

``signature`` is excluded because it IS the signature; ``signing`` is
excluded because it is metadata *about* the signature (algorithm, public
key) attached after signing. Everything else is covered."""


def canonical_bytes(record: dict) -> bytes:
    """Canonical bytes covered by the signature: every field except it."""
    covered = {k: v for k, v in record.items() if k not in SIGNATURE_EXCLUDED_KEYS}
    return json.dumps(covered, sort_keys=True, separators=(",", ":")).encode("utf-8")


class KeyStore:
    """Owns the service Ed25519 identity under ``keys_dir``.

    On first use a keypair is generated and stored with owner-only
    permissions (0600 files, 0700 directory). The private key is held in
    memory only for the process lifetime.
    """

    def __init__(self, keys_dir: Path) -> None:
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.keys_dir, 0o700)
        self.private_path = self.keys_dir / "private.key"
        self.public_path = self.keys_dir / "public.key"
        if self.private_path.exists():
            self._private_key = read_private_key_file(self.private_path)
        else:
            self._private_key, public_key = generate_keypair()
            write_private_key_file(self.private_path, self._private_key)
            self.public_path.write_text(public_key.hex() + "\n", encoding="utf-8")
            os.chmod(self.public_path, _PRIVATE_KEY_FILE_MODE)
        self._public_key = _encode_point(
            _scalarmult(_BASE, _clamp(self._private_key))
        )

    @property
    def public_key_hex(self) -> str:
        return self._public_key.hex()

    def sign_record(self, record: dict) -> str:
        """Sign a proof packet dict (without ``signature``); returns hex."""
        return sign(self._private_key, canonical_bytes(record)).hex()


def verify_record(public_key_hex: str, record: dict) -> bool:
    """Verify a proof packet's signature against its own public key field."""
    try:
        public_key = bytes.fromhex(public_key_hex)
        signature = bytes.fromhex(record["signature"])
    except (KeyError, ValueError):
        return False
    return verify(public_key, canonical_bytes(record), signature)
