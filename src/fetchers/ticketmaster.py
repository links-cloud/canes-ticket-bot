"""Ticketmaster fetcher.

Uses the official Discovery API:
    https://developer.ticketmaster.com/

Set TICKETMASTER_API_KEY (free, from developer.ticketmaster.com).
This returns primary + verified resale prices in aggregate. Like SeatGeek,
section-level data via Discovery is limited; we use priceRanges as the
cheapest available signal.
"""
import os
from typing import List
import requests

from .base import Listing


API = "https://app.ticketmaster.com/discovery/v2/events.json"


def fetch_ticketmaster(team: str, date_iso: str, venue_city: str, game_id: str,
                       lower_prefixes, upper_prefixes) -> List[Listing]:
    api_key = os.environ.get("TICKETMASTER_API_KEY")
    if not api_key:
        print("[ticketmaster] TICKETMASTER_API_KEY not set, skipping")
        return []

    params = {
        "apikey": api_key,
        "keyword": team,
        "city": venue_city,
        "size": 20,
    }
    try:
        r = requests.get(API, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"[ticketmaster] request failed: {e}")
        return []

    all_events = (data.get("_embedded") or {}).get("events", [])
    # Filter client-side on venue-local date (Discovery's date filter is UTC).
    events = [
        e for e in all_events
        if ((e.get("dates") or {}).get("start") or {}).get("localDate") == date_iso
    ]
    if not events:
        print(f"[ticketmaster] no event found for {date_iso}")
        return []

    event = events[0]
    price_ranges = event.get("priceRanges") or []
    if not price_ranges:
        # Normal state for sold-out/resale-only events. Watch for this to
        # change when TM releases more primary inventory closer to game day.
        print(f"[ticketmaster] no primary inventory yet for event {event.get('id')}")
        return []

    listings: List[Listing] = []
    seated_min: float | None = None
    for pr in price_ranges:
        min_p = pr.get("min")
        if min_p is None:
            continue
        pr_type = str(pr.get("type") or "").lower()
        is_sro = "standing" in pr_type or "sro" in pr_type
        if is_sro:
            listings.append(Listing(
                site="ticketmaster",
                game_id=game_id,
                section="Standing Room",
                row=None,
                price=float(min_p),
                quantity=1,
                url=event.get("url"),
                level="sro",
            ))
        else:
            if seated_min is None or min_p < seated_min:
                seated_min = float(min_p)

    if seated_min is not None:
        listings.append(Listing(
            site="ticketmaster",
            game_id=game_id,
            section="(aggregate)",
            row=None,
            price=seated_min,
            quantity=1,
            url=event.get("url"),
            level="unknown",
        ))
    return listings
