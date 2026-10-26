"""The sceptic: tries to break each proposed explanation with a targeted, comparative test.

The investigator scores each hypothesis on its own. The sceptic asks the questions that only
make sense across hypotheses: was the defender already struggling before he "tired"? Did the
goal actually come from the booking's restart? Is the flank problem about extra attackers or
about one defender losing duels? A finding can weaken a claim and shift weight to the
explanation it points at instead.

This implementation is deterministic. An LLM sceptic must call the same tests (they are its
tools) and pass the same verifier; it may only choose which tests to run and how to phrase them.
"""
from __future__ import annotations

import math

from phase0.engine import OVERLOAD_RUNNER, WIDE_LANES, pid
from phase0.investigators import TAUS, MatchView, z_prop

from .board import Board, Challenge, Claim
from .language import club, flank, minute, player

VERDICT_FACTOR = {"proposed": 1.0, "upheld": 1.0, "weakened": 0.55, "refuted": 0.05}
SHIFT_SHARE = 0.6          # share of a weakened claim's score handed to the explanation it points at
ALREADY_WEAK_Z = 1.0
DECLINE_Z = 1.0
GOT_WORSE_Z = 1.5


# --- tools: small, deterministic queries over observable events -------------------------------

def duel_record(v: MatchView, defender: str, t_from: float = 0, t_to: float = math.inf) -> dict:
    duels = [e for e in v.attack if e["type"] == "dribble" and e["opponent_id"] == defender
             and t_from <= e["t"] < t_to]
    lost = [e for e in duels if e["outcome"] == "success"]
    return {"lost": len(lost), "n": len(duels), "lost_ids": [e["id"] for e in lost]}


def best_decline(v: MatchView, defender: str) -> tuple:
    best, best_tau = 0.0, None
    for tau in TAUS:
        pre, post = duel_record(v, defender, 0, tau), duel_record(v, defender, tau)
        z = z_prop(post["lost"], post["n"], pre["lost"], pre["n"])
        if z > best:
            best, best_tau = z, tau
    return best, best_tau


def runner_presence(v: MatchView, lane: str, tau: float) -> tuple:
    runner = pid(v.A, OVERLOAD_RUNNER[lane])
    in_lane = [e for e in v.attack if v.lane[e["id"]] == lane]
    hits = lambda evs: sum(1 for e in evs if runner in (e["player_id"], e["receiver_id"]))
    pre = [e for e in in_lane if e["t"] < tau]
    post = [e for e in in_lane if e["t"] >= tau]
    return z_prop(hits(post), len(post), hits(pre), len(pre)), runner


def other_full_back(v: MatchView, defender: str) -> str:
    return next(v.full_back(l) for l in WIDE_LANES if v.full_back(l) != defender)


# --- challenges --------------------------------------------------------------------------------

def challenge_fatigue(v: MatchView, c: Claim, roster: dict) -> list:
    d, tau = c.target, c.onset or 60 * 60
    o = other_full_back(v, d)
    pre, other_pre = duel_record(v, d, 0, tau), duel_record(v, o, 0, tau)
    post = duel_record(v, d, tau)
    z_pre = z_prop(pre["lost"], pre["n"], other_pre["lost"], other_pre["n"])
    z_change = z_prop(post["lost"], post["n"], pre["lost"], pre["n"])
    declined = z_change >= DECLINE_Z
    record = f"{pre['lost']} of {pre['n']} duels lost before {minute(tau)}"
    other = f"{other_pre['lost']} of {other_pre['n']} for {player(roster, o)}"

    q = f"Was {player(roster, d)} already struggling before {minute(tau)}?"
    if z_pre >= ALREADY_WEAK_Z and not declined:
        first = Challenge(q, f"Yes: {record}, against {other}, and no clear change afterwards. That looks like a "
                             f"mismatch all match, not a late decline.", "weakened", pre["lost_ids"][:6], ("STATIC", d))
    elif z_pre >= ALREADY_WEAK_Z:
        first = Challenge(q, f"Somewhat: {record}, against {other}, but it got clearly worse afterwards.",
                          "upheld", pre["lost_ids"][:4])
    elif z_pre <= -ALREADY_WEAK_Z:
        first = Challenge(q, f"No: {record}, fewer than {other}.", "upheld", pre["lost_ids"][:4])
    else:
        first = Challenge(q, f"No: {record}, in line with {other}.", "upheld", pre["lost_ids"][:4])

    q = f"Did the decline after {minute(tau)} really happen?"
    if not declined:
        second = Challenge(q, f"Not clearly: {post['lost']} of {post['n']} duels lost after {minute(tau)} "
                              f"versus {pre['lost']} of {pre['n']} before.", "weakened", post["lost_ids"][:6])
    else:
        second = Challenge(q, f"Yes: {post['lost']} of {post['n']} duels lost after {minute(tau)}, "
                              f"up from {pre['lost']} of {pre['n']} before.", "upheld", post["lost_ids"][:6])
    return [first, second]


