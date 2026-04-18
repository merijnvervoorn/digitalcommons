# import subprocess, json

# syft = "C:\\Users\\light\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Anchore.Syft_Microsoft.Winget.Source_8wekyb3d8bbwe\\syft.exe"
# repo = "https://github.com/scikit-learn/scikit-learn"
# repo_list = repo.split("/")
# repo_name = repo_list[(len(repo_list))-1]

# # Step 1: clone the repo
# #subprocess.run(["git", "clone", repo])

# # Step 2: run syft on it
# subprocess.run([syft, "dir:./"+repo_name, "-o", "spdx-json="+repo_name+".spdx.json"], shell = True)

# # Step 3: parse the SBOM
# with open(repo_name+".spdx.json") as f:
#     sbom = json.load(f)

# # Step 4: extract package names for GitHub API lookup
# packages = [p["name"] for p in sbom["packages"]]
# print(packages)

# -------------------------------------------------------------------------------------------------------------------------------------

# import subprocess, json, time, os
# import urllib.request
# import urllib.parse
# import urllib.error
 
# syft = "C:\\Users\\light\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Anchore.Syft_Microsoft.Winget.Source_8wekyb3d8bbwe\\syft.exe"
# repo = "https://github.com/scikit-learn/scikit-learn"
# repo_list = repo.split("/")
# repo_name = repo_list[(len(repo_list))-1]
 
# # Step 2: run syft on it
# subprocess.run([syft, "dir:./"+repo_name, "-o", "spdx-json="+repo_name+".spdx.json"], shell=True)
 
# # Step 3: parse the SBOM
# with open(repo_name+".spdx.json") as f:
#     sbom = json.load(f)
 
# # Step 4: extract package names
# packages = sbom["packages"]
# seen = {}
# for p in packages:
#     purl = next(
#         (ref["referenceLocator"] for ref in p.get("externalRefs", [])
#          if ref.get("referenceType") == "purl"),
#         "N/A"
#     )
#     if purl != "N/A":
#         purl = purl.removeprefix("pkg:")
#         purl = purl.split("@")[0]
#     seen[purl] = p["name"]

# for purl, name in seen.items():
#     print(f"{name}: {purl}")

# -------------------------------------------------------------------------------------------------------------------------------------

""" CODE BELOW CURRENTLY ONLY ANALYSES DEPENDENCIES FROM GITHUB """

import subprocess, json, time, os, re
import urllib.request
import urllib.parse
import urllib.error

syft = "C:\\Users\\light\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Anchore.Syft_Microsoft.Winget.Source_8wekyb3d8bbwe\\syft.exe"
repo = "https://github.com/scikit-learn/scikit-learn"
repo_list = repo.split("/")
repo_name = repo_list[(len(repo_list))-1]

# Optional: set GITHUB_TOKEN env var for higher rate limits (5000 req/hr vs 60)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# COCOMO II constants
# A is recalibrated for kilobytes (KB) rather than KLOC.
# Assuming ~45 bytes/line on average, 1 KLOC ~ 45 KB.
# Original A=2.94 per KLOC → 2.94 / 45 = ~0.065 per KB
# VALUES SUBJECT TO CHANGE
COCOMO_A         = 0.065 # 2.94 / 45
COCOMO_E         = 1.0
MONTHLY_RATE_USD = 10000

