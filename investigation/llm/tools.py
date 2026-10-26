"""Read-only tools the LLM agents may call. All of them read observable events only.

Every result lists the event ids it is based on; agents may cite only ids a tool returned to
them (the verifier enforces existence and relevance afterwards).
"""
from __future__ import annotations

from phase0.engine import FULL_BACK_FOR_LANE, OVERLOAD_RUNNER, WIDE_LANES, pid
from phase0.investigators import TAUS, MatchView, StatInvestigator, z_prop

from ..language import club, player
from ..sceptic import CHALLENGERS, best_decline, duel_record, other_full_back
from ..workflow import DEFAULT_WEIGHTS

KINDS = ["FATIGUE", "STATIC", "OVERLOAD", "STYLE", "FOUL"]
MAX_IDS = 10
MIN_FLANK_SAMPLE = 25
OVERLOAD_SHARE = 0.20


def _m(t: float) -> int:
    return int(t // 60) + 1


def _strict(name: str, description: str, properties: dict, required: list | None = None) -> dict:
    return {"name": name, "description": description, "strict": True,
            "input_schema": {"type": "object", "properties": properties,
                             "required": required if required is not None else list(properties),
                             "additionalProperties": False}}


class MatchTools:
    def __init__(self, view: MatchView, roster: dict):
        self.v = view
        self.roster = roster
        self.seen_ids: set[str] = set()

    def _ids(self, ids) -> list:
        ids = list(ids)[:MAX_IDS]
        self.seen_ids.update(ids)
        return ids

    def _defender(self, defender_id: str) -> str:
        valid = {self.v.full_back(l) for l in WIDE_LANES}
        if defender_id not in valid:
            raise ValueError(f"defender_id must be one of {sorted(valid)}")
        return defender_id

    # --- shared evidence tools ------------------------------------------------------------

    def match_brief(self) -> dict:
        v = self.v
        fb = {lane: v.full_back(lane) for lane in WIDE_LANES}
        return {
            "scoring_team": club(v.A), "conceding_team": club(v.B),
            "goal": {"event_id": self._ids([v.incident["id"]])[0], "minute": _m(v.t_inc),
                     "scorer": player(self.roster, v.incident["player_id"])},
            "flanks": {lane: {"scoring_team_attacks_down": lane,
                              "defended_by": {"id": fb[lane], "name": player(self.roster, fb[lane])},
                              "overload_runner": player(self.roster, pid(v.A, OVERLOAD_RUNNER[lane]))}
                       for lane in WIDE_LANES},
            "booking_before_goal": ({"event_id": self._ids([v.last_foul["id"]])[0], "minute": _m(v.last_foul["t"]),
                                     "player": player(self.roster, v.last_foul["player_id"])} if v.last_foul else None),
            "valid_targets": {"FATIGUE": list(fb.values()), "STATIC": list(fb.values()), "OVERLOAD": list(WIDE_LANES),
                              "STYLE": list(WIDE_LANES), "FOUL": [v.last_foul["id"]] if v.last_foul else []},
        }

    def goal_build_up(self) -> dict:
        evs = self.v.build_up
        return {"events": [{"id": e["id"], "minute": _m(e["t"]), "player": player(self.roster, e["player_id"]),
                            "type": e["type"], "outcome": e["outcome"], "lane": self.v.lane[e["id"]],
                            "opponent": player(self.roster, e["opponent_id"]) if e["opponent_id"] else None}
                           for e in evs],
                "event_ids": self._ids(e["id"] for e in evs)}

    def statistical_screen(self) -> dict:
        """The statistical investigator's evidence strength per candidate: a lead, not a verdict."""
        evidence = StatInvestigator(DEFAULT_WEIGHTS).investigate(self.v.case)
        return {"note": "Change-point and base-rate statistics. Higher means stronger evidence; it does not establish cause.",
                "candidates": [{"kind": h.kind, "target": h.target, "strength": round(h.score, 2),
                                "change_minute": _m(h.onset) if h.onset else None,
                                "event_ids": self._ids(h.cited[:5])} for h in evidence]}

    def duel_record(self, defender_id: str, from_minute: int, to_minute: int) -> dict:
        d = self._defender(defender_id)
        rec = duel_record(self.v, d, (from_minute - 1) * 60, to_minute * 60)
        return {"defender": player(self.roster, d), "from_minute": from_minute, "to_minute": to_minute,
                "duels": rec["n"], "lost": rec["lost"], "event_ids": self._ids(rec["lost_ids"])}

    def defender_decline(self, defender_id: str) -> dict:
        d = self._defender(defender_id)
        z, tau = best_decline(self.v, d)
        if tau is None:
            return {"defender": player(self.roster, d), "decline_found": False}
        pre, post = duel_record(self.v, d, 0, tau), duel_record(self.v, d, tau)
        return {"defender": player(self.roster, d), "decline_found": z >= 1.0, "change_minute": _m(tau),
                "strength_z": round(z, 2), "before": f"{pre['lost']} of {pre['n']} duels lost",
                "after": f"{post['lost']} of {post['n']} duels lost", "event_ids": self._ids(post["lost_ids"])}

    def flank_profile(self, lane: str, from_minute: int, to_minute: int) -> dict:
        if lane not in WIDE_LANES:
            raise ValueError("lane must be 'left' or 'right'")
        lo, hi = (from_minute - 1) * 60, to_minute * 60
        window = [e for e in self.v.attack if lo <= e["t"] < hi]
        in_lane = [e for e in window if self.v.lane[e["id"]] == lane]
        passes = [e for e in in_lane if e["type"] in ("pass", "cross")]
        players = {}
        for e in in_lane:
            name = player(self.roster, e["player_id"])
            players[name] = players.get(name, 0) + 1
        runner = pid(self.v.A, OVERLOAD_RUNNER[lane])
        runner_ids = [e["id"] for e in in_lane if runner in (e["player_id"], e["receiver_id"])]
        return {"lane": lane, "from_minute": from_minute, "to_minute": to_minute,
                "share_of_attacking_actions": round(len(in_lane) / max(len(window), 1), 2),
                "pass_completion": round(sum(e["outcome"] == "success" for e in passes) / max(len(passes), 1), 2),
                "players_on_this_flank": dict(sorted(players.items(), key=lambda kv: -kv[1])[:6]),
                "overload_runner_appearances": len(runner_ids), "event_ids": self._ids(runner_ids or [e["id"] for e in in_lane[:6]])}

    def flank_change(self, lane: str) -> dict:
        """Overload detector: did the overload runner become a regular presence on this flank from some minute?

        Calibrated on tuning matches only (seeds 400001+): in real overloads the runner takes part in at
        least about a quarter of flank actions afterwards; otherwise at most about one in six. Pass
        completion is reported for context, not used: a tiring full-back raises it too.
        """
        if lane not in WIDE_LANES:
            raise ValueError("lane must be 'left' or 'right'")
        runner = pid(self.v.A, OVERLOAD_RUNNER[lane])
        in_lane = [e for e in self.v.attack if self.v.lane[e["id"]] == lane]
        hits = lambda evs: [e for e in evs if runner in (e["player_id"], e["receiver_id"])]
        passes = lambda evs: [e for e in evs if e["type"] in ("pass", "cross")]
        done = lambda evs: sum(e["outcome"] == "success" for e in evs)
        best_share, best_tau = 0.0, None
        for tau in TAUS:
            post = [e for e in in_lane if e["t"] >= tau]
            if len(post) < MIN_FLANK_SAMPLE:
                continue
            share = len(hits(post)) / len(post)
            if share > best_share:
                best_share, best_tau = share, tau
        name = player(self.roster, runner)
        if best_tau is None:
            return {"lane": lane, "overload_runner": name, "change_found": False, "note": "too few flank actions to judge"}
        pre = [e for e in in_lane if e["t"] < best_tau]
        post = [e for e in in_lane if e["t"] >= best_tau]
        found = best_share >= OVERLOAD_SHARE and len(hits(post)) >= 5
        return {"lane": lane, "overload_runner": name, "change_found": found, "from_minute": _m(best_tau),
                "runner_share_after": f"{len(hits(post))} of {len(post)} flank actions",
                "runner_share_before": f"{len(hits(pre))} of {len(pre)} flank actions",
                "flank_pass_completion_before_after": f"{done(passes(pre))} of {len(passes(pre))} -> {done(passes(post))} of {len(passes(post))} (context only)",
                "rule": f"an overload means the runner is in at least {OVERLOAD_SHARE:.0%} of flank actions afterwards",
                "event_ids": self._ids(e["id"] for e in hits(post)) if found else []}

    # --- sceptic tool ---------------------------------------------------------------------

    def standard_tests(self, claim) -> list:
        return CHALLENGERS[claim.kind](self.v, claim, self.roster)


INVESTIGATOR_TOOLS = [
    _strict("match_brief", "Teams, the goal, who defends each flank, the booking before the goal, and valid hypothesis targets.", {}),
    _strict("goal_build_up", "The events of the move that produced the goal.", {}),
    _strict("statistical_screen", "Change-point and base-rate evidence strength for every candidate explanation. A lead, not a verdict.", {}),
    _strict("duel_record", "One-on-one duels a full-back faced in a minute window, and how many they lost.",
            {"defender_id": {"type": "string"}, "from_minute": {"type": "integer"}, "to_minute": {"type": "integer"}}),
    _strict("defender_decline", "Whether a full-back's duel record clearly got worse at some point, and from when.",
            {"defender_id": {"type": "string"}}),
    _strict("flank_profile", "How the scoring team used one flank in a minute window: share of play, pass completion, who appeared there.",
            {"lane": {"type": "string", "enum": list(WIDE_LANES)}, "from_minute": {"type": "integer"}, "to_minute": {"type": "integer"}}),
    _strict("flank_change", "Overload detector: whether the overload runner became a regular presence on one flank from some minute (change_found).",
            {"lane": {"type": "string", "enum": list(WIDE_LANES)}}),
    _strict("submit_hypotheses", "Submit 1 to 4 candidate causes, strongest first. Call exactly once, at the end.",
            {"hypotheses": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["kind", "target", "onset_minute", "cited_event_ids", "reasoning"],
                "properties": {"kind": {"type": "string", "enum": KINDS}, "target": {"type": "string"},
                               "onset_minute": {"type": ["integer", "null"]},
                               "cited_event_ids": {"type": "array", "items": {"type": "string"}},
                               "reasoning": {"type": "string"}}}}}),
]

SCEPTIC_TOOLS = [
    _strict("run_standard_tests", "Run the deterministic challenge tests for one claim (for example: was the defender already struggling? did play reset after the booking?).",
            {"claim_id": {"type": "string"}}),
    INVESTIGATOR_TOOLS[3], INVESTIGATOR_TOOLS[4], INVESTIGATOR_TOOLS[5], INVESTIGATOR_TOOLS[6],
    _strict("submit_reviews", "Submit a verdict for every claim you reviewed. Call exactly once, at the end.",
            {"reviews": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["claim_id", "verdict", "rationale"],
                "properties": {"claim_id": {"type": "string"}, "verdict": {"type": "string", "enum": ["upheld", "weakened", "refuted"]},
                               "rationale": {"type": "string"}}}}}),
]

PRODUCER_TOOL = _strict(
    "submit_explanation", "Submit the final explanation. Call exactly once.",
    {"headline": {"type": "string"},
     "beats": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                          "required": ["label", "fan", "analyst"],
                                          "properties": {"label": {"type": "string", "enum": ["Cause", "Evidence", "The moment"]},
                                                         "fan": {"type": "string"}, "analyst": {"type": "string"}}}}})
