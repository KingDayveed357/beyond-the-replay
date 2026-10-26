"""Match intelligence from the observable event stream: what a broadcast graphics engine needs.

build_timeline() replays events in order and produces:
  - states:  one snapshot per minute (score, possession, shots, xG, passing, pressing, control/chaos,
             tempo, momentum) so a client can show the match "as it happens" at any clock time;
  - moments: key moments with a plain-language headline and why they matter;
  - cues:    timed, machine-readable overlay cues (name tags, speed/distance alerts, stat cards);
  - players: per-player match summaries for player-focus mode.

Everything is computed from observable fields. Nothing here reads hidden simulation state.
"""
from __future__ import annotations

import math
from collections import defaultdict

from phase0.engine import PITCH_X, lane_of

from .models import PassModel, attacks_right, xg

SPRINT_KMH = 31.0          # name tag with speed indicator
POWER_SHOT_KMH = 105.0
DISTANCE_TAGS = (150, 300)  # metres carried with the ball
BIG_CHANCE_XG = 0.25
HARD_PASS = 60             # difficulty rating for "pass of the match" candidates
CUE_SECONDS = 8
SWING_MOMENTUM = 0.6       # ten-minute threat difference that counts as a side being on top


def _minute(t: float) -> int:
    return int(t // 60) + 1


def _progress(e: dict, home: str) -> float:
    return (e["x"] if attacks_right(e["team"], home) else PITCH_X - e["x"]) / PITCH_X


def _blank():
    return {"goals": 0, "shots": 0, "on_target": 0, "xg": 0.0, "passes": 0, "passes_completed": 0,
            "tackles": 0, "interceptions": 0, "fouls": 0, "yellow_cards": 0, "actions": 0, "pressured": 0,
            "final_third": 0, "possession_s": 0.0, "def_actions_high": 0, "opp_passes_deep": 0,
            "turnovers": 0}


def build_timeline(match: dict, model: PassModel) -> dict:
    home, away = match["home"], match["away"]
    roster = match["roster"]
    name = lambda pid: roster.get(pid, {}).get("name", pid) if pid else None
    other = lambda t: away if t == home else home
    events = match["events"]

    totals = {home: _blank(), away: _blank()}
    players = defaultdict(lambda: {"touches": 0, "passes": 0, "passes_completed": 0, "difficulty_sum": 0,
                                   "duels_won": 0, "duels_lost": 0, "tackles": 0, "interceptions": 0, "shots": 0,
                                   "xg": 0.0, "goals": 0, "assists": 0, "top_speed_kmh": 0.0, "carry_m": 0.0})
    enriched, moments, cues = [], [], []
    states = []
    window = []                       # (t, team, threat, is_turnover, is_pass)
    poss_bounds = {}                  # possession_id -> [team, first_t, last_t]
    last_pass_by_poss = {}
    distance_tagged = defaultdict(set)
    speed_tagged = set()
    next_minute = 1
    last_swing_t = -1e9
    last_momentum = None   # which side held momentum last

    def snapshot(minute: int):
        nonlocal last_momentum, last_swing_t
        t_now = minute * 60
        recent = [w for w in window if t_now - w[0] <= 600]
        threat = {home: 0.0, away: 0.0}
        for w in recent:
            threat[w[1]] += w[2]
        momentum = round(threat[home] - threat[away], 3)
        poss = {k: v["possession_s"] for k, v in totals.items()}
        poss_total = sum(poss.values()) or 1
        ft_total = (totals[home]["final_third"] + totals[away]["final_third"]) or 1
        passes_recent = sum(1 for w in recent if w[4])
        turnovers_recent = sum(1 for w in recent if w[3])
        span = max(min(t_now, 600), 60) / 60
        team_view = {}
        for team, v in totals.items():
            completion = v["passes_completed"] / v["passes"] if v["passes"] else 0
            share = poss[team] / poss_total
            tilt = v["final_third"] / ft_total
            ppda = round(totals[other(team)]["opp_passes_deep"] / v["def_actions_high"], 1) if v["def_actions_high"] else None
            team_view[team] = {
                "goals": v["goals"], "shots": v["shots"], "on_target": v["on_target"], "xg": round(v["xg"], 2),
                "possession": round(100 * share), "pass_accuracy": round(100 * completion),
                "passes": v["passes"], "tackles": v["tackles"], "interceptions": v["interceptions"],
                "fouls": v["fouls"], "yellow_cards": v["yellow_cards"], "field_tilt": round(100 * tilt),
                "pressured_share": round(100 * v["pressured"] / v["actions"]) if v["actions"] else 0,
                "ppda": ppda,
                # Control: keeping the ball, keeping it cleanly, and keeping it high up the pitch.
                "control": round(100 * (0.4 * share + 0.3 * completion + 0.3 * tilt)),
            }
        chaos = min(100, round(100 * (turnovers_recent / span) / 6))
        states.append({"minute": minute, "teams": team_view, "momentum": momentum,
                       "tempo_passes_per_min": round(passes_recent / span, 1),
                       "turnovers_per_min": round(turnovers_recent / span, 2), "chaos": chaos})
        # A swing: the side on top over the last ten minutes changes decisively (at most every 8 minutes).
        if abs(momentum) >= SWING_MOMENTUM:
            leader = home if momentum > 0 else away
            if leader != last_momentum and minute >= 10 and t_now - last_swing_t >= 480:
                verb = "take control" if last_momentum is None else "turn the tide"
                moments.append({"t": t_now, "minute": minute, "type": "momentum", "team": leader, "player_id": None,
                                "variant": "take" if last_momentum is None else "turn",
                                "importance": min(1.0, abs(momentum)),
                                "headline": f"{match.get('names', {}).get(leader, leader)} {verb}",
                                "why": "They have created clearly more threat than their opponents over the last ten minutes."})
                last_swing_t = t_now
            if leader != last_momentum and (minute >= 10 or last_momentum is None):
                last_momentum = leader

    for e in events:
        while e["t"] >= next_minute * 60:
            snapshot(next_minute)
            next_minute += 1
        team, pid = e["team"], e["player_id"]
        tv = totals[team]
        out = dict(e)
        p = players[pid]
        if e["possession_id"]:
            b = poss_bounds.setdefault(e["possession_id"], [team, e["t"], e["t"]])
            if b[0] == team:
                tv["possession_s"] += max(e["t"] - b[2], 0) + (3.0 if b[1] == b[2] == e["t"] else 0)
                b[2] = e["t"]
        threat, turnover, is_pass = 0.0, False, False

        if e["type"] in ("pass", "carry", "dribble", "cross", "shot"):
            tv["actions"] += 1
            p["touches"] += 1
            if e["under_pressure"]:
                tv["pressured"] += 1
            if _progress(e, home) > 2 / 3:
                tv["final_third"] += 1
                threat += 0.03
            if e["type"] in ("pass", "carry", "dribble", "cross") and e["outcome"] == "fail":
                turnover = True
                tv["turnovers"] += 1
        if e["type"] == "pass":
            is_pass = True
            tv["passes"] += 1
            p["passes"] += 1
            diff = model.difficulty(e, home)
            out["pass_difficulty"] = diff
            out["pass_distance_m"] = round(math.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"]), 1)
            p["difficulty_sum"] += diff
            if _progress(e, home) < 0.6:
                totals[team]["opp_passes_deep"] += 1
            if e["outcome"] == "success":
                tv["passes_completed"] += 1
                p["passes_completed"] += 1
                last_pass_by_poss[e["possession_id"]] = e
                if diff >= HARD_PASS and out["pass_distance_m"] >= 25:
                    moments.append({"t": e["t"], "minute": _minute(e["t"]), "type": "pass", "team": team, "player_id": pid,
                                    "receiver_id": e["receiver_id"], "distance_m": out["pass_distance_m"], "difficulty": diff,
                                    "importance": 0.35, "event_id": e["id"],
                                    "headline": f"{name(pid)} finds {name(e['receiver_id'])} with a {out['pass_distance_m']:.0f} m pass",
                                    "why": f"Rated {diff}/100 for difficulty: most passes like it don't arrive."})
        if e["type"] == "cross" and e["outcome"] == "success":
            last_pass_by_poss[e["possession_id"]] = e
        if e["type"] in ("carry", "dribble") and e["outcome"] == "success" and e["end_x"] is not None:
            p["carry_m"] += math.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"])
            for mark in DISTANCE_TAGS:
                if p["carry_m"] >= mark and mark not in distance_tagged[pid]:
                    distance_tagged[pid].add(mark)
                    cues.append({"t_in": e["t"], "t_out": e["t"] + CUE_SECONDS, "kind": "name_tag", "priority": 2,
                                 "team": team, "player_id": pid, "player": name(pid),
                                 "metric": "distance_carried_m", "value": mark,
                                 "text": f"{name(pid)}: {mark} m carried with the ball"})
        if e["type"] in ("carry", "dribble") and e["speed_kmh"]:
            p["top_speed_kmh"] = max(p["top_speed_kmh"], e["speed_kmh"])
            half = 1 if e["t"] < 45 * 60 else 2
            if e["speed_kmh"] >= SPRINT_KMH and (pid, half) not in speed_tagged:
                speed_tagged.add((pid, half))
                cues.append({"t_in": e["t"], "t_out": e["t"] + CUE_SECONDS, "kind": "name_tag", "priority": 2,
                             "team": team, "player_id": pid, "player": name(pid), "metric": "speed_kmh",
                             "value": e["speed_kmh"], "text": f"{name(pid)}: {e['speed_kmh']:.1f} km/h"})
        if e["type"] == "dribble":
            if e["outcome"] == "success":
                p["duels_won"] += 1
                players[e["opponent_id"]]["duels_lost"] += 1
            else:
                p["duels_lost"] += 1
                players[e["opponent_id"]]["duels_won"] += 1
        if e["type"] in ("tackle", "interception"):
            key = "tackles" if e["type"] == "tackle" else "interceptions"
            tv[key] += 1
            p[key] += 1
            # Pressing uses interceptions and fouls: the engine logs every lost one-on-one as a tackle,
            # far more than real tackle counts, which would make pressing look implausibly intense.
            if e["type"] == "interception" and _progress(e, home) > 0.4:
                tv["def_actions_high"] += 1
        if e["type"] == "foul":
            tv["fouls"] += 1
            if _progress(e, home) > 0.4:
                tv["def_actions_high"] += 1
        if e["type"] == "card":
            tv["yellow_cards"] += 1
            moments.append({"t": e["t"], "minute": _minute(e["t"]), "type": "card", "team": team, "player_id": pid,
                            "importance": 0.45, "event_id": e["id"], "headline": f"Yellow card: {name(pid)}",
                            "why": "A booked player has to be more careful in every duel from here."})
        if e["type"] == "shot":
            right = attacks_right(team, home)
            header = e["speed_kmh"] is not None and e["speed_kmh"] < 66 and _progress(e, home) > 0.9
            q = xg(e["x"], e["y"], right, header)
            out["xg"] = q
            tv["shots"] += 1
            tv["xg"] += q
            p["shots"] += 1
            p["xg"] += q
            threat += q
            if e["outcome"] in ("goal", "saved"):
                tv["on_target"] += 1
            if e["speed_kmh"] and e["speed_kmh"] >= POWER_SHOT_KMH:
                cues.append({"t_in": e["t"], "t_out": e["t"] + CUE_SECONDS, "kind": "speed", "priority": 3, "team": team,
                             "player_id": pid, "player": name(pid), "metric": "shot_speed_kmh", "value": e["speed_kmh"],
                             "text": f"Shot speed: {e['speed_kmh']:.0f} km/h"})
            if e["outcome"] == "goal":
                tv["goals"] += 1
                p["goals"] += 1
                assist = last_pass_by_poss.get(e["possession_id"])
                assist_pid = assist["player_id"] if assist and assist["receiver_id"] == pid else None
                if assist_pid:
                    players[assist_pid]["assists"] += 1
                score = f"{totals[home]['goals']}-{totals[away]['goals']}"
                moments.append({"t": e["t"], "minute": _minute(e["t"]), "type": "goal", "team": team, "player_id": pid,
                                "assist_id": assist_pid, "importance": 1.0, "event_id": e["id"], "score": score,
                                "xg": q, "headline": f"GOAL: {name(pid)}" + (f", assisted by {name(assist_pid)}" if assist_pid else ""),
                                "why": f"A {q:.2f} xG chance: " + ("a big chance taken." if q >= BIG_CHANCE_XG
                                                                  else "a low-probability finish.")})
            elif q >= BIG_CHANCE_XG:
                moments.append({"t": e["t"], "minute": _minute(e["t"]), "type": "big_chance", "team": team, "player_id": pid,
                                "outcome": e["outcome"],
                                "importance": 0.6, "event_id": e["id"], "xg": q,
                                "headline": f"Big chance: {name(pid)} " + ("is denied" if e["outcome"] == "saved" else "misses"),
                                "why": f"Worth {q:.2f} expected goals: chances like it are scored about {round(q * 100)}% of the time."})
        window.append((e["t"], team, threat, turnover, is_pass))
        enriched.append(out)

    while next_minute <= max(95, _minute(events[-1]["t"])):
        snapshot(next_minute)
        next_minute += 1
        if next_minute > _minute(events[-1]["t"]) + 1:
            break

    for m in moments:  # every key moment also becomes an overlay cue
        cues.append({"t_in": m["t"], "t_out": m["t"] + CUE_SECONDS, "kind": "lower_third" if m["type"] != "goal" else "goal",
                     "priority": 4 if m["type"] == "goal" else 3, "team": m["team"], "player_id": m.get("player_id"),
                     "text": m["headline"], "subtext": m["why"]})
    cues.sort(key=lambda c: (c["t_in"], -c["priority"]))
    moments.sort(key=lambda m: m["t"])

    summaries = {}
    for pid, p in players.items():
        if pid not in roster:
            continue
        summaries[pid] = p | {"name": name(pid), "team": roster[pid]["team"], "role": roster[pid]["role"],
                              "xg": round(p["xg"], 2), "carry_m": round(p["carry_m"]), "top_speed_kmh": round(p["top_speed_kmh"], 1),
                              "pass_accuracy": round(100 * p["passes_completed"] / p["passes"]) if p["passes"] else None,
                              "avg_pass_difficulty": round(p["difficulty_sum"] / p["passes"]) if p["passes"] else None}
    return {"events": enriched, "states": states, "moments": moments, "cues": cues, "players": summaries}
