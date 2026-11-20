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
            f'<text x="224" y="{y}" class="v" text-anchor="end">{fmt(v)}</text>'
            f'<rect x="24" y="{y + 5}" width="200" height="3" rx="1.5" fill="#14213D"/>'
            f'<rect class="bar" x="24" y="{y + 5}" width="{wb:.0f}" height="3" rx="1.5" fill="url(#ac)" style="animation-delay:{dl + .3:.2f}s"/>'
            f'</g>'
        )
    sc = score(d)
    frac = max(min(sc / 8000, 1), .05)
    c = 2 * math.pi * 48
    o = c * (1 - frac)
    out += (
        '<circle cx="330" cy="124" r="48" fill="none" stroke="#14213D" stroke-width="9"/>'
        f'<circle class="ring" cx="330" cy="124" r="48" fill="none" stroke="url(#ac)" stroke-width="9" stroke-linecap="round" transform="rotate(-90 330 124)" filter="url(#gl)" style="--c:{c:.1f};--o:{o:.1f};stroke-dasharray:{c:.1f}"/>'
        '<text x="330" y="112" class="l" text-anchor="middle">RANK</text>'
        f'<text x="330" y="141" class="big pulse" text-anchor="middle">{grade(sc)}</text>'
    )
    return frame(410, 220, out)


