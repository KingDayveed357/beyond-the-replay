# Phase 0 results

Held-out cases: 80 (55 with a clear measured cause). Paired re-runs per variable: 120.

| investigator | recall@1 | recall@3 | recall@1_strict_onset | decoy_rejection | unsupported_claim_rate | evidence_link_correctness |
|---|---|---|---|---|---|---|
| random | 0.11 | 0.42 | 0.05 | 0.94 | 1.00 | 0.00 |
| salience | 0.02 | 0.49 | 0.00 | 0.05 | 0.68 | 0.32 |
| lane_shortcut | 0.44 | 0.69 | 0.00 | 1.00 | 1.00 | 0.00 |
| stat_unfitted | 0.36 | 0.80 | 0.33 | 0.99 | 0.00 | 1.00 |
| stat_fitted | 0.64 | 0.89 | 0.53 | 1.00 | 0.00 | 1.00 |

LLM-only baseline: see results/slice3_agents.json (python -m investigation.evaluate_agents)

## Gates

- **G0_no_leakage**: PASS — []
- **G1_truth_is_meaningful**: PASS — 69% of cases have a clear measured cause (need >= 60%)
- **G2_learnable**: FAIL — stat recall@1 0.64 (>=0.50), recall@3 0.89 (>=0.75), class-balanced recall@1 0.46 (>=0.50)
- **G3_not_trivial**: PASS — salience recall@1 0.02 (<=0.35); stat minus lane-shortcut +0.20 (>=+0.15)
- **G4_headroom**: PASS — stat recall@1 0.64; above 0.90 leaves agents nothing to add

## Ground truth

```
{
  "labelled": 55,
  "ambiguous": 25,
  "label_is_planted_factor": 48,
  "label_kinds": {
    "FATIGUE": 37,
    "OVERLOAD": 11,
    "STATIC": 7,
    "STYLE": 0
  },
  "planted_effect_mean": 0.201,
  "but_for_rate": 0.613,
  "candidates_per_case": 8.95
}
```

## Engine realism (mean per match)

```
{
  "events": 953.267,
  "goals": 3.608,
  "shots": 21.742,
  "pass_completion": 0.808,
  "possessions": 227.15,
  "fouls": 11.867
}
```

Fitted weights: `{'FATIGUE': 1.0, 'OVERLOAD': 0.25, 'STATIC': 0.25, 'STYLE': 0.25, 'FOUL': 0.25}`
