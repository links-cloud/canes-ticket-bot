from __future__ import annotations
import os
import requests


PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def send_alert(title: str, body: str, url: str | None = None) -> None:
    token = os.environ.get("PUSHOVER_APP_TOKEN")
    user = os.environ.get("PUSHOVER_USER_KEY")
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

    if dry_run or not (token and user):
        prefix = "[DRY RUN] " if dry_run else "[NO PUSHOVER CREDS] "
        print(f"{prefix}Would push:\n  title: {title}\n  body: {body}\n  url: {url}")
        return

    data = {
        "token": token,
        "user": user,
        "title": title,
        "message": body,
        "priority": 1,        # bypass quiet hours, force notification
        "sound": "cashregister",
    }
    if url:
        data["url"] = url
        data["url_title"] = "Open listing"

    try:
        r = requests.post(PUSHOVER_URL, data=data, timeout=15)
        r.raise_for_status()
        resp = r.json()
    except requests.RequestException as e:
        print(f"[pushover] send failed: {e}")
        return
    if resp.get("status") != 1:
        print(f"[pushover] non-success response: {resp}")
        return
    print(f"Pushover sent, receipt={resp.get('receipt', '-')}")


def format_alert(game_label: str, site: str, level: str, price: float,
                 threshold: float, section: str, url: str | None) -> tuple[str, str, str | None]:
    title = f"🏒 {game_label} — ${price:.0f}"
    body_lines = [
        f"{site}: ${price:.0f} ({level}, sec {section})",
        f"threshold ${threshold:.0f}",
    ]
    body = "\n".join(body_lines)
    return title, body, url
