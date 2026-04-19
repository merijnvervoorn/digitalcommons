"""
Agent-Based Model: Digital Commons Contribution Dynamics
=========================================================
Simulates small firms choosing to contribute to or free-ride on digital commons.
Calibrated from empirical GitHub Gini coefficients (gini_results.csv).

Theoretical basis: Olson (1971) collective action theory.
  - Rational firms free-ride unless a selective incentive makes contributing worthwhile.
  - ABM finds the incentive tipping point where ≥50% of firms switch to contributing.

Agent decision rule (each step):
  net_benefit = selective_incentive + commons_quality * benefit_multiplier - cost_threshold
  contribute  iff  net_benefit >= 0

Commons quality = fraction of contributing firms (positive feedback loop).
Cost threshold distribution: Normal(μ, 1), μ = Φ⁻¹(Gini), so that at zero incentive
exactly (1 − Gini) of firms contribute — directly encoding the empirical free-rider rate.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.special import erfinv

# ── Simulation constants ──────────────────────────────────────────────────────
N_AGENTS        = 300    # firms per simulation
N_STEPS         = 30     # timesteps per run (converges quickly)
N_RUNS          = 10     # independent runs per incentive level (robustness)
N_INCENTIVE_PTS = 80     # resolution of the incentive sweep
INCENTIVE_RANGE = (0.0, 4.0)

# Canonical benefit multiplier — see README and calibrate_costs() docstring.
# Grounded in Ostrom (2015) BCR lower-bound midpoint × average cost-threshold
# centre across repos. Cross-checked against Hoffmann, Nagle & Zhou (2024).
BENEFIT_MULTIPLIER = 2.0

# Sensitivity sweep range for BENEFIT_MULTIPLIER (Ostrom BCR 1.5–2.5, ±buffer)
SENSITIVITY_RANGE  = np.round(np.arange(1.0, 3.25, 0.25), 2)


# ── Core ABM ──────────────────────────────────────────────────────────────────

def calibrate_costs(gini: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Draw firm-level contribution cost thresholds from Normal(μ, 1).

    μ is chosen so that at zero incentive and zero commons quality, exactly
    (1 − Gini) of firms have a negative net cost and will choose to contribute.

    Derivation:
      P(cost ≤ 0) = 1 − Gini
      Φ(−μ / 1)  = 1 − Gini
      μ           = Φ⁻¹(Gini) = √2 · erfinv(2·Gini − 1)

    Effect: higher Gini → larger μ → most firms default to free-riding.
    """
    mu = np.sqrt(2) * erfinv(2.0 * np.clip(gini, 0.01, 0.999) - 1.0)
    return rng.normal(loc=mu, scale=1.0, size=n)


def run_model(
    cost_thresholds: np.ndarray,
    selective_incentive: float,
    benefit_multiplier: float = BENEFIT_MULTIPLIER,
    n_steps: int = N_STEPS,
) -> float:
    """
    Run one ABM instance. Returns steady-state contributor fraction (final step).

    Each step: firms update simultaneously based on current commons quality.
    Commons quality then updates to the new contributor fraction.
    The loop converges within ~15 steps for all tested parameter values.
    """
    commons_quality = 0.0

    for _ in range(n_steps):
        net_benefit  = selective_incentive + commons_quality * benefit_multiplier - cost_thresholds
        commons_quality = (net_benefit >= 0.0).mean()

    return float(commons_quality)


def incentive_sweep(
    gini: float,
    benefit_multiplier: float = BENEFIT_MULTIPLIER,
    n_agents: int = N_AGENTS,
    n_runs: int = N_RUNS,
    n_steps: int = N_STEPS,
    incentive_range: tuple = INCENTIVE_RANGE,
    n_pts: int = N_INCENTIVE_PTS,
    base_seed: int = 42,
) -> pd.DataFrame:
    """
    Sweep selective_incentive across a range, running n_runs replicates each time.
    Returns DataFrame with mean ± std contributor fraction per incentive level.
    """
    incentives = np.linspace(*incentive_range, n_pts)
    records = []

    for incentive in incentives:
        fracs = [
            run_model(
                calibrate_costs(gini, n_agents, np.random.default_rng(base_seed + run * 1000)),
                incentive,
                benefit_multiplier,
                n_steps,
            )
            for run in range(n_runs)
        ]
        records.append({
            "incentive": incentive,
            "mean": np.mean(fracs),
            "std":  np.std(fracs),
        })

    return pd.DataFrame(records)


