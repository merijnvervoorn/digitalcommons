# Making the Commons Work — Quantitative Analysis

BSc Computational Social Science capstone — University of Amsterdam
Collaboration with Internet Society Netherlands (ISOC) and the Open Systems Foundation (OSF)

---

## `gini_repo.py`

Fetches GitHub contribution data and computes a Gini coefficient per repository.

- Set your GitHub token in `TOKEN` and list repos in `REPOS`
- Pulls commit counts per contributor via the GitHub API
- Computes the Contributions Gini Index (CGI): 0 = perfectly equal, 1 = one person does everything
- Outputs results to `data/gini_results.csv`

```bash
/opt/anaconda3/bin/python gini_repo.py
```

---

## `abm.py`

Agent-Based Model simulating firms choosing to contribute or free-ride on the digital commons. Reads from `data/gini_results.csv`.

- Each agent is a firm with a cost threshold drawn from a distribution calibrated to the repo's Gini coefficient — higher Gini means more firms default to free-riding
- Each step, a firm contributes if: `incentive + commons_quality × β ≥ cost`
- Commons quality updates each step based on the current contributor fraction, creating a feedback loop
- Sweeps across incentive levels to find the tipping point where ≥50% of firms contribute
- Also runs a sensitivity sweep over the benefit multiplier (β) to confirm the repo ordering is robust
- Outputs plots to `figures/` and data to `data/`

```bash
/opt/anaconda3/bin/python abm.py
```

**What the outputs show:**

The incentive sweep curves (main plot)
- For each repo, it sweeps incentive from 0 to 4 and shows what fraction of firms end up contributing at each level
- The S-curve shape shows the feedback loop — once enough firms contribute, commons quality rises, which pulls in more firms
- The red dashed line is the tipping point: the minimum incentive needed to get ≥50% of firms contributing

The Gini scatter (bottom of main plot)
- Shows that higher Gini → higher tipping point, across all repos
- This is the core empirical finding: more unequal repos need more incentive to overcome free-riding

The sensitivity chart
- Shows the same tipping points across different values of the benefit multiplier β
- The key result here is that the ordering never changes — sandstorm always needs the most incentive, flocker always the least, regardless of β
- This means the finding is robust even though β is estimated from theory, not measured

---

## References

- Olson, M. (1971). *The Logic of Collective Action*. Harvard University Press.
- Ostrom, E. (2015). *Governing the Commons*. Cambridge University Press.
- Hoffmann, Nagle & Zhou (2024). *The Value of Open Source Software*. HBS Working Paper 24-038.
