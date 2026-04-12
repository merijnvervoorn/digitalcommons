"""
GitHub Repo Gini Coefficient Calculator
Multi-repo CSV output, measures contribution inequality using commit counts per author.

Repositories are hardcoded in the REPOS list. Results are saved to gini_results.csv and printed in a summary table.

Use /opt/anaconda3/bin/python gini_repo.py in terminal if anaconda is installed.

"""

import sys
import csv
import requests
from collections import defaultdict

TOKEN = "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"
REPOS = [
    "facebook/react",
    "scikit-learn/scikit-learn",
    "mastodon/mastodon",
    "ClusterHQ/flocker",
]

OUTPUT_FILE = "gini_results.csv"


def get_contributors(owner: str, repo: str, token: str = None) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    commits_per_author = defaultdict(int)
    page = 1

    print(f"  Fetching {owner}/{repo}...")

    while True:
        resp = requests.get(
            url,
            headers=headers,
            params={"per_page": 100, "page": page, "anon": "true"},
        )

        if resp.status_code == 403:
            print("  Rate limit hit. Add a GitHub token to the TOKEN variable at the top of the script.")
            sys.exit(1)
        if resp.status_code == 404:
            print(f"  Repo {owner}/{repo} not found — skipping.")
            return {}
        resp.raise_for_status()

        data = resp.json()
        if not data:
            break

        for contributor in data:
            login = contributor.get("login") or contributor.get("email", "anonymous")
            commits_per_author[login] += contributor.get("contributions", 0)

        if "next" not in resp.links:
            break
        page += 1

    return dict(commits_per_author)


def gini(values: list) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    sorted_vals = sorted(values)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cumulative = sum((i + 1) * v for i, v in enumerate(sorted_vals))
    return (2 * cumulative) / (n * total) - (n + 1) / n


def analyze_repo(full_repo: str) -> dict | None:
    owner, repo = full_repo.split("/", 1)
    contributors = get_contributors(owner, repo, token=TOKEN)

    if not contributors:
        return None

    counts = list(contributors.values())
    total_commits = sum(counts)
    sorted_authors = sorted(contributors.items(), key=lambda x: x[1], reverse=True)

    top_author, top_commits = sorted_authors[0]
    top5_commits = sum(c for _, c in sorted_authors[:5])

    return {
        "repo": full_repo,
        "gini": round(gini(counts), 4),
        "total_commits": total_commits,
        "total_contributors": len(counts),
        "top_author": top_author,
        "top_author_commits": top_commits,
        "top_author_pct": round(top_commits / total_commits * 100, 2),
        "top5_pct": round(top5_commits / total_commits * 100, 2),
    }


def print_summary(results: list):
    print()
    print("=" * 75)
    print(f"  {'Repo':<30} {'Gini':>6}  {'Contributors':>12}  {'Top Author %':>12}  {'Top 5 %':>8}")
    print("  " + "-" * 70)
    for r in results:
        print(f"  {r['repo']:<30} {r['gini']:>6.4f}  {r['total_contributors']:>12,}  {r['top_author_pct']:>11.1f}%  {r['top5_pct']:>7.1f}%")
    print("=" * 75)


def main():
    print(f"\nAnalyzing {len(REPOS)} repos...\n")

    results = []
    for repo in REPOS:
        result = analyze_repo(repo)
        if result:
            results.append(result)

    if not results:
        print("No results collected.")
        sys.exit(1)

    # Write CSV
    fieldnames = [
        "repo", "gini", "total_commits", "total_contributors",
        "top_author", "top_author_commits", "top_author_pct", "top5_pct"
    ]
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print_summary(results)
    print(f"\n  CSV saved to: {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()