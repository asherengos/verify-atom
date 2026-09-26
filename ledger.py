"""Append-only verification ledger.

``data/ledger.jsonl`` holds one JSON object per verification -- the full
signed proof packet. It is the single source of truth for:

* ``GET /verify/<id>`` (scan for the id; O(n), fine for v1 scale)
* ``GET /board/feed`` (oldest first; file order is insertion order)
* the honest loop: per-verification cost vs. price, read by operators
  (and later by the loop itself) to keep winners and kill losers.

The ledger is append-only: records are never edited or deleted. If a
packet is ever found to be wrong, the remedy is a new superseding
verification, not a rewrite -- the history must stay auditable.

Single-worker v1: no file locking. Run one worker per data directory.
"""

from __future__ import annotations

import json
from pathlib import Path


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def append(self, packet: dict) -> None:
        """Append one proof packet. The packet must already be signed."""
        if "signature" not in packet or "id" not in packet:
            raise ValueError("only signed packets with an id may be appended")
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(packet, sort_keys=True) + "\n")

    def _iter_packets(self):
        with open(self.path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def get(self, record_id: str) -> dict | None:
        for packet in self._iter_packets():
            if packet.get("id") == record_id:
                return packet
        return None

    def feed(self) -> list[dict]:
        """Public board feed, oldest first: one summary per verification."""
        return [
            {
                "id": packet["id"],
                "timestamp_utc": packet["timestamp_utc"],
                "type": packet["type"],
                "verdict": packet["verdict"],
                "url": packet.get("target", {}).get("url"),
            }
            for packet in self._iter_packets()
        ]

    def unit_economics(self) -> dict:
        """Aggregate cost vs. price across the ledger (the honest loop's input)."""
        count = 0
        total_cost = 0.0
        total_price = 0.0
        below_cost_count = 0
        for packet in self._iter_packets():
            count += 1
            total_cost += float(packet.get("cost_usd", 0.0))
            total_price += float(packet.get("price_quote_usd", 0.0))
            if packet.get("below_cost"):
                below_cost_count += 1
        return {
            "verifications": count,
            "total_cost_usd_estimate": round(total_cost, 9),
            "total_price_quoted_usd": round(total_price, 9),
            "total_margin_usd_estimate": round(total_price - total_cost, 9),
            "below_cost_count": below_cost_count,
            "cost_basis": "estimate",
        }
