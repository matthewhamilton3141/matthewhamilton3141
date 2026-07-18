#!/usr/bin/env python3
"""Generate a green-themed GitHub stats SVG.

Queries the authenticated user's public contribution calendar via the GitHub
GraphQL API and renders three panels:
  Total Contributions | Current Streak | Most Commits in a Day

Environment:
  GH_USER   GitHub login to report on
  GH_TOKEN  token with GraphQL read access (the Actions GITHUB_TOKEN works)
"""
import datetime
import json
import os
import urllib.request

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]

BG = "#0D1117"
ACCENT = "#76B900"
NUM = "#FFFFFF"
DIVIDER = "#21262D"


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": USER,
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def collect_days():
    created = gql(
        "query($login:String!){user(login:$login){createdAt}}", {"login": USER}
    )
    start_year = int(created["user"]["createdAt"][:4])
    now = datetime.datetime.utcnow()

    days = {}
    for year in range(start_year, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = (
            now.strftime("%Y-%m-%dT%H:%M:%SZ")
            if year == now.year
            else f"{year}-12-31T23:59:59Z"
        )
        q = (
            "query($login:String!,$from:DateTime!,$to:DateTime!){"
            "user(login:$login){contributionsCollection(from:$from,to:$to){"
            "contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"
        )
        data = gql(q, {"login": USER, "from": frm, "to": to})
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for day in week["contributionDays"]:
                days[day["date"]] = day["contributionCount"]
    return days


def compute(days):
    total = sum(days.values())
    most = max(days.values()) if days else 0

    today = datetime.date.today()
    cursor = today
    # Today counting as zero-so-far shouldn't break an active streak.
    if days.get(today.isoformat(), 0) == 0:
        cursor = today - datetime.timedelta(days=1)
    streak = 0
    while days.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    return total, streak, most


def build_svg(total, streak, most):
    return f"""<svg width="495" height="195" viewBox="0 0 495 195" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub stats">
  <style>
    .num {{ font: 700 30px 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; fill: {NUM}; }}
    .label {{ font: 400 13px 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; fill: {ACCENT}; }}
    text {{ text-anchor: middle; }}
  </style>
  <rect x="0.5" y="0.5" rx="6" width="494" height="194" fill="{BG}"/>
  <line x1="165" y1="45" x2="165" y2="150" stroke="{DIVIDER}" stroke-width="1"/>
  <line x1="330" y1="45" x2="330" y2="150" stroke="{DIVIDER}" stroke-width="1"/>
  <text class="num" x="82.5" y="98">{total}</text>
  <text class="label" x="82.5" y="128">Total Contributions</text>
  <circle cx="247.5" cy="88" r="40" fill="none" stroke="{ACCENT}" stroke-width="4"/>
  <text class="num" x="247.5" y="98">{streak}</text>
  <text class="label" x="247.5" y="150">Current Streak</text>
  <text class="num" x="412.5" y="98">{most}</text>
  <text class="label" x="412.5" y="128">Most Commits in a Day</text>
</svg>
"""


def main():
    days = collect_days()
    total, streak, most = compute(days)
    svg = build_svg(total, streak, most)
    with open("github-stats.svg", "w") as fh:
        fh.write(svg)
    print(f"total={total} streak={streak} most={most}")


if __name__ == "__main__":
    main()
