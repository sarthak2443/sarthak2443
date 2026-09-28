#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

OWNER = os.getenv("GITHUB_OWNER", "sarthak2443")
FEATURED_REPO = os.getenv("FEATURED_REPO", "Portfolio")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "profile"))
TOKEN = os.getenv("GITHUB_TOKEN", "")

BG = "#0d1117"
BORDER = "#30363d"
TITLE = "#58a6ff"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#7ee787"


def request_json(url: str) -> object:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "readme-cards-generator")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def request_json_or_default(url: str, default: object) -> object:
    try:
        return request_json(url)
    except Exception as exc:  # pragma: no cover - defensive for API/network issues
        print(f"Warning: failed to load {url}: {exc}", file=sys.stderr)
        return default


def card(title: str, body_lines: list[str], width: int = 450, height: int = 180) -> str:
    line_step = 24
    text_blocks = [f'<text x="24" y="40" fill="{TITLE}" font-size="20" font-weight="700">{escape(title)}</text>']
    y = 74
    for line in body_lines:
        text_blocks.append(
            f'<text x="24" y="{y}" fill="{TEXT}" font-size="16">{escape(line)}</text>'
        )
        y += line_step
    content = "\n    ".join(text_blocks)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">Generated GitHub profile card for {escape(OWNER)}</desc>
  <rect width="100%" height="100%" rx="12" fill="{BG}" stroke="{BORDER}"/>
  {content}
</svg>
'''


def fetch_repositories(owner: str) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{urllib.parse.quote(owner)}/repos?per_page=100&type=owner&page={page}"
        data = request_json_or_default(url, [])
        if not isinstance(data, list) or not data:
            break
        repos.extend([r for r in data if isinstance(r, dict)])
        if len(data) < 100:
            break
        page += 1
    return repos


def fetch_languages(owner: str, repo_name: str) -> dict[str, int]:
    url = f"https://api.github.com/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo_name)}/languages"
    data = request_json_or_default(url, {})
    if isinstance(data, dict):
        return {str(k): int(v) for k, v in data.items() if isinstance(v, int)}
    return {}


def generate() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    user = request_json_or_default(
        f"https://api.github.com/users/{urllib.parse.quote(OWNER)}",
        {},
    )
    if not isinstance(user, dict):
        raise RuntimeError("Unexpected user payload from GitHub API")

    repos = fetch_repositories(OWNER)
    public_repos = int(user.get("public_repos", 0))
    followers = int(user.get("followers", 0))
    following = int(user.get("following", 0))
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in repos)

    stats_svg = card(
        "GitHub Stats",
        [
            f"Public Repositories: {public_repos}",
            f"Followers: {followers}",
            f"Following: {following}",
            f"Total Stars Earned: {stars}",
        ],
    )
    (OUTPUT_DIR / "stats.svg").write_text(stats_svg, encoding="utf-8")

    languages_totals: defaultdict[str, int] = defaultdict(int)
    for repo in repos:
        if repo.get("fork"):
            continue
        repo_name = repo.get("name")
        if isinstance(repo_name, str) and repo_name:
            for language, value in fetch_languages(OWNER, repo_name).items():
                languages_totals[language] += value

    top_languages = sorted(languages_totals.items(), key=lambda item: item[1], reverse=True)[:5]
    total_bytes = sum(value for _, value in top_languages) or 1
    lines = [
        f"{language}: {value * 100 // total_bytes}%"
        for language, value in top_languages
    ] or ["No language statistics available"]

    top_langs_svg = card("Top Languages", lines)
    (OUTPUT_DIR / "top-langs.svg").write_text(top_langs_svg, encoding="utf-8")

    featured = request_json_or_default(
        f"https://api.github.com/repos/{urllib.parse.quote(OWNER)}/{urllib.parse.quote(FEATURED_REPO)}"
        ,
        {},
    )
    if not isinstance(featured, dict):
        raise RuntimeError("Unexpected featured repository payload from GitHub API")

    description = str(featured.get("description") or "No description provided")
    if len(description) > 42:
        description = description[:39] + "..."

    portfolio_svg = card(
        f"Featured: {FEATURED_REPO}",
        [
            description,
            f"Primary Language: {featured.get('language') or 'N/A'}",
            f"Stars: {featured.get('stargazers_count', 0)}  Forks: {featured.get('forks_count', 0)}",
            f"Open Issues: {featured.get('open_issues_count', 0)}",
        ],
    )
    (OUTPUT_DIR / "portfolio.svg").write_text(portfolio_svg, encoding="utf-8")


if __name__ == "__main__":
    generate()
