#!/usr/bin/env bash
# Wrapper to run the ticket bot under launchd.
# Loads secrets from .env (kept out of git) and runs the checker.

set -euo pipefail

cd "$(dirname "$0")"

# Load env file. The `set -a` exports everything that follows.
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# Use venv python; install browsers on first run.
if [[ ! -d .venv ]]; then
    /usr/bin/python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
if [[ ! -d "$HOME/Library/Caches/ms-playwright" ]]; then
    .venv/bin/python -m playwright install chromium
fi

exec .venv/bin/python -m src.main
