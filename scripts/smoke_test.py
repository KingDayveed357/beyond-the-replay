"""Post-deploy smoke test. Never triggers a model call, so it costs nothing to run.

Usage:  python scripts/smoke_test.py https://<your-app>.azurecontainerapps.io
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
LANGS = ("en", "es", "fr", "pt", "ar")
failures = []


def get(path, method="GET", raw=False, timeout=30):
    req = urllib.request.Request(BASE + path, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        body = res.read().decode("utf-8")
        return (res.status, res.headers, body) if raw else json.loads(body)


def check(name, fn):
    started = time.perf_counter()
    try:
        detail = fn()
        print(f"  ok   {name} ({(time.perf_counter() - started) * 1000:.0f} ms){' - ' + detail if detail else ''}")
    except (AssertionError, urllib.error.URLError, KeyError, ValueError) as exc:
        failures.append(name)
        print(f"  FAIL {name}: {exc}")


print(f"Smoke test against {BASE}")
check("health", lambda: str(get("/api/health")))
provider = {}


def provider_status():
    provider.update(get("/api/provider"))
    raw = json.dumps(provider)
    assert "sk-ant" not in raw, "a key-shaped string appears in /api/provider"
    return f"key configured: {provider['server_key_configured']}, platform: {provider.get('platform')}, " \
           f"budget left ≈ ${provider['budget']['remaining_usd_estimate']}"


check("provider status exposes no key", provider_status)
matches = get("/api/matches")
check("matches", lambda: f"{len(matches)} matches, hero: " + next(m["id"] for m in matches if m["role"] == "hero"))

for m in matches:
    mid, inc = m["id"], m["incident_id"]
    check(f"{mid} timeline in 5 languages", lambda mid=mid: ", ".join(
        f"{l}:{len(get(f'/api/matches/{mid}/timeline?lang={l}')['moments'])}" for l in LANGS))
    check(f"{mid} overlays json + vtt", lambda mid=mid: (
        f"{len(get(f'/api/matches/{mid}/overlays')['cues'])} cues; "
        + ("WEBVTT ok" if get(f"/api/matches/{mid}/overlays?format=vtt", raw=True)[2].startswith("WEBVTT") else "bad vtt")))
    check(f"{mid} recaps saved (Claude)", lambda mid=mid: ", ".join(
        f"{p}/{v}:{get(f'/api/matches/{mid}/recap?phase={p}&voice={v}')['source']}" for p in ("ht", "ft") for v in ("fan", "analyst")))
    check(f"{mid} statistics-only investigation", lambda mid=mid, inc=inc: get(
        f"/api/matches/{mid}/incidents/{inc}/investigations?mode=deterministic", method="POST")["explanation"]["headline"])

    def saved(mid=mid, inc=inc):
        out = get(f"/api/matches/{mid}/incidents/{inc}/saved-investigation")
        return f"{out['model_label']}: {out['explanation']['headline']}"
    check(f"{mid} saved AI investigation (prevents paid runs)", saved)


def stream():
    mid = next(m["id"] for m in matches if m["role"] in ("showcase", "hero"))
    req = urllib.request.Request(f"{BASE}/api/matches/{mid}/live?speed=240")
    with urllib.request.urlopen(req, timeout=30) as res:
        assert res.headers.get_content_type() == "text/event-stream", res.headers.get_content_type()
        seen = 0
        for line in res:
            if line.startswith(b"data: "):
                seen += 1
            if seen >= 20:
                return "20 live messages received"
    raise AssertionError("stream ended early")


check("live event stream", stream)


def identity_check():
    out = get("/api/identity")
    assert out["mode"] == "fictional", f"public names are {out['mode']}: set BTR_NAMES=fictional for the demo"
    return out["label"]


def studio_pack():
    mid = next(m["id"] for m in matches if m["role"] == "hero")
    pack = get(f"/api/matches/{mid}/studio-pack")
    edl = get(f"/api/matches/{mid}/studio-pack?format=edl", raw=True)[2]
    assert edl.startswith("TITLE:"), "EDL export"
    return f"{len(pack['highlights']['clips'])} clips, 60s script {pack['presenter']['60s']['seconds']} s"


def ingestion():
    feed = get("/api/feeds/demo?speed=120", method="POST")
    time.sleep(3)
    snap = get(f"/api/feeds/{feed['feed_id']}")
    assert snap["summary"]["events"] > 0, "no events ingested"
    return f"feed {feed['feed_id']}: {snap['summary']['events']} events after 3 s, {snap['summary']['stats']['batches']} batches"


def a2a():
    card = get("/a2a/.well-known/agent-card.json")
    return f"{card['name']}: {', '.join(s['id'] for s in card['skills'])}"


check("fictional names by default", identity_check)
check("studio pack + EDL", studio_pack)
check("live ingestion (Agent Framework pipeline)", ingestion)
check("A2A agent card", a2a)
check("agent workflows described", lambda: ", ".join(get("/api/agents")["investigation"]["executors"][i]["id"] for i in range(6)))
check("frontend served", lambda: "ok" if "<div id=\"root\">" in get("/", raw=True)[2] else (_ for _ in ()).throw(AssertionError("no app shell")))

print("\nAll checks passed." if not failures else f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
sys.exit(1 if failures else 0)
