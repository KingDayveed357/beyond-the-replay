"""Slice 2 ablation: does the sceptic improve the investigation?

Sceptic thresholds are tuned on development seeds only. The comparison is reported on a fresh
held-out range (200001+) that neither the Phase 0 investigator nor the sceptic has seen.

Usage:  python -m investigation.evaluate_workflow --dev 40 --test 80 --k 120
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import statistics

from phase0.evaluate import DEV_START, build_records, score
from phase0.investigators import Hypothesis, StatInvestigator, fit_weights

from .workflow import investigate

FRESH_TEST_START = 200_001


def cached_records(start: int, n: int, k: int, workers: int, cache_dir: str) -> list:
    from phase0.engine import ENGINE_VERSION, LEAGUE
    identity = "pl" if LEAGUE else "fictional"
    path = os.path.join(cache_dir, f"records_{ENGINE_VERSION}_{identity}_{start}_{n}_{k}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    records = build_records(start, n, k, workers)
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(records, f)
    return records


def workflow_rankings(records: list, weights: dict, use_sceptic: bool, mode: str = "refute") -> tuple:
    rankings, latencies, grounded = {}, [], 0
    for r in records:
        out = investigate(r.case, use_sceptic=use_sceptic, weights=weights, sceptic_mode=mode)
        latencies.append(out["elapsed_ms"])
        grounded += "problems" not in out["explanation"]
        rankings[r.case.case_id] = [
            Hypothesis(c["kind"], c["target"], c["score"], c["onset"], c["cited"])
            for c in out["claims"] if c["verified"]
        ]
    return rankings, {"median_ms": statistics.median(latencies), "max_ms": max(latencies),
                      "grounded_explanations": grounded / len(records)}


def compare(records: list, weights: dict) -> dict:
    out = {}
    variants = (("investigator_only", False, "refute"), ("sceptic_refute (default)", True, "refute"),
                ("sceptic_rescore", True, "rescore"))
    for name, sceptic, mode in variants:
        rankings, perf = workflow_rankings(records, weights, sceptic, mode)
        out[name] = score(name, rankings, records) | perf
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", type=int, default=40)
    ap.add_argument("--test", type=int, default=80)
    ap.add_argument("--k", type=int, default=120)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--dev-only", action="store_true")
    ap.add_argument("--cache", default=".cache")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    dev = cached_records(DEV_START, args.dev, args.k, args.workers, args.cache)
    weights = fit_weights([StatInvestigator().evidence(r.case) for r in dev], [r.truth.label for r in dev])
    report = {"weights": weights, "dev": compare(dev, weights)}
    if not args.dev_only:
        test = cached_records(FRESH_TEST_START, args.test, args.k, args.workers, args.cache)
        report["fresh_test"] = compare(test, weights)
        report["fresh_test_truth"] = {
            "cases": len(test), "labelled": sum(1 for r in test if r.truth.label),
            "label_kinds": {k: sum(1 for r in test if r.truth.label and r.truth.label[0] == k)
                            for k in ("FATIGUE", "OVERLOAD", "STATIC", "STYLE")},
        }
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "slice2_sceptic.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

    cols = ("recall@1", "recall@3", "macro_recall@1", "decoy_rejection", "unsupported_claim_rate", "median_ms")
    for split in ("dev", "fresh_test"):
        if split not in report:
            continue
        print(f"\n## {split}")
        print("| variant | " + " | ".join(cols) + " | by kind |")
        for name, s in report[split].items():
            kinds = ", ".join(f"{k} {v['recall@1']:.2f} (n={v['n']})" for k, v in s["by_label_kind"].items())
            print(f"| {name} | " + " | ".join(f"{s[c]:.2f}" for c in cols) + f" | {kinds} |")
    if "fresh_test_truth" in report:
        print(report["fresh_test_truth"])


if __name__ == "__main__":
    main()
