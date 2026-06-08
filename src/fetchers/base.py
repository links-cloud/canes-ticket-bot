from dataclasses import dataclass
from typing import Optional


@dataclass
class Listing:
    site: str
    game_id: str
    section: str
    row: Optional[str]
    price: float          # total per-ticket price including fees if available
    quantity: int         # smallest contiguous lot size offered
    url: Optional[str]    # deep link to the listing if we have it
    level: str            # "lower" | "upper" | "unknown"


def classify_level(section: str, lower_prefixes, upper_prefixes) -> str:
    s = section.strip().upper()
    for p in upper_prefixes:
        if s.startswith(p.upper()):
            return "upper"
    for p in lower_prefixes:
        if s.startswith(p.upper()):
            return "lower"
    return "unknown"
