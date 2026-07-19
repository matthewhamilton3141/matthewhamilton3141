#!/usr/bin/env python3
"""Render a gold 'Rayquaza' snake that weaves through the empty cells of the
last ~10 weeks of contributions, dodging lit (contribution) tiles.

The lit tiles are treated as obstacles: the snake only travels through empty
cells. The route is a DFS Euler tour of the largest empty-cell component, so it
starts and ends on the same cell -> the animation loops seamlessly.

Environment:
  GH_USER   GitHub login
  GH_TOKEN  token with GraphQL read access (Actions GITHUB_TOKEN works)
"""
import datetime
import json
import os
import sys
import urllib.request

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]

WEEKS = 10          # ~2 months of columns
CELL = 20           # tile size
GAP = 6             # gap between tiles
PITCH = CELL + GAP
MX = 24             # left/right margin
MY = 24             # top/bottom margin

BG = "#0d1117"
EMPTY = "#161b22"
GREENS = ["#0e4429", "#006d32", "#26a641", "#39d353"]  # low -> high
HEAD = "#f8d13a"    # bright shiny gold
TAIL = "#6b4e00"    # dark gold
NSEG = 15           # snake body segments


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


def fetch_grid():
    now = datetime.datetime.utcnow()
    frm = (now - datetime.timedelta(days=WEEKS * 7 + 7)).strftime("%Y-%m-%dT00:00:00Z")
    to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    q = (
        "query($login:String!,$from:DateTime!,$to:DateTime!){"
        "user(login:$login){contributionsCollection(from:$from,to:$to){"
        "contributionCalendar{weeks{contributionDays{weekday contributionCount}}}}}}"
    )
    data = gql(q, {"login": USER, "from": frm, "to": to})
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    weeks = weeks[-WEEKS:]
    cells = {}  # (row, col) -> contributionCount, only for real days
    for c, week in enumerate(weeks):
        for day in week["contributionDays"]:
            cells[(day["weekday"], c)] = day["contributionCount"]
    return cells, len(weeks)


def euler_tour(free):
    free_set = set(free)

    def neighbors(cell):
        r, c = cell
        for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            n = (r + dr, c + dc)
            if n in free_set:
                yield n

    # largest connected component of empty cells
    seen, comps = set(), []
    for cell in free_set:
        if cell in seen:
            continue
        stack, comp = [cell], []
        seen.add(cell)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in neighbors(u):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        comps.append(comp)
    if not comps:
        return []
    comp = set(max(comps, key=len))
    start = min(comp)

    def comp_neighbors(cell):
        for v in neighbors(cell):
            if v in comp:
                yield v

    sys.setrecursionlimit(10000)
    visited, tour = set(), []

    def dfs(u):
        visited.add(u)
        tour.append(u)
        for v in comp_neighbors(u):
            if v not in visited:
                dfs(v)
                tour.append(u)  # backtrack keeps consecutive cells adjacent

    dfs(start)
    return tour


def lerp(a, b, t):
    ai = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    bi = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(ai[i] + (bi[i] - ai[i]) * t) for i in range(3))


def green(count):
    if count >= 10:
        return GREENS[3]
    if count >= 6:
        return GREENS[2]
    if count >= 3:
        return GREENS[1]
    return GREENS[0]


def cx(c):
    return MX + c * PITCH + CELL / 2


def cy(r):
    return MY + r * PITCH + CELL / 2


def build_svg(cells, cols):
    width = 2 * MX + cols * CELL + (cols - 1) * GAP
    height = 2 * MY + 7 * CELL + 6 * GAP

    free = [cell for cell, n in cells.items() if n == 0]
    tour = euler_tour(free)

    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'role="img" aria-label="Contribution snake">',
        f'<rect width="{width}" height="{height}" rx="8" fill="{BG}"/>',
    ]

    # tiles
    for (r, c), n in cells.items():
        x = MX + c * PITCH
        y = MY + r * PITCH
        fill = green(n) if n > 0 else EMPTY
        parts.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="4" fill="{fill}"/>'
        )

    if len(tour) >= 2:
        pts = [(cx(c), cy(r)) for (r, c) in tour]
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        seg_len = (len(tour) - 1) * PITCH
        dur = max(4.0, round(len(tour) * 0.09, 2))
        parts.append(f'<path id="snakepath" d="{d}" fill="none" stroke="none"/>')

        spacing_frac = (0.5 * PITCH) / seg_len
        # head last so it draws on top
        for i in range(NSEG - 1, -1, -1):
            t = i / max(NSEG - 1, 1)
            color = lerp(HEAD, TAIL, t)
            radius = 9 - 4 * t
            begin = round((i * spacing_frac - 1) * dur, 3)
            if i == 0:
                parts.append(
                    f'<g><circle r="{radius:.1f}" fill="{color}"/>'
                    f'<circle cx="3" cy="-3" r="1.5" fill="#0d1117"/>'
                    f'<circle cx="3" cy="3" r="1.5" fill="#0d1117"/>'
                    f'<animateMotion dur="{dur}s" begin="{begin}s" repeatCount="indefinite" rotate="auto">'
                    f'<mpath xlink:href="#snakepath" href="#snakepath"/></animateMotion></g>'
                )
            else:
                parts.append(
                    f'<circle r="{radius:.1f}" fill="{color}">'
                    f'<animateMotion dur="{dur}s" begin="{begin}s" repeatCount="indefinite">'
                    f'<mpath xlink:href="#snakepath" href="#snakepath"/></animateMotion></circle>'
                )

    parts.append("</svg>\n")
    return "\n".join(parts)


def main():
    cells, cols = fetch_grid()
    svg = build_svg(cells, cols)
    with open("github-snake.svg", "w") as fh:
        fh.write(svg)
    lit = sum(1 for n in cells.values() if n > 0)
    print(f"cols={cols} cells={len(cells)} lit={lit}")


if __name__ == "__main__":
    main()
