"""Evaluation truth: which hidden variable actually drove the goal, measured by intervention.

Planting a factor does not make it the cause. For every hidden variable that could explain
the incident we run K paired futures that branch at the factor onset and share their
randomness, once as generated and once with that variable switched off. The effect is the
mean difference in the beneficiary's goals after the onset. The label is the variable with
the largest effect, but only if it clears an absolute bar, its own noise, and the runner-up.

Limits: this is the effect within this engine, on goals after the onset, not on the exact
goal in isolation. The decoy is excluded because its effect is zero by construction
(tests/test_phase0.py enforces that).
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from .engine import MatchConfig, mix, simulate, style_bias, style_lane

STYLE_MIN_BIAS = 0.15
MIN_EFFECT = 0.10     # goals; smaller effects are not worth explaining to a viewer
MIN_MARGIN = 0.05     # top cause must beat the runner-up by this much


@dataclass
class Effect:
    variable: str
    key: tuple
    mean: float
    se: float


@dataclass
class Truth:
    label: tuple | None       # None means ambiguous: no single hidden cause stands out
    effects: list
    planted_key: tuple
    but_for: bool             # on the actual timeline, does the goal vanish without the factor?
    k: int


def hypothesis_key(cfg: MatchConfig, variable: str) -> tuple:
    if variable == "factor":
        return ("FATIGUE" if cfg.factor.kind == "fatigue" else "OVERLOAD", cfg.factor.target)
    if variable == "static":
        return ("STATIC", cfg.weak_player)
    if variable == "style":
        return ("STYLE", style_lane(cfg))
    raise ValueError(variable)


def goals_after(result, team: str, t0: float) -> int:
    return sum(1 for t, tm, _ in result.goals if tm == team and t >= t0)


def measure(cfg: MatchConfig, incident_t: float, k: int = 80) -> Truth:
    split = cfg.factor.onset
    variables = ["factor"]
    if cfg.weak_player:
        variables.append("static")
    if style_bias(cfg) >= STYLE_MIN_BIAS:
        variables.append("style")

    diffs = {v: [] for v in variables}
    for i in range(k):
        noise = mix(cfg.seed, 7_000 + i)
        g_on = goals_after(simulate(cfg, noise, split), cfg.beneficiary, split)
        for v in variables:
            g_off = goals_after(simulate(cfg, noise, split, {v}), cfg.beneficiary, split)
            diffs[v].append(g_on - g_off)

    effects = sorted(
        (Effect(v, hypothesis_key(cfg, v), statistics.fmean(d), statistics.stdev(d) / math.sqrt(k))
         for v, d in diffs.items()),
        key=lambda e: -e.mean,
    )
    top = effects[0]
    runner_up = effects[1].mean if len(effects) > 1 else 0.0
    clear = top.mean >= MIN_EFFECT and top.mean - 2 * top.se > 0 and top.mean - runner_up >= MIN_MARGIN
    label = top.key if clear else None

    counterfactual = simulate(cfg, neutralize={"factor"})
    but_for = not any(tm == cfg.beneficiary and abs(t - incident_t) <= 120
                      for t, tm, _ in counterfactual.goals)
    return Truth(label, effects, hypothesis_key(cfg, "factor"), but_for, k)
