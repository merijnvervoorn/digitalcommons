"""
Agent-Based Model: Digital Commons — Mesa 3 Interactive Visualisation
=====================================================================
Wraps the core Olson (1971) collective-action model in Mesa's Agent / Model
classes and exposes it through a Solara web UI with:

  • Spatial grid   — firms colour-coded green (contributing) / red (free-riding)
  • Live sliders   — selective_incentive, benefit_multiplier (β), sensitivity
  • Time-series    — % of contributing firms over the run

Decision rule (stochastic sigmoid — same net_benefit signal as abm.py):
  net_benefit = selective_incentive + commons_quality × β − cost_threshold
  P(contribute) = sigmoid(net_benefit × sensitivity)

Using a sigmoid instead of a hard threshold means firms flip probabilistically,
so convergence is gradual and visible in real time. At sensitivity → ∞ the
behaviour collapses back to the original deterministic rule.

Run with:
  solara run abm_mesa.py
"""

import numpy as np
from scipy.special import erfinv, expit

from mesa import Agent, Model
from mesa.space import SingleGrid
from mesa.datacollection import DataCollector
from mesa.visualization import SolaraViz, make_space_component, make_plot_component

# ── Grid dimensions — 20 × 15 = 300 firms, matching N_AGENTS in abm.py ────────
GRID_WIDTH  = 20
GRID_HEIGHT = 15

# ── Parameter defaults (mirror abm.py canonical values) ───────────────────────
DEFAULT_INCENTIVE   = 1.0
DEFAULT_BETA        = 2.0
DEFAULT_GINI        = 0.70
DEFAULT_SENSITIVITY = 1.5   # sigmoid steepness; lower → slower, noisier convergence


# ── Core helper (identical to abm.py) ─────────────────────────────────────────

def calibrate_costs(gini: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Draw cost thresholds from Normal(μ,1) so (1−Gini) firms default to free-ride."""
    mu = np.sqrt(2) * erfinv(2.0 * np.clip(gini, 0.01, 0.999) - 1.0)
    return rng.normal(loc=mu, scale=1.0, size=n)


# ── Agent ──────────────────────────────────────────────────────────────────────

class FirmAgent(Agent):
    """One firm on the grid."""

    def __init__(self, model: "CommonsModel", cost_threshold: float) -> None:
        super().__init__(model)
        self.cost_threshold: float = cost_threshold
        self.contributing:   bool  = False

    def step(self) -> None:
        net_benefit = (
            self.model.selective_incentive
            + self.model.commons_quality * self.model.benefit_multiplier
            - self.cost_threshold
        )
        prob = float(expit(net_benefit * self.model.sensitivity))
        self.contributing = bool(self.model.rng.random() < prob)


# ── Model ──────────────────────────────────────────────────────────────────────

class CommonsModel(Model):
    """Digital-commons collective-action model on a fixed spatial grid."""

    def __init__(
        self,
        selective_incentive: float = DEFAULT_INCENTIVE,
        benefit_multiplier:  float = DEFAULT_BETA,
        gini:                float = DEFAULT_GINI,
        sensitivity:         float = DEFAULT_SENSITIVITY,
        width:               int   = GRID_WIDTH,
        height:              int   = GRID_HEIGHT,
        seed:                int   = 42,
    ) -> None:
        super().__init__(rng=seed)

        self.selective_incentive = selective_incentive
        self.benefit_multiplier  = benefit_multiplier
        self.sensitivity         = sensitivity
        self.gini                = gini
        self.commons_quality     = 0.0

        self.grid = SingleGrid(width, height, torus=False)

        np_rng          = np.random.default_rng(seed)
        cost_thresholds = calibrate_costs(gini, width * height, np_rng)

        for idx, (x, y) in enumerate(
            (x, y) for x in range(width) for y in range(height)
        ):
            agent = FirmAgent(self, float(cost_thresholds[idx]))
            self.grid.place_agent(agent, (x, y))

        self.datacollector = DataCollector(
            model_reporters={"Contributing %": lambda m: round(m.commons_quality * 100, 1)}
        )
        self.datacollector.collect(self)

    def step(self) -> None:
        # All firms decide simultaneously based on last step's commons_quality.
        self.agents.do("step")

        n_contrib            = sum(1 for a in self.agents if a.contributing)
        self.commons_quality = n_contrib / len(self.agents)

        self.datacollector.collect(self)


# ── Visualisation ──────────────────────────────────────────────────────────────

def agent_portrayal(agent: FirmAgent) -> dict:
    return {
        "color":  "#27ae60" if agent.contributing else "#e74c3c",
        "size":   20,
        "marker": "s",
    }


model_params = {
    "selective_incentive": {
        "type":  "SliderFloat",
        "value": DEFAULT_INCENTIVE,
        "label": "Selective Incentive",
        "min":   0.0,
        "max":   4.0,
        "step":  0.05,
    },
    "benefit_multiplier": {
        "type":  "SliderFloat",
        "value": DEFAULT_BETA,
        "label": "Benefit Multiplier (β)",
        "min":   1.0,
        "max":   3.0,
        "step":  0.05,
    },
    "gini": {
        "type":  "SliderFloat",
        "value": DEFAULT_GINI,
        "label": "Gini Coefficient",
        "min":   0.10,
        "max":   0.99,
        "step":  0.01,
    },
    "sensitivity": {
        "type":  "SliderFloat",
        "value": DEFAULT_SENSITIVITY,
        "label": "Sigmoid Sensitivity (higher = faster/deterministic)",
        "min":   0.5,
        "max":   8.0,
        "step":  0.25,
    },
    "width":  GRID_WIDTH,
    "height": GRID_HEIGHT,
}

_initial_model = CommonsModel(
    selective_incentive=DEFAULT_INCENTIVE,
    benefit_multiplier=DEFAULT_BETA,
    gini=DEFAULT_GINI,
    sensitivity=DEFAULT_SENSITIVITY,
    width=GRID_WIDTH,
    height=GRID_HEIGHT,
)

page = SolaraViz(
    _initial_model,
    components=[
        make_space_component(agent_portrayal),
        make_plot_component("Contributing %"),
    ],
    model_params=model_params,
    name="Digital Commons — Collective Action ABM",
)

page  # noqa: B018