def challenge_static(v: MatchView, c: Claim, roster: dict) -> list:
    d = c.target
    o = other_full_back(v, d)
    z_decline, tau = best_decline(v, d)
    q = f"Did {player(roster, d)} get worse as the match went on?"
    if z_decline >= GOT_WORSE_Z and tau is not None:
        pre, post = duel_record(v, d, 0, tau), duel_record(v, d, tau)
        return [Challenge(q, f"Yes: {pre['lost']} of {pre['n']} duels lost before {minute(tau)}, then "
                             f"{post['lost']} of {post['n']} after. A decline, not a constant weakness.",
                          "weakened", post["lost_ids"][:6], ("FATIGUE", d))]
    first, other_first = duel_record(v, d, 0, 45 * 60), duel_record(v, o, 0, 45 * 60)
    z_first = z_prop(first["lost"], first["n"], other_first["lost"], other_first["n"])
    q2 = "Was the gap already visible in the first half?"
    if z_first < 0.5:
        return [Challenge(q, "No clear decline.", "upheld"),
                Challenge(q2, f"No: {first['lost']} of {first['n']} first-half duels lost, against "
                              f"{other_first['lost']} of {other_first['n']} for {player(roster, o)}.", "weakened",
                          first["lost_ids"][:6])]
    return [Challenge(q, "No clear decline.", "upheld"),
            Challenge(q2, f"Yes: {first['lost']} of {first['n']} first-half duels lost, against "
                          f"{other_first['lost']} of {other_first['n']} for {player(roster, o)}.", "upheld",
                      first["lost_ids"][:6])]


def challenge_overload(v: MatchView, c: Claim, roster: dict) -> list:
    lane, tau = c.target, c.onset or 60 * 60
    fb = v.full_back(lane)
    z_runner, runner = runner_presence(v, lane, tau)
    z_fb, _ = best_decline(v, fb)
    q = f"Is the problem on {flank(v.A, lane)} extra attackers, or {player(roster, fb)} losing duels?"
    if z_fb > z_runner:
        return [Challenge(q, f"More likely the defender: {player(roster, fb)}'s duel record declined more sharply "
                             f"than {player(roster, runner)}'s presence on that flank grew.", "weakened",
                          duel_record(v, fb, tau)["lost_ids"][:6], ("FATIGUE", fb))]
    return [Challenge(q, f"Extra attackers: {player(roster, runner)} kept appearing on that flank after "
                         f"{minute(tau)}, which a tiring defender alone does not explain.", "upheld", c.cited[:6])]


