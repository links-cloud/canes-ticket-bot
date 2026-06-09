from __future__ import annotations
"""Ticketmaster fetcher: Discovery API for event ID lookup, then Playwright
to scrape live prices.

The Discovery API (priceRanges field) doesn't return prices for sold-out
playoff events even when those events have active inventory (verified
2026-06-09 on SCF Game 5). We have to load the real event page in a real
browser to evade Akamai's bot protection and read what's actually for sale.

The page makes an XHR to /ismds/event/{id}/facets?by=shape&q=available&show=listpricerange
that returns one entry per section with min/max price + count. The page DOM
maps section IDs (s_NNN) to human-readable section names — we extract both
and join them.
"""
import asyncio
import os
import re
from typing import List

import requests

from .base import Listing, classify_level


DISCOVERY = "https://app.ticketmaster.com/discovery/v2/events.json"


def fetch_ticketmaster(team: str, date_iso: str, venue_city: str, game_id: str,
                       lower_prefixes, upper_prefixes) -> List[Listing]:
    api_key = os.environ.get("TICKETMASTER_API_KEY")
    if not api_key:
        print("[ticketmaster] TICKETMASTER_API_KEY not set, skipping")
        return []

    # 1. Resolve event ID + URL via Discovery API.
    try:
        r = requests.get(DISCOVERY, params={
            "apikey": api_key,
            "keyword": team,
            "city": venue_city,
            "size": 20,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"[ticketmaster] discovery request failed: {e}")
        return []

    all_events = (data.get("_embedded") or {}).get("events", [])
    events = [
        e for e in all_events
        if ((e.get("dates") or {}).get("start") or {}).get("localDate") == date_iso
    ]
    if not events:
        print(f"[ticketmaster] no event found for {date_iso}")
        return []

    event = events[0]
    event_id = event.get("id")
    event_url = event.get("url")
    if not (event_id and event_url):
        print(f"[ticketmaster] event missing id or url: {event}")
        return []

    # Discovery API's event ID differs from the website's internal ID used by
    # the offeradapter facets endpoint. Extract the internal ID from the URL.
    m = re.search(r"/event/([A-F0-9]+)(?:[/?#]|$)", event_url)
    internal_id = m.group(1) if m else event_id
    if internal_id != event_id:
        print(f"[ticketmaster] using internal id {internal_id} (discovery: {event_id})")

    # 2. Scrape the event page with Playwright to get live availability.
    try:
        return asyncio.run(_scrape(internal_id, event_url, game_id,
                                   lower_prefixes, upper_prefixes))
    except Exception as e:  # noqa: BLE001
        print(f"[ticketmaster] playwright scrape failed: {e}")
        return []


async def _scrape(event_id: str, event_url: str, game_id: str,
                  lower_prefixes, upper_prefixes) -> List[Listing]:
    from playwright.async_api import async_playwright

    facets_data = {"facets": []}
    html = ""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1400, "height": 900},
            )
            page = await context.new_page()

            # Collect matching responses synchronously; read their JSON
            # AFTER the page settles but BEFORE we close the browser.
            captured: list = []
            facets_urls_seen: list = []

            def on_response(resp):
                u = resp.url
                if "/ismds/event/" in u and "facets" in u:
                    facets_urls_seen.append(u)
                if (f"/ismds/event/{event_id}/facets" in u
                        and "by=shape" in u
                        and "show=listpricerange" in u):
                    captured.append(resp)

            page.on("response", on_response)
            await page.goto(event_url, wait_until="domcontentloaded", timeout=60000)
            # Let the listings panel + facets load.
            await asyncio.sleep(10)
            title = await page.title()
            html = await page.content()
            print(f"[ticketmaster] DIAG page title: {title!r}")
            print(f"[ticketmaster] DIAG html length: {len(html)}")
            print(f"[ticketmaster] DIAG facets URLs seen: {len(facets_urls_seen)}, matched: {len(captured)}")
            for u in facets_urls_seen[:3]:
                print(f"[ticketmaster] DIAG seen: {u[:180]}")

            for resp in captured:
                try:
                    body = await resp.json()
                except Exception:
                    continue
                if body.get("facets"):
                    facets_data = body
                    break
        finally:
            await browser.close()

    # Build section_id -> human section name map from DOM.
    section_names = {}
    for m in re.finditer(
        r'data-section-id="(s_\d+)"\s+data-section-name="([^"]*)"', html
    ):
        section_names[m.group(1)] = m.group(2)

    listings: List[Listing] = []
    for facet in facets_data.get("facets", []) or []:
        shapes = facet.get("shapes") or []
        if not shapes:
            continue
        price_range = facet.get("listPriceRange") or []
        if not price_range:
            continue
        min_p = price_range[0].get("min")
        if min_p is None:
            continue

        section_id = shapes[0]
        full_name = section_names.get(section_id, section_id)
        # Some section names embed marketing copy after a hyphen
        # ("228 CLUB LEDGE - Premium area that bundles..."). Trim to the
        # first ~80 chars so SMS-style alerts stay legible.
        short_name = (full_name.split(" - ", 1)[0]
                      if " - " in full_name and "Standing Room" not in full_name
                      else full_name)[:80]

        is_sro = "Standing Room" in full_name
        level = "sro" if is_sro else classify_level(short_name, lower_prefixes, upper_prefixes)

        listings.append(Listing(
            site="ticketmaster",
            game_id=game_id,
            section=short_name,
            row=None,
            price=float(min_p),
            quantity=int(facet.get("count") or 1),
            url=event_url,
            level=level,
        ))

    if not listings:
        print(f"[ticketmaster] page loaded but no available facets parsed for {event_id}")
    else:
        print(f"[ticketmaster] {len(listings)} available facets for {event_id}")
    return listings
