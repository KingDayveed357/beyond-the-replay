"""Train the pass-difficulty model on development seeds only, and check it on held-out seeds.

Usage:  python scripts/train_pass_model.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.models import FEATURES, MODEL_FILE, PassModel, pass_features  # noqa: E402
from phase0.engine import make_config, simulate  # noqa: E402


def rows(seeds):
    out = []
    for seed in seeds:
        cfg = make_config(seed)
        for e in simulate(cfg).events:
            if e["type"] == "pass":
                out.append((pass_features(e, cfg.home), 1.0 if e["outcome"] == "success" else 0.0))
    return out


def log_loss(w, data):
    total = 0.0
    for f, y in data:
        p = 1 / (1 + math.exp(-sum(a * b for a, b in zip(w, f))))
        p = min(max(p, 1e-6), 1 - 1e-6)
        total -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return total / len(data)


train = rows(range(1, 41))
test = rows(range(600_001, 600_021))
w = PassModel.fit(train)
base = sum(y for _, y in train) / len(train)
base_w = [math.log(base / (1 - base))] + [0.0] * (len(FEATURES) - 1)
print(f"train passes {len(train)}, held-out passes {len(test)}")
print(f"held-out log-loss: model {log_loss(w, test):.4f} vs constant {log_loss(base_w, test):.4f}")
print(dict(zip(FEATURES, w)))
MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
MODEL_FILE.write_text(json.dumps({"features": FEATURES, "weights": w, "trained_on": "development seeds 1-40",
                                  "held_out_log_loss": round(log_loss(w, test), 4),
                                  "constant_log_loss": round(log_loss(base_w, test), 4)}, indent=1))
