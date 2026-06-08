from __future__ import annotations
"""Vivid Seats fetcher (best-effort).

Vivid Seats also has no public API. We use their internal JSON listings
endpoint that their event page calls. Like StubHub, brittle to changes.
"""
import os
from typing import List
import requests

from .base import Listing, classify_level


SEARCH_URL = "https://www.vividseats.com/hermes/api/v1/search"
LISTINGS_URL_TMPL = "https://www.vividseats.com/hermes/api/v1/listings"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _find_production_id(team: str, date_iso: str) -> str | None:
    params = {"searchTerm": team, "startDate": date_iso, "endDate": date_iso}
    try:
        r = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[vividseats] search failed: {e}")
        return None
    productions = data.get("productions") or data.get("results") or []
    if not productions:
        return None
    return str(productions[0].get("id") or productions[0].get("productionId") or "") or None


def fetch_vividseats(team: str, date_iso: str, venue_city: str, game_id: str,
                     lower_prefixes, upper_prefixes) -> List[Listing]:
    if os.environ.get("VIVIDSEATS_DISABLE"):
        print("[vividseats] disabled via VIVIDSEATS_DISABLE")
        return []

    prod_id = os.environ.get(f"VIVIDSEATS_PROD_{game_id.upper()}") or _find_production_id(team, date_iso)
    if not prod_id:
        print(f"[vividseats] could not resolve production id for {date_iso}")
        return []

    params = {"productionId": prod_id, "includeAllInPrice": "true"}
    try:
        r = requests.get(LISTINGS_URL_TMPL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[vividseats] listings fetch failed: {e}")
        return []

    raw = data.get("tickets") or data.get("listings") or []
    out: List[Listing] = []
    for t in raw:
        section = str(t.get("section") or t.get("s") or "")
        price_val = t.get("price") or t.get("p") or t.get("currentPrice")
        if isinstance(price_val, dict):
            price_val = price_val.get("amount") or price_val.get("value")
        if not section or price_val is None:
            continue
        out.append(Listing(
            site="vividseats",
            game_id=game_id,
            section=section,
            row=t.get("row") or t.get("r"),
            price=float(price_val),
            quantity=int(t.get("quantity") or t.get("q") or 1),
            url=f"https://www.vividseats.com/production/{prod_id}",
            level=classify_level(section, lower_prefixes, upper_prefixes),
        ))
    if not out:
        print(f"[vividseats] 0 listings parsed (endpoint may have changed)")
    return out
