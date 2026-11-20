import json
import math
import os
import sys
import textwrap
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from html import escape

OWNER = os.environ.get("STATS_OWNER", "manit6752025")
KIND = os.environ.get("STATS_KIND", "user")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("STATS_OUT", "stats")
MEMBERS = [m.strip() for m in os.environ.get("STATS_MEMBERS", "").split(",") if m.strip()]
PROJECTS = [p.strip() for p in os.environ.get("STATS_PROJECTS", "").split(",") if p.strip()]
TITLE = os.environ.get("STATS_TITLE") or ("Manit's GitHub Stats" if KIND == "user" else OWNER + " Stats")
CACHE = os.path.join(OUT, "cache.json")
API = "https://api.github.com"
PALETTE = ["#00D4FF", "#6C3BFF", "#3FA9FF", "#9B6BFF", "#00A6A6", "#B38CFF"]
SHADES = ["#14213D", "#2a1f6b", "#4a2fb8", "#6C3BFF", "#00D4FF"]

DEFAULT = {
    "commits": 0, "stars": 0, "repos": 0, "followers": 0, "prs": 0, "merged": 0,
    "issues": 0, "forks": 0, "issues_open": 0, "total": 0,
    "current": 0, "longest": 0, "days": [0] * 30, "cal": [], "langs": [["Python", 100]],
}

PROJECT_DEFAULT = {
    "name": "project", "desc": "", "stars": 0, "forks": 0, "issues": 0,
    "release": "none", "lang": "n/a", "pushed": "", "license": "none",
}

CSS = """
text{font-family:'JetBrains Mono','Fira Code','Segoe UI',monospace}
.t{fill:#00D4FF;font-size:15px;font-weight:700}
.l{fill:#9AA0B4;font-size:11.5px}
.v{fill:#FFFFFF;font-size:14px;font-weight:700}
.big{fill:#FFFFFF;font-size:30px;font-weight:800}
.row{opacity:0;animation:in .7s ease-out forwards}
.pulse{animation:pulse 2.2s ease-in-out infinite}
.bar{transform-box:fill-box;transform-origin:left center;transform:scaleX(0);animation:grow 1.3s cubic-bezier(.2,.8,.2,1) forwards}
.spin{transform-box:fill-box;transform-origin:center;animation:spin 14s linear infinite}
.cur{animation:blink 1s steps(1) infinite}
.ring{stroke-dashoffset:var(--c);animation:ring 1.8s ease-out .4s forwards}
.lap{stroke-dasharray:30 70;animation:lap 5s linear infinite}
.scan{animation:scan 4s linear infinite}
.sw{animation:sweep 5s linear infinite}
.flame{transform-box:fill-box;transform-origin:center bottom;animation:flame 1.2s ease-in-out infinite}
.pop{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .6s cubic-bezier(.2,1.4,.4,1) forwards}
.cell{opacity:0;transform-box:fill-box;transform-origin:center;animation:cellin .5s ease-out forwards}
.draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2.5s ease-out .5s forwards}
@keyframes in{from{opacity:0;transform:translateX(-16px)}to{opacity:1;transform:translateX(0)}}
@keyframes pulse{0%,100%{opacity:.45}50%{opacity:1}}
@keyframes grow{to{transform:scaleX(1)}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}
@keyframes ring{to{stroke-dashoffset:var(--o)}}
@keyframes lap{to{stroke-dashoffset:-100}}
@keyframes scan{from{transform:translateY(-4px)}to{transform:translateY(320px)}}
@keyframes sweep{from{transform:translateX(-140px)}to{transform:translateX(900px)}}
@keyframes float{0%{transform:translateY(0);opacity:0}15%{opacity:.9}100%{transform:translateY(-260px);opacity:0}}
@keyframes flame{0%,100%{transform:scale(1,1)}50%{transform:scale(1.12,.92)}}
@keyframes pop{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:scale(1)}}
@keyframes cellin{from{opacity:0;transform:scale(.2)}to{opacity:1;transform:scale(1)}}
@keyframes draw{to{stroke-dashoffset:0}}
"""

DEFS = """<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#090A0F"/><stop offset=".6" stop-color="#14213D"/><stop offset="1" stop-color="#241466"/></linearGradient>
<linearGradient id="ac" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#00D4FF"/><stop offset="1" stop-color="#6C3BFF"/></linearGradient>
<linearGradient id="sw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".08"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<filter id="gl" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>"""


def log(e):
    print("stats warning:", e, file=sys.stderr)


