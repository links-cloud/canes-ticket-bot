from .seatgeek import fetch_seatgeek
from .ticketmaster import fetch_ticketmaster

# Active fetchers. StubHub and Vivid Seats are disabled (no public API,
# internal endpoints not reachable without per-event session). To re-enable,
# fix the fetcher and add to ALL_FETCHERS.
#
# SeatGeek = aggregate cheapest resale price across many marketplaces.
# Ticketmaster = primary inventory only. priceRanges is null when nothing's
#   on sale via TM (sold out / resale-only). When TM releases more primary
#   inventory closer to the game, prices will appear and we'll alert.
ALL_FETCHERS = [
    ("seatgeek", fetch_seatgeek),
    ("ticketmaster", fetch_ticketmaster),
]
