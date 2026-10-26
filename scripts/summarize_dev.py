"""Compact view of a `--dev-only` run captured to a file (tolerates progress lines and a BOM)."""
import json
import sys

text = open(sys.argv[1], encoding="utf-8-sig", errors="replace").read()
d = json.loads(text[text.index("{"):])
print("weights", d["weights"], "| labelled", d["labelled"], "/", d["cases"], "| label is planted", d["label_is_planted"])
print("planted effect mean by kind", {k: (round(sum(v) / len(v), 2), len(v)) for k, v in d["planted_effect_by_kind"].items()})
print("labels", {k: d["labels"].count(k) for k in set(d["labels"])})
for k, v in d["gates_on_dev"].items():
    print(k, "PASS" if v["pass"] else "FAIL", v["detail"])
for name, s in d["scores"].items():
    print(f"{name:14s} r@1 {s['recall@1']:.2f}  r@3 {s['recall@3']:.2f}  macro {s['macro_recall@1']:.2f}  "
          f"decoy-rej {s['decoy_rejection']:.2f}  by-kind {{{', '.join(f'{k}:{v['recall@1']:.2f}/{v['n']}' for k, v in s['by_kind'].items())}}}")
