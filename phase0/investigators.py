"""Investigators that see only a Case (observable events + public line-ups).

Hypothesis vocabulary, always about the conceding team B or the scoring team A:
  FATIGUE(player)  a B full-back declined during the match
  STATIC(player)   a B full-back was weak all match
  OVERLOAD(lane)   A flooded a flank from some point on
  STYLE(lane)      A simply prefers that flank
  FOUL(event)      the dramatic foul before the goal turned the game

Baselines:
  random_ranking   uniform over the candidate set (chance level)
  salience         what a quick narrator says: blame the late booking, then the beaten defender
  lane_shortcut    uses only the lane the goal came from (tests whether the label leaks via geometry)
  StatInvestigator change-point and base-rate statistics with five per-kind weights fit on dev seeds
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .engine import FULL_BACK_FOR_LANE, LANE_POOL, OVERLOAD_RUNNER, WIDE_LANES, pid, role_of
from .observe import Case, event_lane

KINDS = ("FATIGUE", "OVERLOAD", "STATIC", "STYLE", "FOUL")
ATTACK_TYPES = {"pass", "carry", "dribble", "cross", "shot"}
TAUS = tuple(range(45 * 60, 81 * 60, 5 * 60))
FOUL_WINDOW = 20 * 60


@dataclass
class Hypothesis:
    kind: str
    target: str
    score: float
    onset: int | None = None
    cited: list = field(default_factory=list)
    rationale: str = ""

    @property
    def key(self) -> tuple:
        return (self.kind, self.target)


class MatchView:
    """Indexes a case around its incident. Everything here is derived from observables."""

    def __init__(self, case: Case):
        self.case = case
        self.by_id = {e["id"]: e for e in case.events}
        inc = self.by_id[case.incident_id]
        self.incident = inc
        self.A = inc["team"]
        self.B = case.away if self.A == case.home else case.home
        self.t_inc = inc["t"]
        self.attack = [e for e in case.events if e["team"] == self.A and e["type"] in ATTACK_TYPES]
        self.lane = {e["id"]: event_lane(e, case.home) for e in self.attack}
        build_up = [e for e in self.attack if e["possession_id"] == inc["possession_id"] and e["t"] <= inc["t"]]
        self.build_up = build_up
        self.goal_lanes = {self.lane[e["id"]] for e in build_up}
        before_shot = [e for e in build_up if e["type"] != "shot"]
        self.final_lane = self.lane[(before_shot or build_up)[-1]["id"]]
        self.last_foul = self._last_booked_foul()

    def _last_booked_foul(self):
        cards = [e for e in self.case.events
                 if e["type"] == "card" and e["team"] == self.B and self.t_inc - FOUL_WINDOW <= e["t"] <= self.t_inc]
        if not cards:
            return None
        card = cards[-1]
        fouls = [e for e in self.case.events
                 if e["type"] == "foul" and e["player_id"] == card["player_id"] and card["t"] - 2 <= e["t"] <= card["t"]]
        return fouls[-1] if fouls else None

    def full_back(self, lane: str) -> str:
        return pid(self.B, FULL_BACK_FOR_LANE[lane])

    def relevance(self, lane: str) -> float:
        return 1.0 + 0.5 * (lane in self.goal_lanes) + 0.5 * (lane == self.final_lane)


def candidate_keys(view: MatchView) -> list:
    keys = []
    for lane in WIDE_LANES:
        keys += [("FATIGUE", view.full_back(lane)), ("STATIC", view.full_back(lane)),
                 ("OVERLOAD", lane), ("STYLE", lane)]
    if view.last_foul:
        keys.append(("FOUL", view.last_foul["id"]))
    return keys


def z_prop(s1: int, n1: int, s2: int, n2: int) -> float:
    """Two-proportion z statistic for s1/n1 minus s2/n2; 0 when there is too little data."""
    if n1 < 3 or n2 < 3:
        return 0.0
    pooled = (s1 + s2) / (n1 + n2)
    var = pooled * (1 - pooled) * (1 / n1 + 1 / n2)
    if var <= 0:
        return 0.0
    return (s1 / n1 - s2 / n2) / math.sqrt(var)


def _wins(events) -> int:
    return sum(1 for e in events if e["outcome"] == "success")


# --- baselines -------------------------------------------------------------------------------

def random_ranking(case: Case, seed: int) -> list:
    keys = candidate_keys(MatchView(case))
    random.Random(seed).shuffle(keys)
    return [Hypothesis(k, t, 1.0 / (i + 1)) for i, (k, t) in enumerate(keys)]


def salience(case: Case) -> list:
    v = MatchView(case)
    out = []
    if v.last_foul:
        out.append(Hypothesis("FOUL", v.last_foul["id"], 3.0, cited=[v.last_foul["id"]],
                              rationale="booking shortly before the goal"))
    beaten = [e["opponent_id"] for e in v.build_up
              if e["opponent_id"] and e["type"] == "dribble" and e["outcome"] == "success"]
    lane = v.final_lane if v.final_lane in WIDE_LANES else "left"
    defender = beaten[-1] if beaten else v.full_back(lane)
    out.append(Hypothesis("FATIGUE", defender, 2.0, rationale="defender beaten in the build-up"))
    out.append(Hypothesis("OVERLOAD", lane, 1.0, rationale="goal came down this side"))
    return out


def lane_shortcut(case: Case) -> list:
    v = MatchView(case)
    if v.final_lane in WIDE_LANES:
        lane = v.final_lane
    else:
        wide = [l for l in WIDE_LANES if l in v.goal_lanes]
        lane = wide[0] if wide else "left"
    fb = v.full_back(lane)
    return [Hypothesis("FATIGUE", fb, 4.0), Hypothesis("OVERLOAD", lane, 3.0),
            Hypothesis("STATIC", fb, 2.0), Hypothesis("STYLE", lane, 1.0)]


# --- statistical investigator ----------------------------------------------------------------

DEFAULT_WEIGHTS = dict.fromkeys(KINDS, 1.0)


class StatInvestigator:
    """Change-point and base-rate statistics over observable events.

    Raw evidence strength per hypothesis is computed once; `rank` applies per-kind weights,
    which are the only fitted parameters (fit on development seeds, never on held-out ones).
    """

    def __init__(self, weights: dict | None = None):
        self.weights = dict(weights or DEFAULT_WEIGHTS)

    def evidence(self, case: Case) -> list:
        v = MatchView(case)
        out = []
        fatigue_change = {}
        for lane in WIDE_LANES:
            h = self._fatigue(v, lane)
            fatigue_change[h.target] = h.score
            out.append(h)
            out.append(self._overload(v, lane))
            out.append(self._style(v, lane))
        for lane in WIDE_LANES:
            out.append(self._static(v, lane, fatigue_change))
        if v.last_foul:
            out.append(Hypothesis("FOUL", v.last_foul["id"], 1.0, cited=[v.last_foul["id"]],
                                  rationale="booking within 20 minutes before the goal"))
        for h in out:
            if h.kind != "FOUL":
                lane = h.target if h.kind in ("OVERLOAD", "STYLE") else _lane_of_full_back(h.target)
                h.score = max(h.score, 0.0) * v.relevance(lane)
        return out

    def rank(self, evidence: list) -> list:
        ranked = [Hypothesis(h.kind, h.target, h.score * self.weights[h.kind], h.onset, h.cited, h.rationale)
                  for h in evidence]
        return sorted(ranked, key=lambda h: -h.score)

    def investigate(self, case: Case) -> list:
        return self.rank(self.evidence(case))

    def _fatigue(self, v: MatchView, lane: str) -> Hypothesis:
        d = v.full_back(lane)
        duels = [e for e in v.attack if e["type"] == "dribble" and e["opponent_id"] == d]
        # Only duel outcomes: more attacks down a flank is also what an overload looks like.
        best, best_tau = 0.0, None
        for tau in TAUS:
            pre = [e for e in duels if e["t"] < tau]
            post = [e for e in duels if e["t"] >= tau]
            s = z_prop(_wins(post), len(post), _wins(pre), len(pre))
            if s > best:
                best, best_tau = s, tau
        cited = [e["id"] for e in duels if best_tau is not None and e["t"] >= best_tau and e["outcome"] == "success"][:8]
        return Hypothesis("FATIGUE", d, best, best_tau, cited,
                          f"{d} lost more duels after the change point")

    def _overload(self, v: MatchView, lane: str) -> Hypothesis:
        runner = pid(v.A, OVERLOAD_RUNNER[lane])
        in_lane = [e for e in v.attack if v.lane[e["id"]] == lane]
        best, best_tau = 0.0, None
        for tau in TAUS:
            pre = [e for e in in_lane if e["t"] < tau]
            post = [e for e in in_lane if e["t"] >= tau]
            run_pre = sum(1 for e in pre if runner in (e["player_id"], e["receiver_id"]))
            run_post = sum(1 for e in post if runner in (e["player_id"], e["receiver_id"]))
            z_runner = z_prop(run_post, len(post), run_pre, len(pre))
            passes_pre = [e for e in pre if e["type"] in ("pass", "cross")]
            passes_post = [e for e in post if e["type"] in ("pass", "cross")]
            z_comp = z_prop(_wins(passes_post), len(passes_post), _wins(passes_pre), len(passes_pre))
            s = z_runner + 0.5 * max(0.0, z_comp)
            if s > best:
                best, best_tau = s, tau
        cited = [e["id"] for e in in_lane
                 if best_tau is not None and e["t"] >= best_tau and runner in (e["player_id"], e["receiver_id"])][:8]
        return Hypothesis("OVERLOAD", lane, best, best_tau, cited,
                          f"{runner} started appearing on the {lane} after the change point")

    def _style(self, v: MatchView, lane: str) -> Hypothesis:
        other = "right" if lane == "left" else "left"
        first_half = [e for e in v.attack if e["t"] < 45 * 60]
        n_l = sum(1 for e in first_half if v.lane[e["id"]] == lane)
        n_o = sum(1 for e in first_half if v.lane[e["id"]] == other)
        z = (n_l - n_o) / math.sqrt(n_l + n_o) if n_l + n_o else 0.0
        cited = [e["id"] for e in first_half if v.lane[e["id"]] == lane][:8]
        return Hypothesis("STYLE", lane, z, None, cited, f"first-half preference for the {lane}")

    def _static(self, v: MatchView, lane: str, fatigue_change: dict) -> Hypothesis:
        d = v.full_back(lane)
        o = v.full_back("right" if lane == "left" else "left")
        d_duels = [e for e in v.attack if e["type"] == "dribble" and e["opponent_id"] == d]
        o_duels = [e for e in v.attack if e["type"] == "dribble" and e["opponent_id"] == o]
        z_level = z_prop(_wins(d_duels), len(d_duels), _wins(o_duels), len(o_duels))
        score = z_level - 0.5 * max(0.0, fatigue_change.get(d, 0.0))
        cited = [e["id"] for e in d_duels if e["outcome"] == "success"][:8]
        return Hypothesis("STATIC", d, score, None, cited, f"{d} lost more duels than {o} all match")


def _lane_of_full_back(player_id: str) -> str:
    return {fb: lane for lane, fb in FULL_BACK_FOR_LANE.items()}[role_of(player_id)]


def fit_weights(evidence_by_case: list, labels: list, grid=(0.25, 0.5, 1.0, 1.5, 2.0, 3.0)) -> dict:
    """Grid-search per-kind weights (FATIGUE fixed at 1) to maximise recall@1 + 0.5*recall@3."""
    best, best_w = -1.0, dict(DEFAULT_WEIGHTS)
    pairs = [(ev, lab) for ev, lab in zip(evidence_by_case, labels) if lab is not None]
    if not pairs:
        return best_w
    for w_o in grid:
        for w_s in grid:
            for w_y in grid:
                for w_f in grid:
                    inv = StatInvestigator({"FATIGUE": 1.0, "OVERLOAD": w_o, "STATIC": w_s, "STYLE": w_y, "FOUL": w_f})
                    r1 = r3 = 0
                    for ev, lab in pairs:
                        keys = [h.key for h in inv.rank(ev)[:3]]
                        r1 += keys[0] == lab
                        r3 += lab in keys
                    objective = (r1 + 0.5 * r3) / len(pairs)
                    if objective > best:
                        best, best_w = objective, inv.weights
    return best_w


# --- verification ----------------------------------------------------------------------------

def verify(h: Hypothesis, view: MatchView) -> tuple:
    """Deterministic check of a hypothesis against observable evidence.

    Returns (supported, fraction_of_valid_citations, reasons). A claim is supported only if its
    target is well-formed for its kind and every cited event exists and involves that target.
    """
    reasons = []
    valid_targets = {
        "FATIGUE": {view.full_back(l) for l in WIDE_LANES},
        "STATIC": {view.full_back(l) for l in WIDE_LANES},
        "OVERLOAD": set(WIDE_LANES),
        "STYLE": set(WIDE_LANES),
        "FOUL": {e["id"] for e in view.case.events if e["type"] == "foul" and e["team"] == view.B},
    }
    if h.kind not in valid_targets:
        return False, 0.0, [f"unknown kind {h.kind!r}"]
    if h.target not in valid_targets[h.kind]:
        reasons.append(f"target {h.target!r} is not valid for {h.kind}")
    if h.onset is not None and not (0 <= h.onset <= 95 * 60):
        reasons.append("onset outside the match")
    if not h.cited:
        return False, 0.0, reasons + ["no evidence cited"]
    good = 0
    for cid in h.cited:
        e = view.by_id.get(cid)
        if e is None:
            reasons.append(f"{cid} does not exist")
        elif _involves(h, e, view):
            good += 1
        else:
            reasons.append(f"{cid} does not involve {h.target}")
    frac = good / len(h.cited)
    return (not reasons), frac, reasons


def _involves(h: Hypothesis, e: dict, view: MatchView) -> bool:
    after_onset = h.onset is None or e["t"] >= h.onset
    if h.kind in ("FATIGUE", "STATIC"):
        return h.target in (e["opponent_id"], e["player_id"]) and after_onset
    if h.kind in ("OVERLOAD", "STYLE"):
        return e["team"] == view.A and e["id"] in view.lane and view.lane[e["id"]] == h.target and after_onset
    if h.kind == "FOUL":
        return e["id"] == h.target or (e["type"] in ("foul", "card") and e["team"] == view.B)
    return False