def github_request(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SCA-script"}
    # if GITHUB_TOKEN:
    #     headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())

def get_byte_count(owner, repo):
    try:
        languages = github_request(f"https://api.github.com/repos/{owner}/{repo}/languages")
        return sum(languages.values())
    except Exception:
        return None

def parse_purl(purl_raw):
    # Strip pkg: prefix and version, return (ecosystem, path)
    purl      = purl_raw.removeprefix("pkg:")
    purl      = purl.split("@")[0]
    parts     = purl.split("/", 1)
    ecosystem = parts[0]
    path      = parts[1] if len(parts) > 1 else ""
    return ecosystem, path

def cocomo_cost(total_bytes):
    """Return (effort_person_months, cost_usd) using bytes as the size input."""
    kb     = total_bytes / 1000
    effort = COCOMO_A * (kb ** COCOMO_E)
    cost   = effort * MONTHLY_RATE_USD
    return round(effort, 1), round(cost)

def format_bytes(n):
    if n is None:        return "N/A"
    if n >= 1_000_000:   return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:       return f"{n / 1_000:.1f} KB"
    return f"{n} B"

def format_cost(n):
    if n is None:      return "N/A"
    if n >= 1_000_000: return f"${n / 1_000_000:.1f}M"
    if n >= 1_000:     return f"${n / 1_000:.0f}K"
    return f"${n}"

def print_ecosystem_summary(ecosystem_counts, total):
    """Print a frequency table of packages grouped by ecosystem."""
    col_eco   = 20
    col_count = 8
    col_pct   = 8
    sep = f"+{'-'*(col_eco+2)}+{'-'*(col_count+2)}+{'-'*(col_pct+2)}+"

    print("\n  Package sources (deduplicated)\n")
    print(sep)
    print(f"| {'Ecosystem':<{col_eco}} | {'Count':<{col_count}} | {'%':<{col_pct}} |")
    print(sep)
    for eco, count in sorted(ecosystem_counts.items(), key=lambda x: -x[1]):
        pct = f"{count / total * 100:.1f}%"
        print(f"| {eco:<{col_eco}} | {count:<{col_count}} | {pct:<{col_pct}} |")
    print(sep)
    print(f"  Total unique packages: {total}\n")

def print_table(results, total_scanned):
    col_name   = 26
    col_bytes  = 12
    col_effort = 10
    col_cost   = 10
    sep = (f"+{'-'*(col_name+2)}+{'-'*(col_bytes+2)}"
           f"+{'-'*(col_effort+2)}+{'-'*(col_cost+2)}+")

    print("\n  GitHub packages — COCOMO II cost estimate\n")
    print(sep)
    print(f"| {'Package':<{col_name}} | {'Size':<{col_bytes}}"
          f" | {'Effort(PM)':<{col_effort}} | {'Cost (USD)':<{col_cost}} |")
    print(sep)
    for name, info in sorted(results.items()):
        size   = format_bytes(info["bytes"])
        effort = f"{info['effort']} PM" if info["effort"] else "N/A"
        cost   = format_cost(info["cost"])
        print(f"| {name:<{col_name}} | {size:<{col_bytes}}"
              f" | {effort:<{col_effort}} | {cost:<{col_cost}} |")
    print(sep)

    total_cost = sum(v["cost"] for v in results.values() if v["cost"])
    print(f"\n  {len(results)} GitHub packages processed ({total_scanned} total packages in SBOM)")
    print(f"  Total estimated replacement cost: {format_cost(total_cost)}")
    print(f"  (COCOMO II byte-based: A={COCOMO_A}, E={COCOMO_E}, rate=${MONTHLY_RATE_USD:,}/month)\n")

#subprocess.run(["git", "clone", repo])

subprocess.run([syft, "dir:./"+repo_name, "-o", "spdx-json="+repo_name+".spdx.json"], shell=True)

with open(repo_name+".spdx.json") as f:
    sbom = json.load(f)

seen             = {}
ecosystem_counts = {}
github_packages  = {}

for p in sbom["packages"]:
    raw_purl = next(
        (ref["referenceLocator"] for ref in p.get("externalRefs", [])
         if ref.get("referenceType") == "purl"),
        None
    )
    if not raw_purl or raw_purl in seen:
        continue
    seen[raw_purl]   = True
    ecosystem, path  = parse_purl(raw_purl)
    ecosystem_counts[ecosystem] = ecosystem_counts.get(ecosystem, 0) + 1
    if ecosystem == "github":
        github_packages[raw_purl] = {"name": p["name"], "path": path}

total_scanned = len(sbom["packages"])
total_unique  = len(seen)

print_ecosystem_summary(ecosystem_counts, total_unique)

# fetch byte counts and compute COCOMO for github packages
total_github = len(github_packages)
print(f"  Fetching byte counts for {total_github} GitHub packages...\n")

results = {}
for i, (raw_purl, info) in enumerate(github_packages.items()):
    name    = info["name"]
    path    = info["path"]
    print(f"  [{i+1}/{total_github}] {name}", end="\r", flush=True)

    parts   = path.strip("/").split("/")
    owner   = parts[0] if len(parts) >= 1 else None
    repo_id = parts[1] if len(parts) >= 2 else None

    total_bytes  = get_byte_count(owner, repo_id) if owner and repo_id else None
    effort, cost = cocomo_cost(total_bytes) if total_bytes else (None, None)

    results[name] = {"bytes": total_bytes, "effort": effort, "cost": cost}
    time.sleep(0.5)

print(" " * 60)
print_table(results, total_scanned)
