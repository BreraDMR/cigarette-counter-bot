"""Exchange rates, for converting what the consumables cost.

Three currencies: euro, hryvnia, Czech crown. Rates come from
https://open.er-api.com (free, no key, EUR as the base) and are cached in /data
for half a day. With no network we fall back to hardcoded approximate numbers,
because a bot that dies over a missing exchange rate is worse than one that is
a few percent off. Nothing here pretends to be accounting-grade.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("cigarette-bot.rates")

_API = "https://open.er-api.com/v6/latest/EUR"
# How often to refresh, in hours. The free API is generous but there is no
# reason to hit it more than twice a day for approximate numbers.
_TTL = int(float(os.environ.get("RATES_TTL_HOURS", "12")) * 3600)
_CODES = ("EUR", "UAH", "CZK")

# Rough fallback (units per 1 EUR) for when the API cannot be reached.
_FALLBACK = {"EUR": 1.0, "UAH": 51.0, "CZK": 24.5}

# Display symbol <-> ISO code
SYMBOL = {"EUR": "€", "UAH": "грн", "CZK": "Kč"}
_SYM2ISO = {
    "€": "EUR", "EUR": "EUR",
    "грн": "UAH", "₴": "UAH", "UAH": "UAH",
    "Kč": "CZK", "kč": "CZK", "CZK": "CZK",
}

_CACHE_PATH = os.path.join(
    os.path.dirname(os.environ.get("DB_PATH", "/data/cigarettes.db")) or "/data",
    "rates.json",
)

# In-process cache: (timestamp, rates)
_mem: tuple[float, dict] | None = None


def iso(symbol: str | None) -> str | None:
    """ISO code for a display symbol, or None if we do not recognise it."""
    if not symbol:
        return None
    return _SYM2ISO.get(symbol.strip())


def _fetch() -> dict | None:
    try:
        with urllib.request.urlopen(_API, timeout=10) as r:
            d = json.load(r)
        if d.get("result") == "success":
            rates = d["rates"]
            # A zero or negative rate is nonsense and would blow up convert().
            got = {c: float(rates[c]) for c in _CODES if c in rates}
            got = {c: v for c, v in got.items() if v > 0}
            if got.get("EUR"):
                return got
    except Exception as e:  # noqa: BLE001 - no network or parse error may kill the bot
        log.warning("Could not fetch exchange rates: %s", e)
    return None


def get_rates() -> dict:
    """Rates in units per 1 EUR, memory-cached, disk-cached, with a fallback."""
    global _mem
    now = time.time()
    if _mem and now - _mem[0] < _TTL:
        return _mem[1]

    # Is the disk cache still fresh?
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            disk = json.load(f)
        if now - disk.get("ts", 0) < _TTL and disk.get("rates"):
            _mem = (disk["ts"], disk["rates"])
            return _mem[1]
    except (OSError, ValueError):
        disk = None

    fresh = _fetch()
    if fresh:
        _mem = (now, fresh)
        try:
            # Write to a temp file and rename: a container restart mid-write
            # used to leave a truncated rates.json that never parsed again.
            tmp = _CACHE_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"ts": now, "rates": fresh}, f)
            os.replace(tmp, _CACHE_PATH)
        except OSError as e:
            log.warning("Could not write the rates cache: %s", e)
        return fresh

    # API said nothing - take yesterday's disk cache, stale or not, then the fallback.
    if disk and disk.get("rates"):
        _mem = (disk["ts"], disk["rates"])
        return _mem[1]
    return _FALLBACK


def convert(amount: float, from_symbol: str | None, to_symbol: str | None) -> float:
    """Convert between currencies at the approximate rate.

    An unrecognised currency comes back untouched rather than as an error -
    showing a number that is off by a rate beats showing nothing at all."""
    a, b = iso(from_symbol), iso(to_symbol)
    if a is None or b is None or a == b:
        return amount
    rates = get_rates()
    if not rates.get(a) or not rates.get(b):
        return amount
    return amount / rates[a] * rates[b]
