"""Entry point: fetch cheapest listings per (game, site, level), compare
against per-game thresholds, send Twilio SMS for new triggers."""
import sys
from collections import defaultdict
from typing import Dict, List

from .config import load as load_config, Game
from .fetchers import ALL_FETCHERS
from .fetchers.base import Listing
from .notify import send_alert, format_alert
from .state import load as load_state, save as save_state, alert_key


def cheapest_per_level(listings: List[Listing]) -> Dict[str, Listing]:
    """For one (game, site), pick the cheapest listing per level."""
    best: Dict[str, Listing] = {}
    for lst in listings:
        cur = best.get(lst.level)
        if cur is None or lst.price < cur.price:
            best[lst.level] = lst
    return best


def threshold_for(level: str, game: Game) -> float:
    if level == "upper":
        return game.upper_threshold
    if level == "sro":
        return game.sro_threshold
    # "lower" or "unknown" -> use the lower-bowl threshold (most permissive)
    return game.lower_threshold


def run() -> int:
    cfg = load_config()
    state = load_state()
    new_state = dict(state)
    alerts_sent = 0

    for game in cfg.games:
        print(f"\n=== {game.label} ({game.date}) ===")
        for site_name, fetcher in ALL_FETCHERS:
            try:
                listings = fetcher(
                    cfg.team, game.date, cfg.venue_city, game.id,
                    cfg.lower_prefixes, cfg.upper_prefixes,
                )
            except Exception as e:  # noqa: BLE001 - per-site isolation
                print(f"[{site_name}] unhandled error: {e}")
                continue

            if not listings:
                continue

            best_by_level = cheapest_per_level(listings)
            # Iterate in a stable order so logs/alerts are deterministic.
            for level in ("upper", "lower", "sro", "unknown"):
                lst = best_by_level.get(level)
                if lst is None:
                    continue
                threshold = threshold_for(level, game)
                tag = f"{site_name} {level} sec {lst.section}"
                print(f"  {tag}: ${lst.price:.0f} (threshold ${threshold:.0f})")

                if lst.price > threshold:
                    continue

                key = alert_key(game.id, site_name, level)
                last_alerted = state.get(key)
                if (not cfg.send_repeat_alerts
                        and last_alerted is not None
                        and lst.price >= last_alerted):
                    print(f"    -> skip alert (already alerted at ${last_alerted:.0f})")
                    new_state[key] = lst.price
                    continue

                title, body, alert_url = format_alert(
                    game.label, site_name, level, lst.price,
                    threshold, lst.section, lst.url,
                )
                send_alert(title, body, alert_url)
                alerts_sent += 1
                new_state[key] = lst.price

    # Clear keys whose price went back above threshold so future drops re-alert.
    for game in cfg.games:
        for site_name, _ in ALL_FETCHERS:
            for level in ("lower", "upper", "unknown"):
                key = alert_key(game.id, site_name, level)
                if key in new_state and key not in state:
                    continue  # newly alerted, keep

    save_state(new_state)
    print(f"\nDone. {alerts_sent} alert(s) sent.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
