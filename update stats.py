import json
import os
import re
import urllib.request
from collections import Counter
from datetime import datetime, timezone

ORG = os.environ.get("ORG", "NetCore-Technologies")
TOKEN = os.environ.get("GH_TOKEN", "")
README = "profile/README.md"
MAX_ROWS = 6


def api(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "netcore-readme-bot"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def fetch_repos():
    repos = []
    page = 1
    while True:
        batch = api(f"https://api.github.com/orgs/{ORG}/repos?type=public&per_page=100&page={page}")
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return [r for r in repos if not r["fork"] and not r["archived"] and r["name"] != ".github"]


def replace_block(text, name, content):
    pattern = re.compile(rf"(<!--START_{name}-->)(.*?)(<!--END_{name}-->)", re.DOTALL)
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", text)


def build_stats(repos):
    stars = sum(r["stargazers_count"] for r in repos)
    forks = sum(r["forks_count"] for r in repos)
    langs = Counter(r["language"] for r in repos if r["language"])
    top = " · ".join(f"`{name}`" for name, _ in langs.most_common(6)) or "`n/a`"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"**{len(repos)}** public repos &nbsp;|&nbsp; **{stars}** ★ stars &nbsp;|&nbsp; **{forks}** forks\n\n"
        f"Top languages: {top}\n\n"
        f"<sub>Auto-refreshed {now}</sub>"
    )


def build_table(repos):
    rows = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:MAX_ROWS]
    lines = ["| Repository | Description | Language | ★ | Last push |", "|---|---|---|---|---|"]
    for r in rows:
        desc = (r["description"] or "No description yet").replace("|", "/")
        lang = r["language"] or "-"
        pushed = r["pushed_at"][:10]
        lines.append(f"| [{r['name']}]({r['html_url']}) | {desc} | {lang} | {r['stargazers_count']} | {pushed} |")
    return "\n".join(lines)


def main():
    repos = fetch_repos()
    with open(README, "r", encoding="utf-8") as f:
        text = f.read()
    text = replace_block(text, "STATS", build_stats(repos))
    text = replace_block(text, "REPOS", build_table(repos))
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
