"""An external data provider, simulated: generates a brand-new synthetic match and pushes it to a Beyond the
Replay server over HTTP, one batch per second, exactly as a real provider integration would.

Usage:  python scripts/feed_simulator.py https://<your-app> --speed 30 [--seed 712345]
Then open the printed watch URL. Costs nothing: the pipeline never calls a model.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.provider_sim import new_match  # noqa: E402


def post(url: str, body: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://localhost:8000")
    ap.add_argument("--speed", type=float, default=30.0, help="match seconds per real second")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    base = args.base.rstrip("/")
    sheet, events = new_match(args.seed)
    feed = post(f"{base}/api/feeds", sheet)
    print(f"Feed {feed['feed_id']} open. Watch: {base}/feed/{feed['feed_id']}")
    i, clock = 0, 0.0
    while i < len(events):
        clock += args.speed
        batch = []
        while i < len(events) and events[i]["t"] <= clock:
            batch.append(events[i])
            i += 1
        ack = post(f"{base}{feed['events_url']}", {"events": batch, "final": i >= len(events)}, feed["write_token"])
        print(f"{int(clock // 60):>3}'  +{ack['accepted']:>3} events  rejected {ack['rejected_count']}  "
              f"pipeline {sum(ack['stage_ms'].values()):.0f} ms  total {ack['events_total']}")
        time.sleep(1.0)
    print("Full-time.")


if __name__ == "__main__":
    main()
