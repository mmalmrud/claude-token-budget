#!/usr/bin/env python3
"""
Fetch Claude.ai token budget via direct API call and write to cache.

Uses browser-cookie3 to extract Chrome session cookies — no browser launch needed.
See START_HERE.md for setup instructions.

Cache structure:
  {
    "current": { remaining_cents, total_cents, used_cents, reset_date,
                 scraped_at, working_days_left, daily_token_budget },
    "months": {
      "2026-03": { "total_cents": 30000, "reset_date": "2026-04-01" },
      ...
    },
    "days": {
      "2026-03-26": { "start_used_cents": 270, "end_used_cents": 303 },
      ...
    }
  }

Usage:
    poetry run python get_token_budget.py
"""

import json
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path

import browser_cookie3
from curl_cffi import requests as cffi_requests

_HERE = Path(__file__).parent
_SETTINGS = tomllib.loads((_HERE / "settings.toml").read_text())

ORG_UUID = _SETTINGS["claude"]["org_uuid"]
ACCOUNT_UUID = _SETTINGS["claude"]["account_uuid"]
CACHE_FILE = (_HERE / _SETTINGS["cache"]["file"]).resolve()

API_URL = (
    f"https://claude.ai/api/organizations/{ORG_UUID}/overage_spend_limit"
    f"?account_uuid={ACCOUNT_UUID}"
)


def working_days_between(start: date, end: date, *, exclude_weekends: bool) -> int:
    days = 0
    d = start
    while d < end:
        if not exclude_weekends or d.weekday() < 5:
            days += 1
        d += timedelta(days=1)
    return max(days, 1)


def get_cookies() -> dict:
    jar = browser_cookie3.chrome(domain_name=".claude.ai")
    return {c.name: c.value for c in jar}


def fetch_usage() -> dict:
    cookies = get_cookies()
    if not cookies:
        print("No claude.ai cookies found in Chrome. Make sure you're logged in.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9",
        "referer": "https://claude.ai/settings/usage",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "anthropic-client-platform": "web_claude_ai",
    }

    response = cffi_requests.get(API_URL, cookies=cookies, headers=headers, impersonate="chrome")
    response.raise_for_status()
    return response.json()


def next_monthly_reset() -> str:
    today = date.today()
    reset_day = _SETTINGS["budget"]["monthly_reset_day"]
    if today.day < reset_day:
        return today.replace(day=reset_day).isoformat()
    if today.month == 12:
        return date(today.year + 1, 1, reset_day).isoformat()
    return date(today.year, today.month + 1, reset_day).isoformat()


def update_cache(api_data: dict, prev: dict) -> dict:
    total_cents: int = api_data["monthly_credit_limit"]
    used_cents: int = api_data["used_credits"]
    remaining_cents = total_cents - used_cents
    reset_date = next_monthly_reset()

    today = date.today()
    today_str = today.isoformat()
    month_str = today.strftime("%Y-%m")

    reset = date.fromisoformat(reset_date)
    days_left_all = working_days_between(today, reset, exclude_weekends=False)
    days_left_weekdays = working_days_between(today, reset, exclude_weekends=True)

    # --- current period snapshot ---
    current = {
        "remaining_cents": remaining_cents,
        "total_cents": total_cents,
        "used_cents": used_cents,
        "reset_date": reset_date,
        "scraped_at": today_str,
        "working_days_left_all": days_left_all,
        "working_days_left_weekdays": days_left_weekdays,
        "daily_token_budget": remaining_cents / days_left_all,
        "daily_token_budget_no_weekends": remaining_cents / days_left_weekdays,
    }

    # --- months: record total/reset per billing period ---
    months: dict = prev.get("months", {})
    months[month_str] = {
        "total_cents": total_cents,
        "reset_date": reset_date,
    }

    # --- days: record start/end used_cents per calendar day ---
    days: dict = prev.get("days", {})
    if today_str not in days:
        # First scrape of the day — lock in start point and daily rates
        days[today_str] = {
            "start_used_cents": used_cents,
            "end_used_cents": used_cents,
            "daily_token_budget": remaining_cents / days_left_all,
            "daily_token_budget_no_weekends": remaining_cents / days_left_weekdays,
        }
    else:
        # Subsequent scrape — update end only, daily rates stay fixed
        days[today_str]["end_used_cents"] = used_cents

    return {"current": current, "months": months, "days": days}


def main() -> None:
    prev: dict = {}
    if CACHE_FILE.exists():
        try:
            prev = json.loads(CACHE_FILE.read_text())
        except Exception:
            pass

    api_data = fetch_usage()
    cache = update_cache(api_data, prev)

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))

    print(json.dumps(cache, indent=2))
    print(f"\nCache written to {CACHE_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