def langs_svg(d):
    langs = d["langs"]
    out = head("Most Used Languages")
    out += '<clipPath id="lb"><rect x="24" y="54" width="362" height="12" rx="6"/></clipPath>'
    out += '<rect x="24" y="54" width="362" height="12" rx="6" fill="#14213D"/><g clip-path="url(#lb)">'
    cum = 0.0
    for i, (name, pct) in enumerate(langs):
        wd = pct * 3.62
        out += f'<rect class="bar" x="{24 + cum * 3.62:.1f}" y="54" width="{wd:.1f}" height="12" fill="{PALETTE[i % 6]}" style="animation-delay:{i * .15:.2f}s"/>'
        cum += pct
    out += '</g>'
    for i, (name, pct) in enumerate(langs):
        x = 24 + (i % 2) * 185
        y = 104 + (i // 2) * 42
        out += (
            f'<g class="row" style="animation-delay:{.4 + i * .12:.2f}s">'
            f'<circle class="pulse" cx="{x + 6}" cy="{y - 4}" r="6" fill="{PALETTE[i % 6]}" style="animation-delay:{i * .3:.1f}s"/>'
            f'<text x="{x + 20}" y="{y}" class="v" style="font-size:15px">{escape(str(name))}</text>'
            f'<text x="{x + 20}" y="{y + 17}" class="l">{pct}%</text></g>'
        )
    return frame(410, 220, out)


def streak_svg(d):
    out = head("Contribution Streak")
    out += '<line x1="137" y1="56" x2="137" y2="148" stroke="#6C3BFF" stroke-opacity=".3"/><line x1="273" y1="56" x2="273" y2="148" stroke="#6C3BFF" stroke-opacity=".3"/>'
    out += (
        f'<g class="row"><text x="68" y="106" class="big" text-anchor="middle" style="font-size:26px">{fmt(d["total"])}</text>'
        '<text x="68" y="140" class="l" text-anchor="middle" style="font-size:10px">CONTRIBUTIONS</text></g>'
        f'<g class="row" style="animation-delay:.3s"><text x="342" y="106" class="big" text-anchor="middle" style="font-size:26px">{fmt(d["longest"])}</text>'
        '<text x="342" y="140" class="l" text-anchor="middle" style="font-size:10px">LONGEST STREAK</text></g>'
    )
    frac = max(min(d["current"] / max(d["longest"], 1), 1), .06)
    c = 2 * math.pi * 34
    o = c * (1 - frac)
    out += (
        '<circle cx="205" cy="96" r="34" fill="none" stroke="#14213D" stroke-width="7"/>'
        f'<circle class="ring" cx="205" cy="96" r="34" fill="none" stroke="url(#ac)" stroke-width="7" stroke-linecap="round" transform="rotate(-90 205 96)" filter="url(#gl)" style="--c:{c:.1f};--o:{o:.1f};stroke-dasharray:{c:.1f}"/>'
        '<g transform="translate(205,74) scale(.6)"><path class="flame" d="M0 -12 C6 -4 8 0 4 8 C2 12 -2 12 -4 8 C-7 3 -2 -2 0 -12Z" fill="#00D4FF" filter="url(#gl)"/></g>'
        f'<text x="205" y="110" class="big" text-anchor="middle" style="font-size:22px">{fmt(d["current"])}</text>'
        '<text x="205" y="140" class="l" text-anchor="middle" style="font-size:10px">CURRENT STREAK</text>'
    )
    days = d["days"] if len(d["days"]) > 1 else [0, 0]
    m = max(days + [1])
    step = 362 / (len(days) - 1)
    pts = " ".join(f"{24 + i * step:.1f},{206 - n / m * 30:.1f}" for i, n in enumerate(days))
    out += f'<polyline class="draw" pathLength="1" points="{pts}" fill="none" stroke="url(#ac)" stroke-width="2" stroke-linejoin="round" filter="url(#gl)"/>'
    return frame(410, 220, out)


def hexpts(cx, cy, r):
    return " ".join(
        f"{cx + r * math.cos(math.radians(60 * k - 30)):.1f},{cy + r * math.sin(math.radians(60 * k - 30)):.1f}"
        for k in range(6)
    )


def ach_svg(d):
    if KIND == "org":
        items = [("REPOS", d["repos"]), ("STARS", d["stars"]), ("FORKS", d["forks"]),
                 ("FOLLOWERS", d["followers"]), ("MERGED", d["merged"]), ("ISSUES", d["issues_open"])]
    else:
        items = [("COMMITS", d["commits"]), ("STARS", d["stars"]), ("REPOS", d["repos"]),
                 ("FOLLOWERS", d["followers"]), ("STREAK", d["longest"]), ("MERGED", d["merged"])]
    out = head("Achievements")
    for i, (label, val) in enumerate(items):
        cx = 50 + i * 62
        cy = 102
        out += (
            f'<g class="pop" style="animation-delay:{i * .15:.2f}s">'
            f'<polygon class="spin" points="{hexpts(cx, cy, 31)}" fill="none" stroke="#6C3BFF" stroke-width="1.5" stroke-dasharray="4 4"/>'
            f'<polygon points="{hexpts(cx, cy, 25)}" fill="#14213D" stroke="url(#ac)" stroke-width="2" filter="url(#gl)"/>'
            f'<text x="{cx}" y="{cy + 4}" class="v" text-anchor="middle" style="font-size:11px">{fmt(val)}</text>'
            f'<text x="{cx}" y="{cy + 52}" class="l" text-anchor="middle" style="font-size:9px">{label}</text></g>'
        )
    out += '<rect x="24" y="188" width="362" height="3" rx="1.5" fill="#14213D"/>'
    out += '<rect class="bar" x="24" y="188" width="362" height="3" rx="1.5" fill="url(#ac)" style="animation-delay:1s"/>'
    out += '<text x="205" y="208" class="l pulse" text-anchor="middle" style="font-size:10px">LIVE FROM GITHUB</text>'
    return frame(410, 220, out)


def graph_svg(d, title):
    cal = d.get("cal") or []
    if not cal:
        cal = [[date.today().isoformat(), 0]]
    parsed = [(date.fromisoformat(a), b) for a, b in cal]
    first = parsed[0][0]
    start = first.toordinal() - ((first.weekday() + 1) % 7)
    top = max([n for _, n in parsed] + [1])
    cols = 1
    cells = ""
    months = ""
    last_month = None
    last_col = -9
    for dt, n in parsed:
        idx = dt.toordinal() - start
        col, row = idx // 7, idx % 7
        cols = max(cols, col + 1)
        lvl = 0 if n <= 0 else min(4, 1 + int(3 * n / top))
        x = 24 + col * 14
        y = 56 + row * 14
        rect = f'<rect class="cell" x="{x}" y="{y}" width="11" height="11" rx="3" fill="{SHADES[lvl]}" style="animation-delay:{col * .025:.2f}s"/>'
        if lvl == 4:
            cells += f'<g class="pulse" style="animation-delay:{col * .1:.1f}s">{rect}</g>'
        else:
            cells += rect
        if dt.month != last_month:
            if col - last_col >= 3:
                months += f'<text x="{x}" y="50" class="l" style="font-size:9px">{dt.strftime("%b")}</text>'
                last_col = col
            last_month = dt.month
    w = max(410, 48 + cols * 14 - 3)
    total = sum(n for _, n in parsed)
    best = max(n for _, n in parsed)
    lx = w - 24 - 5 * 14 - 30
    foot = f'<text x="24" y="177" class="l">{fmt(total)} contributions · best day {fmt(best)}</text>'
    foot += f'<text x="{lx - 6}" y="177" class="l" text-anchor="end" style="font-size:9px">Less</text>'
    for i, s in enumerate(SHADES):
        foot += f'<rect x="{lx + i * 14}" y="167" width="11" height="11" rx="3" fill="{s}"/>'
    foot += f'<text x="{lx + 5 * 14 + 2}" y="177" class="l" style="font-size:9px">More</text>'
    return frame(w, 194, head(title) + months + cells + foot)


def ago(iso):
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - t).days
    except Exception:
        return "unknown"
    if days <= 0:
        return "today"
    if days == 1:
        return "1 day ago"
    if days < 60:
        return f"{days} days ago"
    return f"{days // 30} months ago"