def find_tipping_point(sweep_df: pd.DataFrame, threshold: float = 0.5) -> float:
    """Return the smallest incentive where mean contributor fraction ≥ threshold."""
    above = sweep_df[sweep_df["mean"] >= threshold]
    return float(above["incentive"].min()) if not above.empty else float("nan")


# ── Plotting helpers ───────────────────────────────────────────────────────────

def plot_repo_sweep(ax, sweep_df, repo, gini, tipping, color):
    incentive = sweep_df["incentive"]
    mean      = sweep_df["mean"]
    std       = sweep_df["std"]

    ax.plot(incentive, mean, color=color, linewidth=2.2, label="Mean contributor fraction")
    ax.fill_between(incentive, mean - std, mean + std, color=color, alpha=0.2,
                    label=f"±1 SD ({N_RUNS} runs)")
    ax.axhline(0.5, color="grey", linestyle=":", linewidth=1.2, alpha=0.7)

    if not np.isnan(tipping):
        ax.axvline(tipping, color="crimson", linestyle="--", linewidth=1.6,
                   label=f"Tipping point ≈ {tipping:.2f}")

    ax.set_title(f"{repo.split('/')[-1]}  (Gini = {gini})", fontsize=11, fontweight="bold")
    ax.set_xlabel("Selective Incentive Level")
    ax.set_ylabel("Contributor Fraction")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)


def plot_tipping_vs_gini(ax, summary_df):
    valid  = summary_df.dropna(subset=["tipping_point"])
    colors = plt.cm.Set2(np.linspace(0, 1, len(valid)))

    for (_, row), c in zip(valid.iterrows(), colors):
        ax.scatter(row["gini"], row["tipping_point"], s=120, color=c, zorder=3,
                   label=row["repo"].split("/")[-1])

    if len(valid) >= 2:
        m, b = np.polyfit(valid["gini"], valid["tipping_point"], 1)
        x_line = np.linspace(valid["gini"].min() - 0.02, valid["gini"].max() + 0.02, 50)
        ax.plot(x_line, m * x_line + b, "k--", linewidth=1.4, alpha=0.6, label="Linear fit")

    ax.set_xlabel("Gini Coefficient (contribution inequality)")
    ax.set_ylabel("Tipping Point Incentive")
    ax.set_title("Higher Gini → Higher Incentive Needed to Overcome Free-Riding", fontsize=10)
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)


