"""Phase 0 experiment: can a hidden cause be recovered from observable events, non-trivially?

Usage:  python -m phase0.evaluate --dev 40 --test 80 --k 80

Development seeds are used to tune engine strengths and fit the investigator's five weights.
Held-out seeds are evaluated once. Results go to results/phase0.json and results/phase0.md.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import time
from dataclasses import asdict, dataclass

from .engine import make_config, roster, simulate
from .investigators import (MatchView, StatInvestigator, candidate_keys, fit_weights, lane_shortcut,
                            random_ranking, salience, verify)
from .observe import HIDDEN_TERMS, Case, project, validate_events
from .truth import Truth, measure

DEV_START, TEST_START = 1, 100_001
ONSET_TOLERANCE = 10 * 60


@dataclass
class Record:
    case: Case
    truth: Truth
    factor_kind: str
    factor_onset: int
    decoy_key: tuple
    realism: dict


def realism_stats(events: list, goals: list) -> dict:
    passes = [e for e in events if e["type"] == "pass"]
    return {
        "events": len(events),
        "goals": len(goals),
        "shots": sum(1 for e in events if e["type"] == "shot"),
        "pass_completion": sum(1 for e in passes if e["outcome"] == "success") / max(len(passes), 1),
        "possessions": len({e["possession_id"] for e in events if e["possession_id"]}),
        "fouls": sum(1 for e in events if e["type"] == "foul"),
    }


def build_record(args) -> Record | None:
    seed, k = args
    cfg = make_config(seed)
    result = simulate(cfg)
    if not result.decoy_ids:
        return None
    decoy_t = next(e["t"] for e in result.events if e["id"] == result.decoy_ids[0])
    goal = next(((t, eid) for t, team, eid in result.goals if team == cfg.beneficiary and t > decoy_t), None)
    if goal is None:
        return None
    events = project(result.events)
    case = Case(f"m{seed}", cfg.home, cfg.away, roster(cfg), events, goal[1])
    validate_events(case.events, case.roster)
    truth = measure(cfg, goal[0], k)
    return Record(case, truth, cfg.factor.kind, cfg.factor.onset, ("FOUL", result.decoy_ids[0]),
                  realism_stats(result.events, result.goals))


def build_records(start: int, n: int, k: int, workers: int) -> list:
    out, seed = [], start
    with mp.Pool(workers) as pool:
        while len(out) < n and seed < start + n * 6:
            batch = [(s, k) for s in range(seed, seed + workers * 2)]
            seed += len(batch)
            for rec in pool.map(build_record, batch):
                if rec is not None and len(out) < n:
                    out.append(rec)
            print(f"  {len(out)}/{n} cases (seeds tried up to {seed - 1})", flush=True)
    return out


def score(name: str, rankings: dict, records: list) -> dict:
    labelled = [r for r in records if r.truth.label]
    r1 = r3 = strict = 0
    for r in labelled:
        hyps = rankings[r.case.case_id]
        keys = [h.key for h in hyps[:3]]
        hit1 = bool(keys) and keys[0] == r.truth.label
        r1 += hit1
        r3 += r.truth.label in keys
        if hit1:
            top = hyps[0]
            needs_onset = r.truth.label == r.truth.planted_key
            strict += (not needs_onset) or (top.onset is not None and abs(top.onset - r.factor_onset) <= ONSET_TOLERANCE)
    decoy_top = sum(1 for r in records if rankings[r.case.case_id] and rankings[r.case.case_id][0].kind == "FOUL")
    claims = unsupported = 0
    link_fracs = []
    for r in records:
        view = MatchView(r.case)
        for h in rankings[r.case.case_id][:3]:
            ok, frac, _ = verify(h, view)
            claims += 1
            unsupported += not ok
            link_fracs.append(frac)
    n = max(len(labelled), 1)
    by_kind = {}
    for kind in ("FATIGUE", "OVERLOAD", "STATIC", "STYLE"):
        sub = [r for r in labelled if r.truth.label[0] == kind]
        if sub:
            by_kind[kind] = {"n": len(sub), "recall@1": sum(
                1 for r in sub if rankings[r.case.case_id] and rankings[r.case.case_id][0].key == r.truth.label) / len(sub)}
    # Mean recall@1 across label kinds with at least 3 cases, so "always answer FATIGUE" cannot score well.
    macro = [v["recall@1"] for v in by_kind.values() if v["n"] >= 3]
    return {
        "investigator": name, "n_cases": len(records), "n_labelled": len(labelled),
        "recall@1": r1 / n, "recall@3": r3 / n, "recall@1_strict_onset": strict / n,
        "macro_recall@1": statistics.fmean(macro) if macro else 0.0,
        "decoy_rejection": 1 - decoy_top / max(len(records), 1),
        "unsupported_claim_rate": unsupported / max(claims, 1),
        "evidence_link_correctness": statistics.fmean(link_fracs) if link_fracs else 0.0,
        "by_label_kind": by_kind,
    }


def leak_check(records: list) -> list:
    problems = []
    for r in records:
        blob = json.dumps(r.case.events).lower()
        problems += [f"{r.case.case_id}: '{term}' in observable stream" for term in HIDDEN_TERMS if term in blob]
    return problems


def describe(r: Record, hyps: list) -> dict:
    view = MatchView(r.case)
    return {
        "case": r.case.case_id,
        "teams": f"{r.case.home} v {r.case.away}",
        "goal": f"{r.case.incident_id} by {view.A} at {view.t_inc / 60:.1f}'",
        "truth_label": r.truth.label,
        "planted": r.truth.planted_key,
        "measured_effects": [(e.variable, e.key, round(e.mean, 3), round(e.se, 3)) for e in r.truth.effects],
        "but_for": r.truth.but_for,
        "top3": [(h.kind, h.target, round(h.score, 2), round(h.onset / 60) if h.onset else None) for h in hyps[:3]],
        "top1_cited": hyps[0].cited[:5] if hyps else [],
        "evidence_sample": [view.by_id[c] for c in (hyps[0].cited[:3] if hyps else [])],
    }


def run_all(records: list, weights: dict) -> dict:
    stat = StatInvestigator(weights)
    unfit = StatInvestigator()
    rankings = {
        "random": {r.case.case_id: random_ranking(r.case, i) for i, r in enumerate(records)},
        "salience": {r.case.case_id: salience(r.case) for r in records},
        "lane_shortcut": {r.case.case_id: lane_shortcut(r.case) for r in records},
        "stat_unfitted": {r.case.case_id: unfit.investigate(r.case) for r in records},
        "stat_fitted": {r.case.case_id: stat.investigate(r.case) for r in records},
    }
    return rankings


def gates(test_scores: dict, test_records: list, leaks: list) -> dict:
    stat, sal, lane = test_scores["stat_fitted"], test_scores["salience"], test_scores["lane_shortcut"]
    labelled_share = stat["n_labelled"] / max(stat["n_cases"], 1)
    return {
        "G0_no_leakage": {"pass": not leaks, "detail": leaks[:5]},
        "G1_truth_is_meaningful": {"pass": labelled_share >= 0.6,
                                   "detail": f"{labelled_share:.0%} of cases have a clear measured cause (need >= 60%)"},
        "G2_learnable": {"pass": stat["recall@1"] >= 0.5 and stat["recall@3"] >= 0.75 and stat["macro_recall@1"] >= 0.5,
                         "detail": f"stat recall@1 {stat['recall@1']:.2f} (>=0.50), recall@3 {stat['recall@3']:.2f} (>=0.75), "
                                   f"class-balanced recall@1 {stat['macro_recall@1']:.2f} (>=0.50)"},
        "G3_not_trivial": {"pass": sal["recall@1"] <= 0.35 and stat["recall@1"] - lane["recall@1"] >= 0.15,
                           "detail": f"salience recall@1 {sal['recall@1']:.2f} (<=0.35); stat minus lane-shortcut "
                                     f"{stat['recall@1'] - lane['recall@1']:+.2f} (>=+0.15)"},
        "G4_headroom": {"pass": stat["recall@1"] <= 0.9,
                        "detail": f"stat recall@1 {stat['recall@1']:.2f}; above 0.90 leaves agents nothing to add"},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", type=int, default=40)
    ap.add_argument("--test", type=int, default=80)
    ap.add_argument("--k", type=int, default=80, help="paired re-runs per hidden variable")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default="results")
    ap.add_argument("--dev-only", action="store_true", help="tune on development seeds without touching held-out ones")
    args = ap.parse_args()
    started = time.perf_counter()

    print(f"Building {args.dev} development cases ...")
    dev = build_records(DEV_START, args.dev, args.k, args.workers)
    if args.dev_only:
        weights = fit_weights([StatInvestigator().evidence(r.case) for r in dev], [r.truth.label for r in dev])
        scores = {n: score(n, rk, dev) for n, rk in run_all(dev, weights).items()}
        labelled = [r for r in dev if r.truth.label]
        print(json.dumps({"weights": weights, "labelled": len(labelled), "cases": len(dev),
                          "label_is_planted": sum(r.truth.label == r.truth.planted_key for r in labelled),
                          "planted_effect_by_kind": {kind: [round(next(e.mean for e in r.truth.effects if e.variable == "factor"), 2)
                                                            for r in dev if r.factor_kind == kind]
                                                     for kind in ("fatigue", "overload")},
                          "labels": [r.truth.label[0] if r.truth.label else None for r in dev],
                          "realism": {k: round(statistics.fmean(r.realism[k] for r in dev), 3) for k in dev[0].realism},
                          "gates_on_dev": gates(scores, dev, leak_check(dev)),
                          "scores": {n: {k: v for k, v in s.items() if k != "by_label_kind"} | {"by_kind": s["by_label_kind"]}
                                     for n, s in scores.items()}}, indent=1, default=str))
        return
    print(f"Building {args.test} held-out cases ...")
    test = build_records(TEST_START, args.test, args.k, args.workers)
    build_s = time.perf_counter() - started

    weights = fit_weights([StatInvestigator().evidence(r.case) for r in dev], [r.truth.label for r in dev])
    dev_scores = {n: score(n, rk, dev) for n, rk in run_all(dev, weights).items()}
    test_rankings = run_all(test, weights)
    test_scores = {n: score(n, rk, test) for n, rk in test_rankings.items()}

    llm_status = "see results/slice3_agents.json (python -m investigation.evaluate_agents)"

    leaks = leak_check(dev + test)
    gate = gates(test_scores, test, leaks)
    stat_rank = test_rankings["stat_fitted"]
    labelled = [r for r in test if r.truth.label]
    successes = [describe(r, stat_rank[r.case.case_id]) for r in labelled
                 if stat_rank[r.case.case_id][0].key == r.truth.label][:2]
    failures = [describe(r, stat_rank[r.case.case_id]) for r in labelled
                if stat_rank[r.case.case_id][0].key != r.truth.label][:3]
    ambiguous = [describe(r, stat_rank[r.case.case_id]) for r in test if not r.truth.label][:2]

    real = [r.realism for r in dev + test]
    realism = {k: round(statistics.fmean(x[k] for x in real), 3) for k in real[0]}
    truth_stats = {
        "labelled": len(labelled), "ambiguous": len(test) - len(labelled),
        "label_is_planted_factor": sum(1 for r in labelled if r.truth.label == r.truth.planted_key),
        "label_kinds": {k: sum(1 for r in labelled if r.truth.label[0] == k) for k in ("FATIGUE", "OVERLOAD", "STATIC", "STYLE")},
        "planted_effect_mean": round(statistics.fmean(
            next(e.mean for e in r.truth.effects if e.variable == "factor") for r in test), 3),
        "but_for_rate": round(sum(r.truth.but_for for r in test) / len(test), 3),
        "candidates_per_case": round(statistics.fmean(len(candidate_keys(MatchView(r.case))) for r in test), 2),
    }
    report = {
        "args": vars(args), "build_seconds": round(build_s, 1), "fitted_weights": weights,
        "realism_mean_per_match": realism, "truth": truth_stats, "dev_scores": dev_scores,
        "test_scores": test_scores, "llm_only": llm_status, "gates": gate,
        "examples": {"successes": successes, "failures": failures, "ambiguous": ambiguous},
    }
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "phase0.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    with open(os.path.join(args.out, "phase0.md"), "w", encoding="utf-8") as f:
        f.write(render_markdown(report))
    print(render_markdown(report))


def render_markdown(rep: dict) -> str:
    cols = ("recall@1", "recall@3", "recall@1_strict_onset", "decoy_rejection",
            "unsupported_claim_rate", "evidence_link_correctness")
    lines = ["# Phase 0 results", "",
             f"Held-out cases: {rep['truth']['labelled'] + rep['truth']['ambiguous']} "
             f"({rep['truth']['labelled']} with a clear measured cause). Paired re-runs per variable: {rep['args']['k']}.", "",
             "| investigator | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for name, s in rep["test_scores"].items():
        lines.append(f"| {name} | " + " | ".join(f"{s[c]:.2f}" for c in cols) + " |")
    lines += ["", f"LLM-only baseline: {rep['llm_only']}", "", "## Gates", ""]
    for g, v in rep["gates"].items():
        lines.append(f"- **{g}**: {'PASS' if v['pass'] else 'FAIL'} — {v['detail']}")
    lines += ["", "## Ground truth", "", "```", json.dumps(rep["truth"], indent=2), "```",
              "", "## Engine realism (mean per match)", "", "```", json.dumps(rep["realism_mean_per_match"], indent=2), "```",
              "", f"Fitted weights: `{rep['fitted_weights']}`", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
