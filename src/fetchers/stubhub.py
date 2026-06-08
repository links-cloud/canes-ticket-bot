from __future__ import annotations
"""StubHub fetcher (best-effort).

StubHub has no public API for individual users. We hit the same internal
JSON endpoint their event page uses to fetch listings. This works today but
can break without notice — if you start getting empty results, the endpoint
or query params likely changed.

Strategy:
1. Search for the event by team + date via /search
2. Pull listings for that event id, then return the cheapest per section.
"""
import os
from typing import List
import requests

from .base import Listing, classify_level


SEARCH_URL = "https://www.stubhub.com/search/catalog/events"
LISTINGS_URL_TMPL = "https://www.stubhub.com/inventory/listings"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _find_event_id(team: str, date_iso: str) -> str | None:
    params = {"q": team, "from": date_iso, "to": date_iso}
    try:
        r = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[stubhub] search failed: {e}")
        return None
    events = (data.get("events") or data.get("items") or [])
    if not events:
        return None
    return str(events[0].get("id") or events[0].get("eventId") or "") or None


def fetch_stubhub(team: str, date_iso: str, venue_city: str, game_id: str,
                  lower_prefixes, upper_prefixes) -> List[Listing]:
    if os.environ.get("STUBHUB_DISABLE"):
        print("[stubhub] disabled via STUBHUB_DISABLE")
        return []

    event_id = os.environ.get(f"STUBHUB_EVENT_{game_id.upper()}") or _find_event_id(team, date_iso)
    if not event_id:
        print(f"[stubhub] could not resolve event id for {date_iso}")
        return []

    params = {"eventId": event_id, "quantity": 1}
    try:
        r = requests.get(LISTINGS_URL_TMPL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[stubhub] listings fetch failed: {e}")
        return []

    raw_listings = data.get("listings") or data.get("Items") or []
    out: List[Listing] = []
    for lst in raw_listings:
        section = str(lst.get("section") or lst.get("sectionName") or "")
        price = lst.get("currentPrice") or lst.get("price") or {}
        if isinstance(price, dict):
            price_val = price.get("amount") or price.get("value")
        else:
            price_val = price
        if not section or price_val is None:
            continue
        out.append(Listing(
            site="stubhub",
            game_id=game_id,
            section=section,
            row=lst.get("row"),
            price=float(price_val),
            quantity=int(lst.get("quantity") or 1),
            url=f"https://www.stubhub.com/event/{event_id}",
            level=classify_level(section, lower_prefixes, upper_prefixes),
        ))
    if not out:
        print(f"[stubhub] 0 listings parsed (endpoint may have changed)")
    return out
