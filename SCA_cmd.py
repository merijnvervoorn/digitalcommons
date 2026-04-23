import subprocess, json, time, os, re
import urllib.request
import urllib.parse
import urllib.error
import pandas as pd

syft = "C:\\Users\\light\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Anchore.Syft_Microsoft.Winget.Source_8wekyb3d8bbwe\\syft.exe"
repo = "https://github.com/scikit-learn/scikit-learn"
repo_list = repo.split("/")
repo_name = repo_list[(len(repo_list))-1]

# Optional: set GITHUB_TOKEN env var for higher rate limits (5000 req/hr vs 60)
# In PowerShell run: $env:GITHUB_TOKEN = "your_token_here"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# COCOMO II constants
# A is recalibrated for kilobytes (KB) rather than KLOC.
# Assuming ~45 bytes/line on average, 1 KLOC ~ 45 KB.
# Original A=2.94 per KLOC → 2.94 / 45 = ~0.065 per KB
"""A is the calibration constant (2.94) and E is the scaling exponent. 
    When E is above 1.0 the model captures diseconomies of scale — the idea 
    that larger projects become disproportionately harder because of 
    increased communication overhead, coordination complexity, and 
    integration effort. A project twice as large doesn't just take 
    twice as long, it takes more than twice as long"""
# VALUES SUBJECT TO CHANGE
COCOMO_A         = 0.065 # 2.94 / 45
COCOMO_E         = 1.0
MONTHLY_RATE_USD = 10000

# Common OSI-approved open source licence identifiers
OPEN_SOURCE_LICENCES = {
    "MIT", "Apache-2.0", "GPL-2.0", "GPL-3.0", "LGPL-2.0", "LGPL-2.1",
    "LGPL-3.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MPL-2.0",
    "CDDL-1.0", "EPL-1.0", "EPL-2.0", "AGPL-3.0", "CC0-1.0",
    "Artistic-2.0", "Unlicense", "WTFPL", "Zlib", "PSF-2.0",
}