def call(url, body=None):
    headers = {"User-Agent": "stats-bot", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (404, 422):
                raise
            time.sleep(2 * (attempt + 1))
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def load_cache():
    merged = dict(DEFAULT)
    try:
        with open(CACHE, encoding="utf-8") as f:
            merged.update(json.load(f))
    except Exception:
        pass
    return merged


def streaks(counts):
    longest = run = 0
    for n in counts:
        run = run + 1 if n > 0 else 0
        longest = max(longest, run)
    seq = list(counts)
    if seq and seq[-1] == 0:
        seq = seq[:-1]
    cur = 0
    for n in reversed(seq):
        if n > 0:
            cur += 1
        else:
            break
    return cur, longest


def fetch_calendar(login):
    q = "query($l:String!){user(login:$l){contributionsCollection{totalIssueContributions totalPullRequestContributions contributionCalendar{totalContributions weeks{contributionDays{contributionCount date}}}}}}"
    res = call(API + "/graphql", {"query": q, "variables": {"l": login}})
    c = res["data"]["user"]["contributionsCollection"]
    cal = c["contributionCalendar"]
    days = [[x["date"], x["contributionCount"]] for w in cal["weeks"] for x in w["contributionDays"]]
    return days, cal["totalContributions"], c["totalPullRequestContributions"], c["totalIssueContributions"]


def refresh(d):
    path = "users" if KIND == "user" else "orgs"
    try:
        info = call(f"{API}/{path}/{OWNER}")
        d["repos"] = info.get("public_repos", d["repos"])
        d["followers"] = info.get("followers", d["followers"])
    except Exception as e:
        log(e)
    repos = []
    try:
        kind_q = "owner" if KIND == "user" else "public"
        for page in range(1, 6):
            batch = call(f"{API}/{path}/{OWNER}/repos?per_page=100&page={page}&type={kind_q}")
            repos += batch
            if len(batch) < 100:
                break
        d["stars"] = sum(r.get("stargazers_count", 0) for r in repos)
        d["forks"] = sum(r.get("forks_count", 0) for r in repos)
        d["issues_open"] = sum(r.get("open_issues_count", 0) for r in repos)
    except Exception as e:
        log(e)
    counts = {}
    for r in [x for x in repos if not x.get("fork")][:30]:
        try:
            for k, v in call(r["languages_url"]).items():
                counts[k] = counts.get(k, 0) + v
        except Exception as e:
            log(e)
    if counts:
        total = sum(counts.values())
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
        d["langs"] = [[k, round(v * 100 / total, 1)] for k, v in top]
    who = f"author:{OWNER}" if KIND == "user" else f"org:{OWNER}"
    try:
        res = call(f"{API}/search/issues?q={who}+type:pr+is:merged&per_page=1")
        d["merged"] = max(d["merged"], res.get("total_count", 0))
    except Exception as e:
        log(e)
    if KIND == "user":
        try:
            res = call(f"{API}/search/commits?q=author:{OWNER}&per_page=1")
            d["commits"] = max(d["commits"], res.get("total_count", 0))
        except Exception as e:
            log(e)
        try:
            days, total, prs, issues = fetch_calendar(OWNER)
            counts_days = [n for _, n in days]
            d["cal"] = days
            d["total"] = total
            d["prs"] = prs
            d["issues"] = issues
            d["current"], d["longest"] = streaks(counts_days)
            d["days"] = counts_days[-30:]
        except Exception as e:
            log(e)
    elif MEMBERS:
        merged_days = {}
        total = 0
        for m in MEMBERS:
            try:
                days, t, _, _ = fetch_calendar(m)
                total += t
                for a, n in days:
                    merged_days[a] = merged_days.get(a, 0) + n
            except Exception as e:
                log(e)
        if merged_days:
            d["cal"] = sorted([a, n] for a, n in merged_days.items())
            d["total"] = total


def fmt(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def grade(sc):
    for g, t in (("S", 8000), ("A+", 3000), ("A", 1500), ("B+", 700), ("B", 300)):
        if sc >= t:
            return g
    return "C"


def score(d):
    if KIND == "org":
        return d["stars"] * 8 + d["forks"] * 4 + d["followers"] * 4 + d["repos"] * 10 + d["merged"] * 2
    return d["commits"] + d["stars"] * 8 + d["followers"] * 4 + d["merged"] * 3 + d["repos"] * 2


def stat_rows(d):
    if KIND == "org":
        return [("Public repos", d["repos"]), ("Stars earned", d["stars"]), ("Forks", d["forks"]),
                ("Followers", d["followers"]), ("Merged PRs", d["merged"]), ("Open issues", d["issues_open"])]
    return [("Total commits", d["commits"]), ("Stars earned", d["stars"]), ("Public repos", d["repos"]),
            ("Followers", d["followers"]), ("Merged PRs", d["merged"]), ("Issues (12 mo)", d["issues"])]


def head(text):
    x = 24 + len(text) * 9.2 + 4
    return f'<text x="24" y="34" class="t">{escape(text)}</text><rect class="cur" x="{x:.0f}" y="21" width="8" height="15" fill="#00D4FF"/>'


def frame(w, h, body):
    dots = "".join(
        f'<circle cx="{(i * 53 + 17) % w}" cy="{h - 4}" r="{1.2 + i % 3 * .6:.1f}" fill="{PALETTE[i % 2]}" style="animation:float {3 + i % 4}s linear {i * .45:.2f}s infinite"/>'
        for i in range(14)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<style>{CSS}</style>{DEFS}'
        f'<clipPath id="c"><rect width="{w}" height="{h}" rx="14"/></clipPath>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="url(#bg)"/>'
        f'<g clip-path="url(#c)">{dots}'
        f'<rect class="scan" x="0" y="0" width="{w}" height="2" fill="#00D4FF" opacity=".18"/>'
        f'<rect class="sw" x="0" y="0" width="140" height="{h}" fill="url(#sw)"/>'
        f'{body}</g>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="#6C3BFF" stroke-opacity=".4"/>'
        f'<rect class="lap" pathLength="100" x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="url(#ac)" stroke-width="2" filter="url(#gl)"/>'
        f'</svg>'
    )


def stats_svg(d):
    rows = stat_rows(d)
    top = max([v for _, v in rows] + [1])
    out = head(TITLE)
    for i, (k, v) in enumerate(rows):
        y = 66 + i * 25
        wb = max(4, 200 * math.log10(v + 1) / math.log10(top + 1))
        dl = i * .12
        out += (
            f'<g class="row" style="animation-delay:{dl:.2f}s">'
            f'<text x="24" y="{y}" class="l">{escape(k)}</text>'
            f'<text x="224" y="{y}" class="v" text-anchor="end">{fmt(v)}
