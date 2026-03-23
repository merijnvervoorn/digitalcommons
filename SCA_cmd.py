import subprocess, json

syft = "C:\\Users\\light\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Anchore.Syft_Microsoft.Winget.Source_8wekyb3d8bbwe\\syft.exe"
repo = "https://github.com/scikit-learn/scikit-learn"
repo_list = repo.split("/")
repo_name = repo_list[(len(repo_list))-1]

# Step 1: clone the repo
subprocess.run(["git", "clone", repo])

# Step 2: run syft on it
subprocess.run([syft, "dir:./"+repo_name, "-o", "spdx-json="+repo_name+".spdx.json"], shell = True)

# Step 3: parse the SBOM
with open(repo_name+".spdx.json") as f:
    sbom = json.load(f)

# Step 4: extract package names for GitHub API lookup
packages = [p["name"] for p in sbom["packages"]]
print(packages)

#test
print("Hello")