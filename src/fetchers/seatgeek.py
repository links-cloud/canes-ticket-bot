"""SeatGeek fetcher.

Uses the official SeatGeek public API:
    https://platform.seatgeek.com/

You need a SEATGEEK_CLIENT_ID (free from seatgeek.com/account/develop).
The /events endpoint returns aggregated stats including lowest_price and a
deep link, but does NOT return per-listing section detail without partner
access. For our purpose (cheapest available price), the aggregate is enough
to know whether to alert; we then send the user to the deep link.

To get section-level data we'd need the SeatGeek partner feed (paid).
"""
import os
from typing import List
import requests

from .base import Listing


API = "https://api.seatgeek.com/2/events"


def fetch_seatgeek(team: str, date_iso: str, venue_city: str, game_id: str,
                   lower_prefixes, upper_prefixes) -> List[Listing]:
    client_id = os.environ.get("SEATGEEK_CLIENT_ID")
    if not client_id:
        print("[seatgeek] SEATGEEK_CLIENT_ID not set, skipping")
        return []

    params = {
        "client_id": client_id,
        "performers.slug": "carolina-hurricanes",
        "datetime_local.gte": f"{date_iso}T00:00:00",
        "datetime_local.lte": f"{date_iso}T23:59:59",
        "venue.city": venue_city,
        "per_page": 5,
    }
    try:
        r = requests.get(API, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"[seatgeek] request failed: {e}")
        return []

    events = data.get("events", [])
    if not events:
        print(f"[seatgeek] no event found for {date_iso}")
        return []

    event = events[0]
    stats = event.get("stats") or {}
    lowest = stats.get("lowest_price")
    if lowest is None:
        print(f"[seatgeek] no lowest_price for event {event.get('id')}")
        return []

    # SeatGeek aggregate doesn't give us section. We return one synthetic
    # listing with level="unknown" so the threshold logic treats it as
    # "alert if below the lower threshold" (the more conservative one).
    return [
        Listing(
            site="seatgeek",
            game_id=game_id,
            section="(aggregate)",
            row=None,
            price=float(lowest),
            quantity=1,
            url=event.get("url"),
            level="unknown",
        )
    ]
