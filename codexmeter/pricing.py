"""Versioned, reviewed API-equivalent prices. Never infer a subscription bill."""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import re
import urllib.request
from decimal import Decimal
from pathlib import Path

from .persistence import atomic_write_json
from .settings import APP_DIR

SOURCE_URL = "https://developers.openai.com/api/docs/pricing.md"
PUBLIC_URL = "https://developers.openai.com/api/docs/pricing"
PRICING_DIR = APP_DIR / "pricing"


def fingerprint(text: str) -> str:
    # Ignore presentation whitespace, but retain prose (including pricing terms).
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def parse_prices(text: str) -> dict:
    """Fail closed if the official Standard table's schema changes."""
    if "Short context: ≤272K input tokens. Long context: >272K input tokens." not in text:
        raise ValueError("Context pricing rule changed or is missing; update the pricing source/parser.")
    section = text.split("### Standard pricing data", 1)
    if len(section) != 2:
        raise ValueError("Official Standard pricing table was not found; update the pricing source/parser.")
    section = section[1].split("### ", 1)[0]
    prices = {}
    header = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [v.strip() for v in line.strip().strip("|").split("|")]
        if cells[0] == "Model":
            header = cells
            continue
        if not cells[0].startswith(("gpt-", "o1", "o3", "o4")):
            continue
        if len(cells) != len(header):
            raise ValueError("Pricing table column count changed; review the official source.")
        row = dict(zip(header, cells))
        model = cells[0].split(" (")[0]
        def rate(name):
            value = row.get(name)
            if value == "-":
                return None
            if not value or not re.fullmatch(r"\$[0-9]+(?:\.[0-9]+)?", value):
                raise ValueError(f"Unrecognized price for {model}: {name}")
            return value[1:]
        def group(prefix):
            return [rate(prefix + "input"), rate(prefix + "cached input"), rate(prefix + "output")]
        if "Short context input" in header:
            prices[model] = {"short": group("Short context "), "long": group("Long context "), "threshold": 272000}
        elif header == ["Model", "Input", "Output", "Cached input"]:
            prices[model] = {"short": [rate("Input"), rate("Cached input"), rate("Output")]}
        else:
            raise ValueError("Pricing table schema changed; update the pricing source/parser.")
    if not {"gpt-6-astra", "gpt-6.1-sol"}.issubset(prices):
        raise ValueError("Official pricing response is incomplete.")
    return prices