def plot_sensitivity(ax, sensitivity_df, repos, ginis, palette):
    """
    Fan chart: tipping point vs BENEFIT_MULTIPLIER for each repo.
    Shows whether the Gini ordering is robust to parameter uncertainty.
    """
    for repo, gini, color in zip(repos, ginis, palette):
        sub = sensitivity_df[sensitivity_df["repo"] == repo].dropna(subset=["tipping_point"])
        ax.plot(sub["benefit_multiplier"], sub["tipping_point"],
                color=color, linewidth=2.0, marker="o", markersize=4,
                label=f"{repo.split('/')[-1]} (Gini={gini})")

    ax.axvspan(1.5, 2.5, alpha=0.08, color="grey", label="Ostrom BCR range (1.5–2.5)")
    ax.axvline(BENEFIT_MULTIPLIER, color="black", linestyle="--", linewidth=1.2,
               label=f"Canonical value ({BENEFIT_MULTIPLIER})")
    ax.set_xlabel("Benefit Multiplier")
    ax.set_ylabel("Tipping Point Incentive")
    ax.set_title("Sensitivity of Tipping Points to Benefit Multiplier\n"
                 "Stable ordering across repos validates robustness", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    gini_df = pd.read_csv("data/gini_results.csv")
    repos   = gini_df["repo"].tolist()
    ginis   = gini_df["gini"].tolist()
    palette = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2", "#937860"]

    # ── 1. Main incentive sweep ───────────────────────────────────────────────
    print(f"\nRunning incentive sweep for {len(repos)} repos  "
          f"({N_AGENTS} agents · {N_STEPS} steps · {N_RUNS} runs)\n")

    sweep_results = {}
    summary_rows  = []

    for repo, gini, color in zip(repos, ginis, palette):
        print(f"  {repo}  (Gini = {gini}) …", end=" ", flush=True)
        sweep   = incentive_sweep(gini)
        tipping = find_tipping_point(sweep)
        sweep_results[repo] = sweep
        summary_rows.append({"repo": repo, "gini": gini, "tipping_point": tipping})
        print(f"tipping point = {tipping:.3f}")

    summary_df = pd.DataFrame(summary_rows)

    # ── 2. Sensitivity sweep over BENEFIT_MULTIPLIER ──────────────────────────
    print(f"\nRunning sensitivity sweep  "
          f"(benefit_multiplier = {SENSITIVITY_RANGE.tolist()})\n")

    sens_rows = []
    for bm in SENSITIVITY_RANGE:
        for repo, gini in zip(repos, ginis):
            print(f"  BM={bm:.2f}  {repo} …", end=" ", flush=True)
            sweep   = incentive_sweep(gini, benefit_multiplier=bm)
            tipping = find_tipping_point(sweep)
            sens_rows.append({"benefit_multiplier": bm, "repo": repo,
                               "gini": gini, "tipping_point": tipping})
            print(f"tipping point = {tipping:.3f}")

    sensitivity_df = pd.DataFrame(sens_rows)
    sensitivity_df.to_csv("data/abm_sensitivity.csv", index=False)
    print("\n  Sensitivity data saved → data/abm_sensitivity.csv")

    # ── 3. Figure 1: repo sweeps + Gini scatter ───────────────────────────────
    fig1 = plt.figure(figsize=(14, 17))
    fig1.suptitle(
        "Agent-Based Model: Digital Commons Free-Rider Tipping Points\n"
        "Calibrated from GitHub Contribution Gini Coefficients",
        fontsize=13, fontweight="bold", y=0.99,
    )
    gs1 = gridspec.GridSpec(4, 2, figure=fig1, hspace=0.50, wspace=0.35)

    for idx, (repo, gini, color) in enumerate(zip(repos, ginis, palette)):
        ax = fig1.add_subplot(gs1[idx // 2, idx % 2])
        tp = summary_df.loc[summary_df["repo"] == repo, "tipping_point"].values[0]
        plot_repo_sweep(ax, sweep_results[repo], repo, gini, tp, color)

    ax_scatter = fig1.add_subplot(gs1[3, :])
    plot_tipping_vs_gini(ax_scatter, summary_df)

    fig1.savefig("figures/abm_results.png", dpi=150, bbox_inches="tight")
    print("  Figure 1 saved → figures/abm_results.png")

    # ── 4. Figure 2: sensitivity fan chart ───────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    fig2.suptitle(
        "Sensitivity Analysis: Tipping Points Across Benefit Multiplier Values\n"
        "Robustness check for the Ostrom (2015) BCR parameter",
        fontsize=12, fontweight="bold",
    )
    plot_sensitivity(ax2, sensitivity_df, repos, ginis, palette)
    fig2.tight_layout()
    fig2.savefig("figures/abm_sensitivity.png", dpi=150, bbox_inches="tight")
    print("  Figure 2 saved → figures/abm_sensitivity.png\n")

    # ── 5. Console summary ────────────────────────────────────────────────────
    summary_df.to_csv("data/abm_tipping_points.csv", index=False)
    print("=" * 65)
    print(f"  {'Repo':<32} {'Gini':>6}  {'Tipping Pt':>10}")
    print("  " + "-" * 60)
    for _, row in summary_df.iterrows():
        tp_str = f"{row['tipping_point']:.3f}" if not np.isnan(row["tipping_point"]) else "N/A"
        print(f"  {row['repo']:<32} {row['gini']:>6.4f}  {tp_str:>10}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