def challenge_style(v: MatchView, c: Claim, roster: dict) -> list:
    lane = c.target
    shots = [e for e in v.attack if e["type"] == "shot"]
    shot_poss = {e["possession_id"] for e in shots}
    via_lane = {e["possession_id"] for e in v.attack if v.lane[e["id"]] == lane and e["possession_id"] in shot_poss}
    share_actions = sum(1 for e in v.attack if v.lane[e["id"]] == lane) / max(len(v.attack), 1)
    share_shots = len(via_lane) / max(len(shot_poss), 1)
    q = f"Did {club(v.A)}'s preference for the {lane} actually produce chances?"
    if share_shots <= share_actions + 0.05:
        return [Challenge(q, f"Not disproportionately: {share_actions:.0%} of their play went down the {lane}, and "
                             f"{share_shots:.0%} of their shooting moves passed through it.", "weakened")]
    return [Challenge(q, f"Yes: {share_shots:.0%} of shooting moves passed through the {lane}, from "
                         f"{share_actions:.0%} of their play.", "upheld")]


def challenge_foul(v: MatchView, c: Claim, roster: dict) -> list:
    foul = v.by_id[c.target]
    possessions = []
    for e in v.attack:
        if e["t"] > foul["t"] and e["possession_id"] not in possessions:
            possessions.append(e["possession_id"])
    linked = bool(possessions) and possessions[0] == v.incident["possession_id"]
    gap = v.t_inc - foul["t"]
    changes = sum(1 for p in possessions if p <= v.incident["possession_id"]) - 1
    q = "Did the goal come from the booking's restart?"
    if not linked:
        mins, times = max(round(gap / 60), 1), max(changes, 1)
        out = [Challenge(q, f"No: the booking was at {minute(foul['t'])}; the goal came {mins} minute{'s' * (mins != 1)} later, "
                            f"after {club(v.A)} had lost and regained the ball {times} time{'s' * (times != 1)}. "
                            f"Play reset in between.",
                         "refuted", [c.target, v.incident["id"]])]
    else:
        out = [Challenge(q, "Yes, the goal came straight from the restart, but the restart itself did not "
                            "create the chance.", "weakened", [c.target, v.incident["id"]])]
    cards = [e for e in v.case.events if e["type"] == "card" and e["team"] == v.B]
    goals_after = sum(1 for card in cards for e in v.attack
                      if e["type"] == "shot" and e["outcome"] == "goal" and 0 < e["t"] - card["t"] <= 600)
    out.append(Challenge("How often did a booking precede a goal in this match?",
                         f"{len(cards)} booking(s) for {club(v.B)}; {goals_after} goal(s) followed within 10 minutes.",
                         "upheld"))
    return out


CHALLENGERS = {"FATIGUE": challenge_fatigue, "STATIC": challenge_static, "OVERLOAD": challenge_overload,
               "STYLE": challenge_style, "FOUL": challenge_foul}


def worst_verdict(challenges: list) -> str:
    order = ["upheld", "weakened", "refuted"]
    return max((ch.verdict for ch in challenges), key=order.index, default="upheld")


def review(board: Board, v: MatchView, roster: dict, top_n: int = 4, mode: str = "refute") -> None:
    """Challenge the top claims and record verdicts on the board.

    mode "refute":  only refuted claims lose their ranking; weakened claims lower confidence.
    mode "rescore": weakened claims are discounted and their weight shifts to the alternative.
    "rescore" did not improve recall on development seeds (0.71 vs 0.74), so "refute" is the default.
    """
    shifts = []
    # The top claims, plus the booking whatever its rank: the obvious story is always tested.
    targets = board.ranked()[:top_n]
    targets += [c for c in board.claims if c.kind == "FOUL" and c not in targets]
    for c in targets:
        c.challenges = CHALLENGERS[c.kind](v, c, roster)
        c.status = worst_verdict(c.challenges)
        board.log("sceptic", "challenge", f"{c.kind}({c.target}): {c.status}")
        for ch in c.challenges:
            if ch.shifts_to and ch.verdict != "upheld":
                shifts.append((ch.shifts_to, c.score * SHIFT_SHARE))
    for c in board.claims:
        if mode == "rescore" or c.status == "refuted":
            c.score = c.score * VERDICT_FACTOR[c.status]
    if mode != "rescore":
        return
    for key, amount in shifts:
        target = board.claim(key)
        if target is not None and target.status != "refuted":
            target.score += amount
            board.log("sceptic", "shift", f"evidence moved toward {key[0]}({key[1]})")