def refresh_project(full, p):
    info = call(f"{API}/repos/{full}")
    p["name"] = info.get("name", p["name"])
    p["desc"] = info.get("description") or ""
    p["stars"] = info.get("stargazers_count", 0)
    p["forks"] = info.get("forks_count", 0)
    p["issues"] = info.get("open_issues_count", 0)
    p["lang"] = info.get("language") or "n/a"
    p["pushed"] = info.get("pushed_at") or ""
    p["license"] = (info.get("license") or {}).get("spdx_id") or "none"
    try:
        rel = call(f"{API}/repos/{full}/releases/latest")
        p["release"] = rel.get("tag_name") or "none"
    except Exception:
        try:
            tags = call(f"{API}/repos/{full}/tags?per_page=1")
            p["release"] = tags[0]["name"] if tags else "none"
        except Exception as e:
            log(e)


def project_svg(p):
    out = head(p["name"])
    lines = textwrap.wrap(p["desc"] or "No description yet.", 46)[:2]
    for i, line in enumerate(lines):
        out += f'<text x="24" y="{60 + i * 16}" class="l row" style="animation-delay:{i * .1:.1f}s">{escape(line)}</text>'
    tiles = [("STARS", p["stars"]), ("FORKS", p["forks"]), ("OPEN", p["issues"]), ("RELEASE", p["release"])]
    for i, (label, val) in enumerate(tiles):
        x = 24 + i * 92
        is_text = isinstance(val, str)
        shown = val[:11] if is_text else fmt(val)
        size = 11 if is_text else 18
        out += (
            f'<g class="pop" style="animation-delay:{i * .15:.2f}s">'
            f'<rect x="{x}" y="100" width="84" height="52" rx="8" fill="#14213D" stroke="url(#ac)" stroke-width="1.5"/>'
            f'<text x="{x + 42}" y="124" class="v" text-anchor="middle" style="font-size:{size}px">{escape(shown)}</text>'
            f'<text x="{x + 42}" y="142" class="l" text-anchor="middle" style="font-size:9px">{label}</text></g>'
        )
    out += (
        '<circle class="pulse" cx="30" cy="180" r="5" fill="#00D4FF"/>'
        f'<text x="42" y="184" class="v" style="font-size:12px">{escape(p["lang"])}</text>'
        f'<text x="205" y="184" class="l" text-anchor="middle">{escape(p["license"])}</text>'
        f'<text x="386" y="184" class="l" text-anchor="end">updated {escape(ago(p["pushed"]))}</text>'
        '<rect x="24" y="200" width="362" height="3" rx="1.5" fill="#14213D"/>'
        '<rect class="bar" x="24" y="200" width="362" height="3" rx="1.5" fill="url(#ac)" style="animation-delay:1s"/>'
    )
    return frame(410, 220, out)


def write(name, svg):
    try:
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
    except Exception as e:
        log(e)


def run_projects():
    path = os.path.join(OUT, "projects-cache.json")
    cache = {}
    try:
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        pass
    for full in PROJECTS:
        p = dict(PROJECT_DEFAULT)
        p.update(cache.get(full, {}))
        p["name"] = full.split("/")[-1]
        try:
            refresh_project(full, p)
        except Exception as e:
            log(e)
        cache[full] = p
        try:
            write("project-" + p["name"].lower() + ".svg", project_svg(p))
        except Exception as e:
            log(e)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception as e:
        log(e)


def main():
    os.makedirs(OUT, exist_ok=True)
    if KIND == "projects":
        run_projects()
        return
    d = load_cache()
    try:
        refresh(d)
    except Exception as e:
        log(e)
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception as e:
        log(e)
    cards = {
        "stats.svg": stats_svg,
        "langs.svg": langs_svg,
        "achievements.svg": ach_svg,
    }
    if KIND == "user":
        cards["streak.svg"] = streak_svg
        cards["graph.svg"] = lambda data: graph_svg(data, "Contribution Graph")
    elif MEMBERS:
        cards["graph.svg"] = lambda data: graph_svg(data, "Team Contributions")
    for name, fn in cards.items():
        try:
            write(name, fn(d))
        except Exception as e:
            log(e)


try:
    main()
except Exception as e:
    log(e)
sys.exit(0)
