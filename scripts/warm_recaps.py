"""Write Claude half-time and full-time recaps (fan and analyst) for every showcase match.

Each recap must pass the fact check or the labelled template is saved instead. Existing files are
kept unless --force. Never prints the key.

Usage:  python scripts/warm_recaps.py [--langs en] [--force]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.recap import claude_recap, facts  # noqa: E402
from investigation.llm.provider import Provider, server_api_key  # noqa: E402
from server.app import DATA, index, match, policy, timeline  # noqa: E402  (loads .env)

LANGUAGES = {"en": "English", "es": "Spanish", "fr": "French", "pt": "Portuguese", "ar": "Arabic"}

ap = argparse.ArgumentParser()
ap.add_argument("--langs", default="en")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

out_dir = DATA / "recaps"
out_dir.mkdir(parents=True, exist_ok=True)
total = 0.0
for m in index():
    mt, tl = match(m["id"]), timeline(m["id"])
    names = {p["name"] for p in mt["roster"].values()}
    for phase in ("ht", "ft"):
        f = facts(mt, tl, phase)
        for voice in ("fan", "analyst"):
            for lang in args.langs.split(","):
                path = out_dir / f"{m['id']}_{phase}_{voice}_{lang}.json"
                if path.exists() and not args.force:
                    continue
                policy.ledger.check()
                provider = Provider(server_api_key(), None, "server")
                recap = claude_recap(provider, f, voice, LANGUAGES[lang], names)
                policy.ledger.record(provider.usage)
                total += provider.usage.cost_usd_estimate
                path.write_text(json.dumps(recap | {"facts": f, "lang": lang, "voice": voice, "phase": phase},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"{m['id']} {phase} {voice} {lang}: {recap['source']} | {recap['headline']}")
print(f"spend this run ≈ ${total:.4f} (estimate)")
