"""Slice 3: do the Claude agents beat the deterministic workflow and an LLM-only baseline?

Runs on the fresh held-out matches (seeds 200001+) already cached by evaluate_workflow. Results are
appended per case (resumable) and the run stops at a hard estimated-spend cap of its own.

Usage:  python -m investigation.evaluate_agents --cap 1.00 --workers 3
        python -m investigation.evaluate_agents --start 400001 --n 30 --variants agents --tag tune --budget-file results/tuning_spend.json --cap 0.95
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from phase0 import llm as llm_only
from phase0.evaluate import score
from phase0.investigators import Hypothesis

from .evaluate_workflow import FRESH_TEST_START, cached_records, workflow_rankings
from .llm.agents import PROMPT_VERSION, run_agents
from .llm.provider import Provider, ProviderError, load_dotenv
from .workflow import DEFAULT_WEIGHTS

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--cap", type=float, default=1.00, help="stop starting new cases above this estimated spend (USD)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default="results")
    ap.add_argument("--start", type=int, default=FRESH_TEST_START, help="first seed of the match set")
    ap.add_argument("--variants", default="agents,llm_only")
    ap.add_argument("--tag", default="fresh", help="names the log and report files")
    ap.add_argument("--labelled-only", action="store_true", help="skip ambiguous matches (they do not count towards recall)")
    ap.add_argument("--budget-file", default=None, help="JSON file tracking spend shared across several runs; --cap applies to its total")
    args = ap.parse_args()
    variants = [v for v in args.variants.split(",") if v]
    load_dotenv(ROOT / ".env")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    records = cached_records(args.start, args.n, 120, 7, str(ROOT / ".cache"))
    if args.labelled_only:
        records = [r for r in records if r.truth.label]
    log_path = Path(args.out) / f"agents_{args.tag}_{PROMPT_VERSION}.jsonl"
    budget_path = Path(args.budget_file) if args.budget_file else None
    prior = json.loads(budget_path.read_text())["spent_usd"] if budget_path and budget_path.exists() else 0.0
    done = {}
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[(row["case"], row["variant"])] = row
    lock = threading.Lock()
    already = sum(r.get("cost", 0.0) for r in done.values())
    spent = [prior if budget_path else already]

    def run_one(rec, variant):
        if (rec.case.case_id, variant) in done:
            return
        with lock:
            if spent[0] >= args.cap:
                return
        provider = Provider(key, "claude-haiku-5-5", "server")
        row = {"case": rec.case.case_id, "variant": variant}
        try:
            if variant == "agents":
                out = run_agents(rec.case, provider)
                row["ranking"] = [[c["kind"], c["target"], c["onset"], c["cited"]] for c in out["claims"] if c["verified"]]
                row["proposed"] = len(out["claims"])
                row["claims"] = [[c["kind"], c["target"], c["status"], c["verified"], c["onset"]] for c in out["claims"]]
                row["tools"] = [s["detail"] for s in out["trace"] if s["action"] == "tools"]
                row["producer_source"] = out["producer_source"]
                row["audit"] = out["audit"]
            else:
                hyps = llm_only.investigate(rec.case, provider)
                row["ranking"] = [[h.kind, h.target, h.onset, h.cited] for h in hyps]
        except ProviderError as exc:
            row["error"] = exc.code
        row["cost"] = provider.usage.cost_usd_estimate
        row["calls"] = provider.usage.calls
        row["tokens"] = provider.usage.input_tokens + provider.usage.output_tokens
        with lock:
            spent[0] += row["cost"]
            done[(row["case"], variant)] = row
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(f"{len(done):4d} {variant:8s} {row['case']} {row.get('error', 'ok')} ${spent[0]:.3f}", flush=True)

    os.makedirs(args.out, exist_ok=True)
    jobs = [(r, v) for r in records for v in variants]
    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(lambda j: run_one(*j), jobs))
    if budget_path:
        budget_path.write_text(json.dumps({"spent_usd": round(spent[0], 5), "cap_usd": args.cap}))

    report = {"prompt_version": PROMPT_VERSION, "model": "claude-haiku-5-5", "spent_usd_estimate": round(spent[0], 4),
              "n_cases": len(records), "variants": {}}
    det, _ = workflow_rankings(records, DEFAULT_WEIGHTS, True, "refute")
    report["variants"]["deterministic (shipped)"] = score("deterministic", det, records)
    for variant in variants:
        rows = {c: r for (c, v), r in done.items() if v == variant}
        complete = [r for r in records if r.case.case_id in rows]
        rankings = {r.case.case_id: [Hypothesis(k, t, 1.0, o, cited) for k, t, o, cited in rows[r.case.case_id].get("ranking", [])]
                    for r in complete}
        s = score(variant, rankings, complete)
        vals = list(rows.values())
        s |= {"completed": len(complete), "errors": sum("error" in r for r in vals),
              "mean_cost_usd": round(statistics.fmean(r["cost"] for r in vals), 5) if vals else None,
              "mean_calls": round(statistics.fmean(r["calls"] for r in vals), 2) if vals else None}
        if variant == "agents":
            s["template_fallbacks"] = sum(r.get("producer_source") == "template" for r in vals)
            s["citations_dropped"] = sum(r.get("audit", {}).get("citations_dropped", 0) for r in vals)
            proposed = sum(r.get("proposed", 0) for r in vals)
            caught = sum(r.get("audit", {}).get("unverified_claims", 0) for r in vals)
            # unsupported_claim_rate above is after the verifier removed failing claims; this is before.
            s["pre_verification_unsupported_rate"] = round(caught / proposed, 3) if proposed else None
        report["variants"][variant] = s
    report["seed_start"] = args.start
    report_name = "slice3_agents.json" if args.tag == "fresh" else f"agents_{args.tag}.json"
    with open(Path(args.out) / report_name, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    cols = ("recall@1", "recall@3", "macro_recall@1", "decoy_rejection", "unsupported_claim_rate")
    for name, s in report["variants"].items():
        kinds = ", ".join(f"{k} {v['recall@1']:.2f}/{v['n']}" for k, v in s["by_label_kind"].items())
        print(f"{name:24s} " + "  ".join(f"{c} {s[c]:.2f}" for c in cols) + f"  [{kinds}]  n={s['n_cases']}")
    print("estimated spend (cumulative for this budget):", report["spent_usd_estimate"])


if __name__ == "__main__":
    main()