def github_request(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SCA-script"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())

def get_byte_count_github(owner, repo):
    """Fetch total bytes and licence from GitHub for a given owner/repo."""
    try:
        languages = github_request(f"https://api.github.com/repos/{owner}/{repo}/languages")
        repo_data = github_request(f"https://api.github.com/repos/{owner}/{repo}")
        licence   = (repo_data.get("license") or {}).get("spdx_id") or "NOASSERTION"
        return sum(languages.values()), licence
    except Exception:
        return None, "NOASSERTION"

def find_github_url(all_urls):
    """Search a list of URLs for a GitHub repo link and return (owner, repo) or (None, None)."""
    for url in all_urls:
        if not url:
            continue
        match = re.search(r"github\.com/([^/]+)/([^/#?\s]+)", url)
        if match:
            owner = match.group(1)
            repo  = match.group(2).rstrip("/")
            return owner, repo
    return None, None

def get_byte_count_pypi(package_name):
    """Resolve a PyPI package to its GitHub repo and return byte count and licence."""
    try:
        req = urllib.request.Request(
            f"https://pypi.org/pypi/{package_name}/json",
            headers={"User-Agent": "SCA-script"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        info       = data.get("info", {})
        licence    = info.get("license") or "NOASSERTION"
        candidates = list((info.get("project_urls") or {}).values()) + [info.get("home_page", "")]
        owner, repo = find_github_url(candidates)
        byte_count  = get_byte_count_github(owner, repo)[0] if owner and repo else None
        return byte_count, licence
    except Exception:
        return None, "NOASSERTION"

def get_byte_count_npm(package_name):
    """Fetch unpacked size and licence of an npm package from the npm registry."""
    try:
        req = urllib.request.Request(
            f"https://registry.npmjs.org/{package_name}/latest",
            headers={"User-Agent": "SCA-script"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        licence = data.get("license") or "NOASSERTION"
        return data.get("dist", {}).get("unpackedSize"), licence
    except Exception:
        return None, "NOASSERTION"

def get_byte_count_gem(package_name):
    """Resolve a gem package to its GitHub repo and return byte count and licence."""
    try:
        req = urllib.request.Request(
            f"https://rubygems.org/api/v1/gems/{package_name}.json",
            headers={"User-Agent": "SCA-script"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        # RubyGems returns a list of licences
        licences = data.get("licenses") or []
        licence  = licences[0] if licences else "NOASSERTION"
        candidates = [
            data.get("source_code_uri", ""),
            data.get("homepage_uri", ""),
            data.get("bug_tracker_uri", ""),
        ]
        owner, repo = find_github_url(candidates)
        byte_count  = get_byte_count_github(owner, repo)[0] if owner and repo else None
        return byte_count, licence
    except Exception:
        return None, "NOASSERTION"

def get_byte_count_golang(package_name):
    """Fetch size of a Go module from the Go module proxy and licence from GitHub."""
    try:
        # Step 1: get the latest version number
        encoded_name = urllib.parse.quote(package_name, safe="")
        req = urllib.request.Request(
            f"https://proxy.golang.org/{encoded_name}/@latest",
            headers={"User-Agent": "SCA-script"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        version = data.get("Version")
        if not version:
            return None, "NOASSERTION"

        # Step 2: send a HEAD request for the zip to get its size
        zip_url = f"https://proxy.golang.org/{encoded_name}/@v/{version}.zip"
        req = urllib.request.Request(zip_url, method="HEAD",
                                     headers={"User-Agent": "SCA-script"})
        with urllib.request.urlopen(req, timeout=10) as response:
            content_length = response.headers.get("Content-Length")
        byte_count = int(content_length) if content_length else None

        # Step 3: try to get licence from GitHub if the module is hosted there
        owner, repo = find_github_url([package_name])
        if owner and repo:
            _, licence = get_byte_count_github(owner, repo)
        else:
            licence = "NOASSERTION"

        return byte_count, licence
    except Exception:
        return None, "NOASSERTION"

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
    """Effort (person-months) = A × Size^E × ∏EM"""
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
    """Print ecosystem frequency table as a pandas DataFrame."""
    rows = [
        {"Ecosystem": eco, "Count": count, "%": f"{count / total * 100:.1f}%"}
        for eco, count in sorted(ecosystem_counts.items(), key=lambda x: -x[1])
    ]
    df = pd.DataFrame(rows)
    print("\n  Package sources (deduplicated)\n")
    print(df.to_string(index=False))
    print(f"\n  Total unique packages: {total}\n")

def print_table(results, total_scanned):
    """Print COCOMO results as a pandas DataFrame."""
    rows = []
    for name, info in sorted(results.items()):
        rows.append({
            "Package":      name,
            "Source":       info["ecosystem"],
            "Licence":      info["licence"],
            "Open Source":  "Yes" if info["is_open_source"] else "No",
            "Size":         format_bytes(info["bytes"]),
            "Effort (PM)":  f"{info['effort']} PM" if info["effort"] else "N/A",
            "Cost (USD)":   format_cost(info["cost"]),
        })

    df = pd.DataFrame(rows)
    print("\n  GitHub & PyPI packages — COCOMO II cost estimate\n")
    print(df.to_string(index=False))

    # Only sum cost for open source packages
    total_cost     = sum(v["cost"] for v in results.values() if v["cost"] and v["is_open_source"])
    resolved       = sum(1 for v in results.values() if v["bytes"])
    open_src_count = sum(1 for v in results.values() if v["is_open_source"])
    print(f"\n  {resolved} of {len(results)} packages resolved to a byte count ({total_scanned} total in SBOM)")
    print(f"  {open_src_count} of {len(results)} packages identified as open source")
    print(f"  Total estimated replacement cost (open source only): {format_cost(total_cost)}")
    print(f"  (COCOMO II byte-based: A={COCOMO_A}, E={COCOMO_E}, rate=${MONTHLY_RATE_USD:,}/month)\n")

# Uncomment if repository not cloned
# subprocess.run(["git", "clone", repo])

subprocess.run([syft, "dir:./"+repo_name, "-o", "spdx-json="+repo_name+".spdx.json"], shell=True)

with open(repo_name+".spdx.json") as f:
    sbom = json.load(f)

seen             = {}
ecosystem_counts = {}
target_packages  = {}  # packages to process (github + pypi + npm + gem + golang)

for p in sbom["packages"]:
    raw_purl = next(
        (ref["referenceLocator"] for ref in p.get("externalRefs", [])
         if ref.get("referenceType") == "purl"),
        None
    )
    if not raw_purl or raw_purl in seen:
        continue
    seen[raw_purl]  = True
    ecosystem, path = parse_purl(raw_purl)
    ecosystem_counts[ecosystem] = ecosystem_counts.get(ecosystem, 0) + 1

    if ecosystem in ("github", "pypi", "npm", "gem", "golang"):
        target_packages[raw_purl] = {
            "name":      p["name"],
            "path":      path,
            "ecosystem": ecosystem,
        }

total_scanned = len(sbom["packages"])
total_unique  = len(seen)

print_ecosystem_summary(ecosystem_counts, total_unique)

total_target = len(target_packages)
print(f"  Fetching byte counts for {total_target} GitHub + PyPI + npm + gem + golang packages...\n")

results = {}
for i, (raw_purl, info) in enumerate(target_packages.items()):
    name      = info["name"]
    path      = info["path"]
    ecosystem = info["ecosystem"]
    print(f"  [{i+1}/{total_target}] {name} ({ecosystem})", end="\r", flush=True)

    if ecosystem == "github":
        parts   = path.strip("/").split("/")
        owner   = parts[0] if len(parts) >= 1 else None
        repo_id = parts[1] if len(parts) >= 2 else None
        total_bytes, licence = get_byte_count_github(owner, repo_id) if owner and repo_id else (None, "NOASSERTION")

    elif ecosystem == "pypi":
        package_name         = path.split("/")[-1]
        total_bytes, licence = get_byte_count_pypi(package_name)

    elif ecosystem == "npm":
        package_name         = urllib.parse.unquote(path)
        total_bytes, licence = get_byte_count_npm(package_name)

    elif ecosystem == "gem":
        package_name         = path.split("/")[-1]
        total_bytes, licence = get_byte_count_gem(package_name)

    elif ecosystem == "golang":
        total_bytes, licence = get_byte_count_golang(path)

    is_open_source = any(lic in licence for lic in OPEN_SOURCE_LICENCES)
    effort, cost   = cocomo_cost(total_bytes) if total_bytes else (None, None)
    results[name]  = {
        "ecosystem":      ecosystem,
        "licence":        licence,
        "is_open_source": is_open_source,
        "bytes":          total_bytes,
        "effort":         effort,
        "cost":           cost,
    }
    time.sleep(0.75)

print(" " * 60)
print_table(results, total_scanned)
