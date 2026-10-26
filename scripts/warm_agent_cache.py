"""Run the Claude agents once per showcase match with the server key, so the default judge
experience is a saved, real agent result. Skips matches that already have a result for the current
prompt version. Never prints the key.

Usage:  python scripts/warm_agent_cache.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.app import case_for, index, policy  # noqa: E402  (loads .env for local runs)

total = 0.0
for m in index():
    case = case_for(m["id"], m["incident_id"])
    out = policy.investigate(case, client_id="warm-cache", fresh=False, byok_key=None, byok_model=None)
    cost = 0.0 if out.get("cached") else out["usage"]["cost_usd_estimate"]
    total += cost
    print(f"{m['id']} {m['role']:9s} cached={out['cached']!s:5s} top={out['ranking'][0] if out['ranking'] else None} "
          f"producer={out['producer_source']} calls={out['usage']['calls']} cost≈${cost:.4f}")
print(f"new spend this run ≈ ${total:.4f} (estimate); server ledger ≈ ${policy.ledger.spent_usd:.4f}")
