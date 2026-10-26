"""Engine sanity check: mean per-match statistics and speed over development seeds."""
import collections
import statistics
import sys
import time

sys.path.insert(0, ".")
from phase0.engine import make_config, simulate  # noqa: E402
from phase0.evaluate import realism_stats  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
start = time.perf_counter()
rows, types = [], collections.Counter()
for seed in range(1, n + 1):
    res = simulate(make_config(seed))
    rows.append(realism_stats(res.events, res.goals))
    types.update(e["type"] for e in res.events)
print(f"seconds per match: {(time.perf_counter() - start) / n:.4f}")
for key in rows[0]:
    print(f"{key:16s} {statistics.fmean(r[key] for r in rows):8.3f}")
print({k: round(v / n, 1) for k, v in types.items()})