class PricingStore:
    def __init__(self, root: Path = PRICING_DIR):
        self.root = root

    def revisions(self):
        from .pricing_seed import SEED
        revisions = [SEED]
        if self.root.exists():
            for path in sorted(self.root.glob("revision-*.json")):
                revisions.append(json.loads(path.read_text(encoding="utf-8")))
        return sorted(revisions, key=lambda r: r["effective_from"])

    def status(self):
        try:
            state = json.loads((self.root / "status.json").read_text(encoding="utf-8"))
            if state.get("state") == "changed":
                state["message"] = ("OpenAI updated its pricing webpage. This may be a text change, not a price change. "
                                    "Your cost estimates still use your saved rates. "
                                    "Use Review pricing change to see what differs and decide whether to accept it.")
            return state
        except (OSError, ValueError):
            return {"state": "unchecked", "message": "Pricing source has not been checked yet."}

    def check(self, *, force=False, fetch=None, now=None):
        now = now or dt.datetime.now(dt.timezone.utc)
        previous = self.status()
        if not force and now.timestamp() - previous.get("checked_at", 0) < 86400:
            return previous
        try:
            if fetch is None:
                request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "CodexMeter pricing-check/1"})
                with urllib.request.urlopen(request, timeout=15) as response:
                    if not response.url.startswith("https://developers.openai.com/"):
                        raise ValueError("Pricing source redirected outside official documentation.")
                    raw = response.read(2_000_001)
                    if len(raw) > 2_000_000:
                        raise ValueError("Pricing source is unexpectedly large.")
                    text = raw.decode("utf-8")
            else:
                text = fetch()
            digest = fingerprint(text)
            latest = self.revisions()[-1]
            candidate = {"source": SOURCE_URL, "source_sha256": digest,
                         "observed_at": now.isoformat(), "prices": parse_prices(text)}
            changed = digest != latest["source_sha256"]
            if changed:
                atomic_write_json(self.root / "pending.json", candidate)
            status = {"state": "changed" if changed else "current", "checked_at": now.timestamp(),
                      "source_sha256": digest, "active_revision": latest["effective_from"],
                      "message": ("OpenAI updated its pricing webpage. Your cost estimates still use your saved rates. Open the control panel and choose Review pricing change to see whether prices differ."
                                  if changed else "Official pricing source matches the saved rates.")}
        except Exception as exc:
            status = {**previous, "state": "error", "checked_at": now.timestamp(),
                      "message": f"Pricing check failed; saved rates retained. {exc}"}
        atomic_write_json(self.root / "status.json", status)
        return status

    def accept_pending(self, expected_hash: str, now=None):
        """Called only after the user reviews the exact candidate in the control panel."""
        now = now or dt.datetime.now(dt.timezone.utc)
        pending = json.loads((self.root / "pending.json").read_text(encoding="utf-8"))
        if pending["source_sha256"] != expected_hash or self.status().get("state") != "changed":
            raise ValueError("Pricing candidate changed; check and review it again.")
        pending["effective_from"] = now.isoformat()
        # Append-only revisions: accepting new rates never rewrites previous dates.
        name = "revision-" + now.strftime("%Y%m%dT%H%M%S%fZ") + ".json"
        atomic_write_json(self.root / name, pending)
        atomic_write_json(self.root / "status.json", {
            "state": "current", "checked_at": now.timestamp(), "source_sha256": expected_hash,
            "active_revision": pending["effective_from"], "message": "Reviewed rates saved; previous pricing history retained."})
        return pending

    def review_summary(self):
        """Read-only explanation for notification clicks, including stale balloons."""
        state = self.status()
        if state.get("state") == "current":
            return "The pricing source is up to date. No review is pending. Earlier pricing history is retained."
        if state.get("state") != "changed":
            return state.get("message", "Pricing source has not been checked yet.") + "\n\nA failed check does not establish that prices changed. Saved rates remain in use."
        explanation = ("OpenAI's pricing page changed. This does not necessarily mean the actual rates changed.\n\n"
                       "Compare the rates with your saved pricing history and review the official page for changes to terms.")
        try:
            pending = json.loads((self.root / "pending.json").read_text(encoding="utf-8"))
            if pending["source_sha256"] != state.get("source_sha256"):
                raise ValueError("Candidate changed")
            previous = self.revisions()[-1]
            old, new = previous["prices"], pending["prices"]
            changes = [m for m in sorted(old.keys() | new.keys()) if old.get(m) != new.get(m)]
            comparison = (f"Tracked rate entries differ for {len(changes)} model(s): " + ", ".join(changes)
                          if changes else "No tracked Standard token rates differ from the last accepted revision.")
            explanation += "\n\n" + comparison + "\nCompared with revision: " + previous["effective_from"]
        except (OSError, ValueError, KeyError, TypeError):
            explanation += "\n\nThe pending comparison is unavailable. Check the source again before reviewing."
        return explanation + "\n\nSaved rates remain active until you accept a reviewed update. Acceptance adds a dated revision; earlier history is preserved."

    def cost(self, record: dict, revisions=None):
        revisions = revisions or self.revisions()
        eligible = [r for r in revisions if dt.datetime.fromisoformat(r["effective_from"]) <= record["time"]]
        if not eligible:
            return None, "No historical price"
        model = record.get("model") or "Unknown model"
        prices = eligible[-1]["prices"]
        price = prices.get(model)
        # Only explicitly dated snapshots of a documented model inherit its rate.
        if price is None:
            price = prices.get(re.sub(r"-20\d\d-\d\d-\d\d$", "", model))
        if price is None:
            return None, "Unpriced model"
        if record.get("cache_write", 0):
            return None, "Cache-write retention unavailable"
        tier = "long" if record["input"] > price.get("threshold", 10**30) else "short"
        rates = price.get(tier)
        tokens = record["tokens"]
        if not rates or any(n and rate is None for n, rate in zip(tokens, rates)):
            return None, "Unpriced token category"
        # USD per million * tokens = microdollars. Keep Decimal until aggregation.
        return [Decimal(str(rate or 0)) * n for n, rate in zip(tokens, rates)], None


async def pricing_monitor_loop(stop_event, desktop=None):
    store = PricingStore()
    notified = None
    while not stop_event.is_set():
        try:
            status = await asyncio.to_thread(store.check)
            signature = (status.get("state"), status.get("source_sha256"))
            if status["state"] in ("changed", "error") and signature != notified:
                if desktop is not None:
                    desktop.commands.put(("pricing_warning", status["message"]))
                notified = signature
        except Exception:
            import logging
            logging.exception("Pricing monitor unavailable; usage bridge continues")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600)
        except asyncio.TimeoutError:
            pass
