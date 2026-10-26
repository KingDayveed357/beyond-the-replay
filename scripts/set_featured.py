"""Choose which showcase matches are featured, without regenerating anything (no model calls).

hero      - the investigation shown first (landing hook, demo video)
showcase  - the big fixture used for the live match centre
others keep the role build_showcase.py gave them.

Usage:  python scripts/set_featured.py --hero m300080 --showcase m300121
"""
import argparse
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

ap = argparse.ArgumentParser()
ap.add_argument("--hero", required=True)
ap.add_argument("--showcase", required=True)
args = ap.parse_args()

index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
ids = {m["id"] for m in index}
assert {args.hero, args.showcase} <= ids, f"unknown match id; choose from {sorted(ids)}"
for m in index:
    role = "hero" if m["id"] == args.hero else "showcase" if m["id"] == args.showcase else m["role"]
    if role == "hero" and m["id"] != args.hero:
        role = "fatigue"  # a previous hero becomes an ordinary example
    m["role"] = role
    path = DATA / "matches" / f"{m['id']}.json"
    full = json.loads(path.read_text(encoding="utf-8"))
    full["role"] = role
    path.write_text(json.dumps(full, ensure_ascii=False), encoding="utf-8")
(DATA / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
for m in index:
    print(f"{m['id']} {m['role']:9s} {m['home_name']} v {m['away_name']}")
