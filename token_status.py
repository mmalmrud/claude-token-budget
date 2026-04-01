#!/usr/bin/env python3
"""
Fast Claude.ai credit budget status for Claude Code status line.
Reads the cache written by get_token_budget.py — never hits the network.
"""

import json
import tomllib
from datetime import date
from pathlib import Path

_HERE = Path(__file__).parent
_SETTINGS = tomllib.loads((_HERE / "settings.toml").read_text())

CACHE_FILE = (_HERE / _SETTINGS["cache"]["file"]).resolve()
STALE_DAYS = _SETTINGS["cache"]["stale_days"]

GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
RESET  = "\033[0m"
ICON   = "⬡"


def fmt_dollars(cents: float) -> str:
    d = cents / 100
    if d >= 1000:
        return f"${d/1000:.1f}k"
    if d >= 10 or d == 0:
        return f"${d:.0f}"
    if d >= 1:
        return f"${d:.1f}"
    return f"${d:.2f}"


def load_cache() -> dict | None:
    try:
        raw = json.loads(CACHE_FILE.read_text())
        current = raw.get("current", {})
        scraped = date.fromisoformat(current["scraped_at"])
        if (date.today() - scraped).days > STALE_DAYS:
            return None
        return raw
    except Exception:
        return None


def color_for(remaining_today: float, daily_rate: float) -> str:
    if daily_rate == 0:
        return GREEN
    ratio = remaining_today / daily_rate
    if ratio >= 0.50:
        return GREEN
    if ratio >= 0.25:
        return YELLOW
    return RED


def main() -> None:
    cache = load_cache()
    if cache is None:
        print(f"{ICON} --")
        return

    current = cache["current"]
    today_str = date.today().isoformat()
    today_day = cache.get("days", {}).get(today_str, {})

    remaining = current["remaining_cents"]
    budget_all = today_day.get("daily_token_budget", current["daily_token_budget"])
    budget_no_weekends = today_day.get("daily_token_budget_no_weekends", current["daily_token_budget_no_weekends"])
    daily_rate = budget_no_weekends if _SETTINGS["budget"]["exclude_weekends"] else budget_all

    start_used = today_day.get("start_used_cents")
    end_used = today_day.get("end_used_cents")
    used_today = (end_used - start_used) if (start_used is not None and end_used is not None) else None
    remaining_today = (daily_rate - used_today) if used_today is not None else daily_rate

    color = color_for(remaining_today, daily_rate)

    if used_today is not None:
        spent_ratio = min(max(used_today / daily_rate, 0), 1)
        filled = round(spent_ratio * 10)
        bar = "█" * filled + "░" * (10 - filled)
        label = f"{ICON} [{bar}] {fmt_dollars(used_today)}/{fmt_dollars(daily_rate)} | {fmt_dollars(current['used_cents'])}/{fmt_dollars(current['total_cents'])}"
    else:
        label = f"{ICON} no data yet today | {fmt_dollars(current['used_cents'])}/{fmt_dollars(current['total_cents'])}"

    print(f"{color}{label}{RESET}")


def summary() -> None:
    """Print status line + full budget breakdown. Used by shell alias."""
    cache = load_cache()
    if cache is None:
        print(f"{ICON} -- (no cache)")
        return

    current = cache["current"]
    today_str = date.today().isoformat()
    today_day = cache.get("days", {}).get(today_str, {})
    start_used = today_day.get("start_used_cents", 0)
    end_used = today_day.get("end_used_cents", 0)
    used_today = end_used - start_used

    budget_all = today_day.get("daily_token_budget", current["daily_token_budget"])
    budget_no_weekends = today_day.get("daily_token_budget_no_weekends", current["daily_token_budget_no_weekends"])
    daily_rate = budget_no_weekends if _SETTINGS["budget"]["exclude_weekends"] else budget_all

    main()
    print("---")
    print(f"Used today:   ${used_today/100:.2f}")
    print(f"Month total:  ${end_used/100:.2f} of ${current['total_cents']/100:.0f}")
    print(f"Remaining:    ${current['remaining_cents']/100:.2f}")
    days_left_key = "working_days_left_weekdays" if _SETTINGS["budget"]["exclude_weekends"] else "working_days_left_all"
    print(f"Daily budget: ${daily_rate/100:.2f}  ({current[days_left_key]} working days left)")
    print(f"Resets:       {current['reset_date']}")


if __name__ == "__main__":
    import sys
    if "--summary" in sys.argv:
        summary()
    else:
        main()
