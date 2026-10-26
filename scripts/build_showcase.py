"""Precompute the matches the app ships with.

Showcase seeds (300001+) are disjoint from development (1+) and both held-out ranges. Selection
is rule-based and printed, and deliberately includes a case the investigator gets wrong and an
ambiguous one, so the product never only shows its best side.

Usage:  python scripts/build_showcase.py --n 30 --k 120
"""
import argparse
import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from investigation.evaluate_workflow import cached_records  # noqa: E402
from investigation.workflow import investigate  # noqa: E402
from phase0.engine import CLUBS, LEAGUE, make_config, metadata  # noqa: E402
from phase0.investigators import MatchView  # noqa: E402

SHOWCASE_START = 300_001


def stature(r) -> int:
    """Lower is a bigger fixture: sum of both clubs' 2024/25 league positions."""
    if not LEAGUE:
        return 0
    return sum(LEAGUE["clubs"][t]["season_2024_25"]["position"] for t in (r.case.home, r.case.away))


def booking_gap(r) -> float:
    v = MatchView(r.case)
    return (v.t_inc - v.last_foul["t"]) / 60 if v.last_foul else 99.0


def pick(records):
    labelled = [(r, investigate(r.case)) for r in records if r.truth.label]
    right = [(r, o) for r, o in labelled if tuple(o["ranking"][0]) == r.truth.label]
    wrong = [(r, o) for r, o in labelled if tuple(o["ranking"][0]) != r.truth.label]
    chosen, roles = [], []

    def take(pool, role, key=None):
        pool = [p for p in pool if p[0] not in chosen]
        if key:
            pool.sort(key=key)
        if pool:
            chosen.append(pool[0][0])
            roles.append(role)

    take([p for p in right if p[0].truth.label[0] == "FATIGUE" and p[1]["explanation"]["confidence"] == "strong"],
         "hero", key=lambda p: (stature(p[0]), booking_gap(p[0])))
    take([p for p in right if p[0].truth.label[0] == "OVERLOAD"], "overload", key=lambda p: booking_gap(p[0]))
    take([p for p in right if p[0].truth.label[0] == "FATIGUE"], "fatigue", key=lambda p: booking_gap(p[0]))
    take(wrong, "miss", key=lambda p: booking_gap(p[0]))
    ambiguous = [(r, None) for r in records if not r.truth.label]
    take(ambiguous, "ambiguous", key=lambda p: booking_gap(p[0]))
    return list(zip(chosen, roles))


def score_line(r):
    goals = [e for e in r.case.events if e["type"] == "shot" and e["outcome"] == "goal"]
    return {team: sum(1 for g in goals if g["team"] == team) for team in (r.case.home, r.case.away)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--k", type=int, default=120)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    records = cached_records(SHOWCASE_START, args.n, args.k, args.workers, ".cache")
    os.makedirs(os.path.join(args.out, "matches"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "truth"), exist_ok=True)
    index = []
    for r, role in pick(records):
        v = MatchView(r.case)
        mid = r.case.case_id
        goals = [e for e in r.case.events if e["type"] == "shot" and e["outcome"] == "goal"]
        meta = {
            "id": mid, "role": role, "home": r.case.home, "away": r.case.away,
            "home_name": CLUBS[r.case.home], "away_name": CLUBS[r.case.away], "score": score_line(r),
            "incident_id": r.case.incident_id, "incident_minute": int(v.t_inc // 60) + 1,
            "incident_team": v.A, "booking_id": v.last_foul["id"] if v.last_foul else None,
            "booking_minute": int(v.last_foul["t"] // 60) + 1 if v.last_foul else None,
            "goals": [{"id": g["id"], "team": g["team"], "player_id": g["player_id"], "minute": int(g["t"] // 60) + 1}
                      for g in goals],
            "synthetic": True,
            "metadata": metadata(make_config(int(mid[1:]))),
        }
        with open(os.path.join(args.out, "matches", f"{mid}.json"), "w", encoding="utf-8") as f:
            json.dump(meta | {"roster": r.case.roster, "events": r.case.events}, f)
        truth = asdict(r.truth) | {"factor_onset_minute": r.factor_onset // 60 + 1, "decoy_key": list(r.decoy_key),
                                   "evaluation_only": True}
        with open(os.path.join(args.out, "truth", f"{mid}.json"), "w", encoding="utf-8") as f:
            json.dump(truth, f, default=list)
        index.append(meta)
        print(f"{role:9s} {mid}  {meta['home_name']} {meta['score'][r.case.home]}-{meta['score'][r.case.away]} "
              f"{meta['away_name']}  goal {meta['incident_minute']}'  booking {meta['booking_minute']}'  truth {r.truth.label}")
    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1)


if __name__ == "__main__":
    main()
