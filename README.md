# Canes Ticket Bot

Monitors single-ticket prices for Carolina Hurricanes home games across
SeatGeek, Ticketmaster, StubHub, and Vivid Seats. Sends an SMS via Twilio
when the cheapest listing drops below a per-level threshold.

Runs locally on macOS via launchd every 15 minutes. GitHub Actions
disabled for the schedule (kept for manual runs only) because Ticketmaster's
Akamai bot protection blocks GH Actions datacenter IPs. Residential IP from
the home Mac sails through.

## How it works

1. `src/main.py` loads `config.yaml` (games + thresholds).
2. For each game, calls each site fetcher in `src/fetchers/`.
3. Picks the cheapest listing per `(site, level)`.
4. Compares against the per-game threshold (`lower` vs `upper`).
5. Sends a Twilio SMS if below threshold AND we haven't already alerted at
   that price or lower (dedupe via `state/last_alert.json`, committed back
   to the repo after each run).

`level` is derived from section number using `config.yaml`:
- Sections starting with `1` → lower bowl
- Sections starting with `3` → upper bowl
- Anything else → `unknown`, treated conservatively (uses lower threshold)

SeatGeek and Ticketmaster only return an aggregate "lowest_price" via their
free APIs, so listings from those sites come back as level `unknown` and
only trigger if they're below the lower-bowl threshold. StubHub and Vivid
Seats give us per-section data so we can apply upper/lower correctly.

## Setup

### 1. Local test (dry run, no real SMS)

```bash
cd /Users/rk/projects/canes-ticket-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DRY_RUN=1 python -m src.main
```

You should see per-site output even with no API keys (the fetchers will
print why they skipped). Add `SEATGEEK_CLIENT_ID=xxx` and
`TICKETMASTER_API_KEY=xxx` as env vars to exercise those.

### 2. Pushover

We use Pushover instead of SMS — US carrier A2P 10DLC filtering silently
drops Twilio long-code SMS to unregistered senders, and registration takes
1–2 weeks. Pushover delivers a mobile push notification (visually similar
to a text) and works immediately.

1. Sign up free at https://pushover.net.
2. Install the Pushover app on your phone ($5 one-time, lifetime use).
3. From the dashboard, copy your **User Key** (looks like a 30-char alnum).
4. Click "Create an Application/API Token", name it `canes-ticket-bot`,
   submit, copy the **API Token/Key**.

### 3. SeatGeek API key

Free at https://seatgeek.com/account/develop — you only need the
**Client ID** (we don't need the secret).

### 4. Ticketmaster API key

Free at https://developer-acct.ticketmaster.com/user/login — create a new
app and copy the **Consumer Key**. This is your `TICKETMASTER_API_KEY`.

### 5. Local launchd setup (active execution mode)

```bash
cd /Users/rk/projects/canes-ticket-bot
# .env with secrets (chmod 600):
cat > .env <<'EOF'
TICKETMASTER_API_KEY=...
PUSHOVER_APP_TOKEN=...
PUSHOVER_USER_KEY=...
EOF
chmod 600 .env

# Install the LaunchAgent
cp scripts/com.linkscloud.canes-bot.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.linkscloud.canes-bot.plist

# Check status
launchctl print gui/$(id -u)/com.linkscloud.canes-bot | grep -E "state|last exit"

# Tail logs
tail -f logs/bot.log
```

To stop: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.linkscloud.canes-bot.plist`

### 6. GitHub repo + secrets (manual-trigger mode only)

```bash
cd /Users/rk/projects/canes-ticket-bot
git add -A
git commit -m "Initial commit"
gh repo create canes-ticket-bot --private --source=. --remote=origin --push
```

Then add these secrets (Settings → Secrets and variables → Actions):

| Name | Value |
|---|---|
| `SEATGEEK_CLIENT_ID` | from step 3 |
| `TICKETMASTER_API_KEY` | from step 4 |
| `PUSHOVER_APP_TOKEN` | from step 2 |
| `PUSHOVER_USER_KEY` | from step 2 |

Or via `gh`:

```bash
gh secret set SEATGEEK_CLIENT_ID
gh secret set TICKETMASTER_API_KEY
gh secret set PUSHOVER_APP_TOKEN
gh secret set PUSHOVER_USER_KEY
```

### 6. Trigger a test run

Once secrets are set, go to **Actions → Check ticket prices → Run workflow**
to fire it once on demand. Then watch the logs.

To force an SMS for verification, temporarily set absurdly-high thresholds
in `config.yaml` (e.g. `lower: 10000`), commit, and run the workflow once.
Don't forget to revert.

## What each active fetcher gives us

- **SeatGeek** — aggregate cheapest *resale* price across many marketplaces.
  Returns a price as level `unknown` (no section detail from the free API),
  which the threshold logic treats conservatively (uses lower-bowl threshold).
- **Ticketmaster** — *primary* inventory only. Currently returns nothing
  (`no primary inventory yet`) because SCF games are sold out on the primary
  market. The moment TM releases more inventory, prices populate and we alert.

## Caveats

- **StubHub & Vivid Seats are disabled.** Their internal JSON endpoints
  aren't stable and rotate without notice. Files exist in `src/fetchers/`
  but aren't registered in `ALL_FETCHERS`.
- **Ticketmaster HTML scraping is not used.** Their public event pages
  return 401 to non-browser clients (Akamai bot detection). Would need a
  headless browser to bypass.
- **GitHub Actions cron** is best-effort. Scheduled runs can be delayed
  several minutes during peak load — fine for ticket monitoring but don't
  expect second-level precision.
- The repo commits state back to itself on every run that sees price
  changes. If you fork or rebase, that history will look noisy.
