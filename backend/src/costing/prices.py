"""The price table: data in ``prices.json``, validated on load. All figures are APPROXIMATE."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

DEFAULT_PRICES_PATH = Path(__file__).with_name("prices.json")
_NAME = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


class PriceError(ValueError):
    """The price table is malformed."""


@dataclass(frozen=True)
class InstancePrice:
    name: str
    vcpus: int
    on_demand_hourly: float
    spot_hourly: float


@dataclass(frozen=True)
class PriceTable:
    label: str
    as_of: str
    region: str
    currency: str
    default_instance: str
    instances: Dict[str, InstancePrice]
    s3_per_gb_month: float
    sqs_per_million: float

    def instance(self, name: Optional[str] = None) -> InstancePrice:
        key = name or self.default_instance
        if key not in self.instances:
            raise KeyError(key)
        return self.instances[key]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "asOf": self.as_of,
            "region": self.region,
            "currency": self.currency,
            "defaultInstance": self.default_instance,
            "instances": {
                n: {
                    "vcpus": i.vcpus,
                    "onDemandHourly": i.on_demand_hourly,
                    "spotHourly": i.spot_hourly,
                }
                for n, i in self.instances.items()
            },
            "s3": {"perGbMonth": self.s3_per_gb_month},
            "sqs": {"perMillionRequests": self.sqs_per_million},
        }


def _price(value: Any, what: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise PriceError(f"{what} must be a non-negative number")
    return float(value)


def _text(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PriceError(f"{key} is required")
    return value


def parse_prices(data: Any) -> PriceTable:
    """Validate a decoded price table; raises ``PriceError`` on the first problem."""
    if not isinstance(data, dict):
        raise PriceError("price table must be a JSON object")
    as_of = _text(data, "asOf")
    try:
        date.fromisoformat(as_of)
    except ValueError:
        raise PriceError("asOf must be an ISO date (YYYY-MM-DD)") from None
    raw = data.get("instances")
    if not isinstance(raw, dict) or not raw:
        raise PriceError("instances must be a non-empty object")
    instances: Dict[str, InstancePrice] = {}
    for name, entry in raw.items():
        if not _NAME.match(str(name)) or not isinstance(entry, dict):
            raise PriceError(f"invalid instance entry {name!r}")
        vcpus = entry.get("vcpus")
        if isinstance(vcpus, bool) or not isinstance(vcpus, int) or vcpus < 1:
            raise PriceError(f"{name}: vcpus must be a positive integer")
        on_demand = _price(entry.get("onDemandHourly"), f"{name}.onDemandHourly")
        spot = _price(entry.get("spotHourly"), f"{name}.spotHourly")
        if spot > on_demand:
            raise PriceError(f"{name}: spotHourly exceeds onDemandHourly")
        instances[name] = InstancePrice(name, vcpus, on_demand, spot)
    default = _text(data, "defaultInstance")
    if default not in instances:
        raise PriceError("defaultInstance is not in instances")
    s3 = data.get("s3")
    sqs = data.get("sqs")
    if not isinstance(s3, dict) or not isinstance(sqs, dict):
        raise PriceError("s3 and sqs sections are required")
    return PriceTable(
        label=_text(data, "label"),
        as_of=as_of,
        region=_text(data, "region"),
        currency=_text(data, "currency"),
        default_instance=default,
        instances=instances,
        s3_per_gb_month=_price(s3.get("perGbMonth"), "s3.perGbMonth"),
        sqs_per_million=_price(sqs.get("perMillionRequests"), "sqs.perMillionRequests"),
    )


def load_prices(path: "Optional[Path | str]" = None) -> PriceTable:
    """Load and validate the table (the bundled one by default)."""
    target = Path(path) if path is not None else DEFAULT_PRICES_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PriceError(f"cannot read price table: {exc}") from exc
    return parse_prices(data)
