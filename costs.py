"""Per-verification cost accounting.

Every verification measures its own resource usage (wall time, bytes
transferred, HTTP requests) and converts it to a USD cost using the
operator-configured rates in ``cost_model.yaml``.

HONESTY: ``cost_usd`` is an ESTIMATE, not a metered cloud bill. The rates
are placeholders the operator sets; every proof packet carries
``"cost_basis": "estimate"`` so no one mistakes it for metered spend.
Replace the rates with metered values before any real pricing.
"""

from __future__ import annotations

from dataclasses import dataclass

from mini_yaml import MiniYAMLError, load as load_yaml


@dataclass
class Usage:
    wall_time_s: float
    bytes_in: int
    http_requests: int


def load_rates(cost_model_path) -> dict:
    """Load ``rates`` from the cost model file; raise on missing keys."""
    try:
        model = load_yaml(cost_model_path)
    except MiniYAMLError as exc:
        raise ValueError(f"cost model unreadable: {exc}") from exc
    rates = model.get("rates")
    if not isinstance(rates, dict):
        raise ValueError("cost model must define a 'rates' mapping")
    required = (
        "per_second_compute_usd",
        "per_http_request_usd",
        "per_mb_egress_usd",
    )
    missing = [key for key in required if key not in rates]
    if missing:
        raise ValueError(f"cost model missing rates: {', '.join(missing)}")
    for key in required:
        value = rates[key]
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"cost model rate {key!r} must be a non-negative number")
    return {key: float(rates[key]) for key in required}


def compute_cost(usage: Usage, rates: dict) -> float:
    """Convert measured usage to an estimated USD cost (9-decimal rounding)."""
    megabytes = usage.bytes_in / (1024 * 1024)
    cost = (
        usage.wall_time_s * rates["per_second_compute_usd"]
        + usage.http_requests * rates["per_http_request_usd"]
        + megabytes * rates["per_mb_egress_usd"]
    )
    return round(max(cost, 0.0), 9)
