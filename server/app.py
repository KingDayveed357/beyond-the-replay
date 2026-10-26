"""HTTP API. Matches and observable events are public; ground truth has its own endpoint and is
labelled evaluation-only, so no investigation path can read it.

Run:  uvicorn server.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from analytics.i18n import LANGUAGES, localize, to_webvtt
from analytics.live import build_timeline
from analytics.models import PassModel
from analytics.narrative import build_narrative, render as render_narrative
from analytics.recap import facts, template_recap
from investigation.llm.provider import SUPPORTED_MODELS, Provider, ProviderError, load_dotenv, validate_model
from investigation.workflow import investigate
from phase0.observe import Case, OBSERVABLE_FIELDS

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # local development only; deployments set real environment variables

from server.identity import identity  # noqa: E402
from server.inference import InferencePolicy  # noqa: E402  (reads limits from the environment)

DATA = Path(os.environ.get("BTR_DATA", ROOT / "data"))
RESULTS = ROOT / "results"
WEB = ROOT / "web" / "dist"
RUNTIME = Path(os.environ.get("BTR_RUNTIME", ROOT / ".runtime"))

KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")


class RedactKeys(logging.Filter):
    """Belt and braces: no log line may ever carry something shaped like an Anthropic key."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "sk-ant-" in msg:
            record.msg, record.args = KEY_PATTERN.sub("[redacted]", msg), None
        return True


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for handler in logging.getLogger().handlers:
    handler.addFilter(RedactKeys())
log = logging.getLogger("btr")
logging.getLogger("agent_framework").setLevel(logging.WARNING)  # one line per superstep is too chatty

API_DESCRIPTION = """Explainable match intelligence for synthetic football matches.

**Ingest a match in three calls** (full guide: `docs/API.md` in the repository):

1. `POST /api/feeds` with a match sheet. You get a `feed_id` and a `write_token`.
2. `POST /api/feeds/{feed_id}/events` with batches of events, header `Authorization: Bearer <write_token>`.
3. Watch it at `/studio/{feed_id}`, or stream `GET /api/feeds/{feed_id}/live` (server-sent events).

Nothing in the ingestion path calls an AI model, so it is free to test. Names shown are fictional.
"""
TAGS = [
    {"name": "Ingestion", "description": "Push your own synthetic match events and get match intelligence back, live."},
    {"name": "Matches", "description": "The stored showcase matches: timelines, live replay, overlays, recaps."},
    {"name": "Studio pack", "description": "Presenter scripts, highlight edit lists, social posts and alerts."},
    {"name": "Investigation", "description": "Why a goal happened: AI agents and the statistics-only workflow."},
    {"name": "Agents", "description": "Workflow descriptions and the A2A agent."},
    {"name": "Feedback", "description": "Honest feedback from fans, analysts, judges and developers."},
]
class UTF8JSONResponse(JSONResponse):
    """Say the charset out loud: Windows PowerShell 5.1 otherwise decodes accented names as Latin-1."""
    media_type = "application/json; charset=utf-8"


app = FastAPI(title="Beyond the Replay API", version="1.0.0", description=API_DESCRIPTION, openapi_tags=TAGS,
              default_response_class=UTF8JSONResponse)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])
policy = InferencePolicy(DATA / "agent_cache", RUNTIME)


@app.exception_handler(ProviderError)
def provider_error(_: Request, exc: ProviderError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.to_dict()})


def _read(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def index() -> list:
    return _read(DATA / "index.json")


@lru_cache(maxsize=32)
def match(match_id: str) -> dict:
    if match_id not in {m["id"] for m in index()}:
        raise HTTPException(404, f"unknown match {match_id}")
    return _read(DATA / "matches" / f"{match_id}.json")


def public(obj, match_id: str | None = None):
    """Every response leaves through here: in the default fictional mode, real clubs, players, stadiums and
    officials are replaced (see server/identity.py). Internal computation always uses the original data."""
    return identity().skin(obj, match(match_id)["roster"] if match_id else None)


def case_for(match_id: str, incident_id: str) -> Case:
    m = match(match_id)
    if incident_id not in {g["id"] for g in m["goals"]}:
        raise HTTPException(404, f"{incident_id} is not a goal in {match_id}")
    events = [{k: e[k] for k in OBSERVABLE_FIELDS} for e in m["events"]]
    return Case(match_id, m["home"], m["away"], m["roster"], events, incident_id)


@app.get("/api/health")
def health():
    return {"ok": True, "matches": len(index())}


@app.get("/api/identity")
def identity_mode():
    """Which names the app shows. Fictional by default: broadcast-safe, no third-party trademarks."""
    fictional = identity().fictional
    return {"mode": identity().mode, "label": "Fictional clubs and players" if fictional else "Real 2024/25 squads",
            "note": ("Simulated matches. Clubs, players, stadiums and officials are fictional; team strengths are modelled "
                     "on a real top-flight season.") if fictional else "Simulated matches with real 2024/25 squads."}


@app.get("/api/provider")
def provider_status():
    return policy.status() | {"models": [{"id": k, "label": v["label"]} for k, v in SUPPORTED_MODELS.items()],
                              "byok": {"providers": ["anthropic"], "storage": "sent per request, never stored"}}


@app.post("/api/provider/test")
def provider_test(x_byok_key: str | None = Header(default=None), x_byok_model: str | None = Header(default=None)):
    if not x_byok_key:
        raise ProviderError("missing_key", "Paste a key first.", 400)
    return Provider(x_byok_key, validate_model(x_byok_model), "byok").test()


@app.get("/api/matches", tags=["Matches"])
def list_matches():
    return [public(m, m["id"]) for m in index()]


@app.get("/api/matches/{match_id}", tags=["Matches"])
def get_match(match_id: str):
    return public(match(match_id), match_id)


@app.post("/api/matches/{match_id}/incidents/{incident_id}/investigations", tags=["Investigation"])
def run_investigation(match_id: str, incident_id: str, request: Request, mode: str = "agents", fresh: bool = False,
                      sceptic: bool = True, x_byok_key: str | None = Header(default=None),
                      x_byok_model: str | None = Header(default=None)):
    case = case_for(match_id, incident_id)
    if mode == "deterministic":
        out = investigate(case, use_sceptic=sceptic) | {"cached": False}
    elif mode == "agents":
        client = request.client.host if request.client else "unknown"
        out = policy.investigate(case, client_id=client, fresh=fresh, byok_key=x_byok_key, byok_model=x_byok_model)
    else:
        raise HTTPException(400, "mode must be 'agents' or 'deterministic'")
    out = out | {"id": uuid.uuid4().hex[:12]}
    log.info("investigation %s match=%s incident=%s mode=%s cached=%s key=%s top=%s ms=%s cost=%s", out["id"], match_id,
             incident_id, out["mode"], out.get("cached"), out.get("key_source", "-"),
             out["ranking"][0] if out["ranking"] else None, out["elapsed_ms"], out.get("usage", {}).get("cost_usd_estimate"))
    return public(out, match_id)


@lru_cache(maxsize=1)
def pass_model() -> PassModel:
    return PassModel.load()


@lru_cache(maxsize=32)
def timeline(match_id: str) -> dict:
    m = dict(match(match_id))
    m["names"] = {m["home"]: m["home_name"], m["away"]: m["away_name"]}
    return build_timeline(m, pass_model())


@lru_cache(maxsize=64)
def timeline_in(match_id: str, lang: str) -> dict:
    if lang not in LANGUAGES:
        raise HTTPException(400, f"lang must be one of {', '.join(LANGUAGES)}")
    m = match(match_id)
    tl = localize(timeline(match_id), m, lang)
    tl["narrative"] = render_narrative(narrative(match_id), m, lang)
    return public(tl, match_id)


@lru_cache(maxsize=32)
def narrative(match_id: str) -> dict:
    """Storylines, milestones and summaries; every beat is dated, so a replay shows them as the clock passes."""
    return build_narrative(match(match_id), timeline(match_id), final=True)


@app.get("/api/agents", tags=["Agents"])
def agents_graph():
    """The multi-agent workflows (Microsoft Agent Framework): roles, hand-offs and recovery rules."""
    from investigation.orchestration import describe
    return {"investigation": describe()}


@app.get("/api/languages")
def languages():
    return [{"code": k, "label": v, "dir": "rtl" if k == "ar" else "ltr"} for k, v in LANGUAGES.items()]


@app.get("/api/matches/{match_id}/timeline", tags=["Matches"])
def get_timeline(match_id: str, lang: str = "en"):
    """Everything a client needs to show the match at any clock time: per-minute states, key moments,
    overlay cues, player summaries, and events enriched with xG and pass difficulty."""
    return timeline_in(match_id, lang)


@app.get("/api/matches/{match_id}/overlays", tags=["Matches"])
def overlays(match_id: str, lang: str = "en", format: str = "json"):
    """Timed, machine-readable overlay track for a graphics engine or video player.
    format=json: versioned cue list; format=vtt: WebVTT metadata track with one JSON payload per cue."""
    tl = timeline_in(match_id, lang)
    if format == "vtt":
        return PlainTextResponse(to_webvtt(tl["cues"], lang), media_type="text/vtt")
    if format != "json":
        raise HTTPException(400, "format must be json or vtt")
    m = public(match(match_id), match_id)
    return {"schema": "beyond-the-replay/overlays", "version": "1.0", "match_id": match_id, "lang": lang, "dir": tl["dir"],
            "clock": "seconds from kick-off", "simulated": True,
            "teams": {m["home"]: m["home_name"], m["away"]: m["away_name"]},
            "colours": m.get("metadata", {}).get("colours"),
            "layers": {"goal": "full-width goal graphic", "lower_third": "headline with explanation",
                       "name_tag": "player tag with a metric (speed or distance)", "speed": "shot-speed readout"},
            "cues": tl["cues"]}


@app.get("/api/matches/{match_id}/live", tags=["Matches"])
async def live(match_id: str, request: Request, speed: float = 30.0, start: float = 0.0, lang: str = "en"):
    """Server-sent events: the match replayed on a clock, as a live feed would deliver it.
    Each message is one of: event, state (once per minute), moment, cue, phase."""
    tl = timeline_in(match_id, lang)
    speed = min(max(speed, 1.0), 240.0)
    feed = [(e["t"], 0, "event", e) for e in tl["events"]]
    feed += [(s["minute"] * 60, 1, "state", s) for s in tl["states"]]
    feed += [(m["t"] + 0.5, 2, "moment", m) for m in tl["moments"]]
    feed += [(c["t_in"] + 0.6, 3, "cue", c) for c in tl["cues"]]
    nar = tl["narrative"]
    for st in nar["storylines"]:
        for i, b in enumerate(st["beats"]):
            beat = {k: v for k, v in st.items() if k != "beats"} | {"beat": b, "index": i}
            feed.append((b["t"] + 0.7, 3, "beat", beat))
    feed += [(m["t"] + 0.8, 3, "milestone", m) for m in nar["milestones"]]
    feed += [(x["t"] + 0.9, 3, "summary", x) for x in nar["summaries"]]
    end = max(t for t, *_ in feed)
    feed += [(45 * 60, 4, "phase", {"phase": "half_time"}), (end + 1, 4, "phase", {"phase": "full_time"})]
    feed = sorted((x for x in feed if x[0] >= start), key=lambda x: (x[0], x[1]))

    async def stream():
        clock = start
        for t, _, kind, payload in feed:
            if await request.is_disconnected():
                return
            wait = (t - clock) / speed
            if wait > 0:
                await asyncio.sleep(min(wait, 2.0))
            clock = t
            body = json.dumps({"t": t, kind: payload}, ensure_ascii=False)
            yield f"event: {kind}\ndata: {body}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- live ingestion ----------

from server.api_models import ApiError, EventBatch, FeedCreated, IngestAck, MatchSheet  # noqa: E402
from server.feeds import MAX_BATCH, MAX_EVENTS, PIPELINE, FeedError, FeedService, validate_create  # noqa: E402

ERRORS = {400: {"model": ApiError, "description": "The request makes no sense for this feed (the message says why)"},
          401: {"model": ApiError, "description": "Missing or wrong write token"},
          404: {"model": ApiError, "description": "Unknown or expired feed"},
          409: {"model": ApiError, "description": "The feed has already ended"}}


def _feed_view(m: dict, tl: dict, nar: dict | None, lang: str):
    if lang not in LANGUAGES:
        raise HTTPException(400, f"lang must be one of {', '.join(LANGUAGES)}")
    skin = lambda obj: identity().skin(obj, m["roster"])  # noqa: E731
    return skin(localize(tl, m, lang)), (skin(render_narrative(nar, m, lang)) if nar else None)


feeds = FeedService(lambda m: build_timeline(m, pass_model()), _feed_view)


@app.exception_handler(FeedError)
def feed_error(_: Request, exc: FeedError):
    return JSONResponse(status_code=exc.status, content={"detail": {"code": exc.code, "message": exc.message}})


@app.get("/api/schema", tags=["Ingestion"])
def schema():
    """The ingestion contract, as JSON Schema."""
    return _read(ROOT / "schemas" / "match-feed.schema.json")


@app.post("/api/feeds", status_code=201, response_model=FeedCreated, tags=["Ingestion"], summary="Open a live feed",
          responses={400: ERRORS[400], 429: {"model": ApiError, "description": "Too many live feeds on the server"}})
def create_feed(sheet: MatchSheet):
    """Send the match sheet (teams and players) once. The write token is returned only here: keep it."""
    feed = feeds.create(validate_create(sheet.model_dump(exclude_none=True)), "api")
    return {"feed_id": feed.id, "write_token": feed.token, "events_url": f"/api/feeds/{feed.id}/events",
            "live_url": f"/api/feeds/{feed.id}/live", "limits": {"max_batch": MAX_BATCH, "max_events": MAX_EVENTS}}


@app.post("/api/feeds/{feed_id}/events", response_model=IngestAck, tags=["Ingestion"], summary="Push a batch of events",
          responses={k: ERRORS[k] for k in (400, 401, 404, 409)})
async def ingest_events(feed_id: str, batch: EventBatch,
                        authorization: str | None = Header(default=None, description="Bearer <write_token>")):
    """Push events in clock order, about once a second while live. Each event is checked on its own: good ones
    run through the pipeline, bad ones come back in `rejected` with a reason. Send `"final": true` at full-time."""
    feed = feeds.get(feed_id)
    feeds.authorise(feed, authorization)
    return await feeds.ingest(feed, batch.raw_events(), batch.final)


@app.get("/api/feeds", tags=["Ingestion"])
def list_feeds():
    return [identity().skin(f.summary(), f.match["roster"]) for f in feeds.feeds.values()]


@app.get("/api/feeds/sample", tags=["Ingestion"])
def sample_feed(seed: int | None = None):
    """A complete match file (sheet + events) to try the upload path or an integration with."""
    from server.provider_sim import new_match
    sheet, events = new_match(seed)
    return identity().skin({"sheet": sheet, "events": events}, sheet["roster"])


@app.get("/api/feeds/{feed_id}", tags=["Ingestion"])
def get_feed(feed_id: str, lang: str = "en"):
    feed = feeds.get(feed_id)
    return identity().skin(feeds.snapshot(feed, lang), feed.match["roster"])


@app.get("/api/feeds/{feed_id}/live", tags=["Ingestion"])
async def feed_live(feed_id: str, request: Request, lang: str = "en"):
    """Server-sent events for a live feed: a snapshot first, then only what each new batch adds
    (event, state, moment, cue, storyline, milestone, summary, ingest, phase)."""
    feed = feeds.get(feed_id)
    if lang not in LANGUAGES:
        raise HTTPException(400, f"lang must be one of {', '.join(LANGUAGES)}")
    q = feeds.subscribe(feed, lang)
    first = identity().skin(feeds.snapshot(feed, lang), feed.match["roster"])

    async def stream():
        try:
            yield f"event: snapshot\ndata: {json.dumps(first, ensure_ascii=False)}\n\n"
            while not await request.is_disconnected():
                try:
                    kind, payload = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if kind == "phase":
                    return
        finally:
            feeds.unsubscribe(feed, q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/feeds/demo", status_code=201, tags=["Ingestion"])
async def demo_feed(request: Request, speed: float = 20.0, seed: int | None = None):
    """Kick off a brand-new synthetic match and stream it into a live feed through the public ingestion path,
    the way an external data provider would. Speed is match seconds per real second (5-120)."""
    from server.provider_sim import new_match, stream_match
    client = request.client.host if request.client else "unknown"
    if not demo_limiter.allow(client):
        raise FeedError(429, "slow_down", "You've started several demo matches. Watch one, or try again in a few minutes.")
    sheet, events = new_match(seed)
    feed = feeds.create(validate_create(sheet), "simulator")
    asyncio.create_task(stream_match(feeds, feed, events, min(max(speed, 5.0), 120.0)))
    return {"feed_id": feed.id, "live_url": f"/api/feeds/{feed.id}/live", "events": len(events), "speed": speed}


@app.get("/api/pipeline", tags=["Agents"])
def pipeline_graph():
    return PIPELINE


class _Limiter:
    def __init__(self, per_hour: int):
        self.per_hour, self.hits = per_hour, {}

    def allow(self, key: str) -> bool:
        import time as _t
        now = _t.time()
        recent = [x for x in self.hits.get(key, []) if now - x < 3600]
        if len(recent) >= self.per_hour:
            return False
        self.hits[key] = recent + [now]
        return True


demo_limiter = _Limiter(int(os.environ.get("BTR_DEMO_FEEDS_PER_HOUR", "12")))


# ---------- studio pack ----------

def _pack_response(pack: dict, format: str, name: str):
    from analytics.studio_pack import to_csv, to_edl, to_markdown
    if format == "json":
        return pack
    if format == "md":
        return PlainTextResponse(to_markdown(pack), media_type="text/markdown; charset=utf-8",
                                 headers={"Content-Disposition": f'inline; filename="{name}.md"'})
    if format == "edl":
        return PlainTextResponse(to_edl(pack), headers={"Content-Disposition": f'attachment; filename="{name}.edl"'})
    if format == "csv":
        return PlainTextResponse(to_csv(pack), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    raise HTTPException(400, "format must be json, md, edl or csv")


@app.get("/api/matches/{match_id}/studio-pack", tags=["Studio pack"])
def studio_pack(match_id: str, lang: str = "en", club: str | None = None, player: str | None = None, format: str = "json"):
    """Automated recap pack for studio, broadcast and streaming: presenter scripts, highlight rundown (EDL/CSV),
    lower thirds, social copy, push alerts and stat cards. Optional club/player personalise it."""
    from analytics.studio_pack import build_pack
    if lang not in LANGUAGES:
        raise HTTPException(400, f"lang must be one of {', '.join(LANGUAGES)}")
    m = match(match_id)
    saved = policy.cached(match_id, m["incident_id"]) if lang == "en" else None
    pack = build_pack(m, localize(timeline(match_id), m, lang), render_narrative(narrative(match_id), m, lang), lang,
                      explanation=saved["explanation"] if saved else None,
                      club=identity().unskin_id(club) if club else None, player=identity().unskin_id(player) if player else None)
    return _pack_response(public(pack, match_id), format, f"{match_id}-studio-pack-{lang}")


@app.get("/api/feeds/{feed_id}/studio-pack", tags=["Studio pack"])
def feed_studio_pack(feed_id: str, lang: str = "en", club: str | None = None, player: str | None = None, format: str = "json"):
    """The same pack for a live feed, as of the latest batch."""
    from analytics.studio_pack import build_pack
    feed = feeds.get(feed_id)
    if not feed.timeline:
        raise HTTPException(409, "No events yet.")
    tl, nar = _feed_view(feed.match, feed.timeline, feed.narrative, lang)
    pack = build_pack(identity().skin(feed.match, feed.match["roster"]), tl, nar or {"storylines": []}, lang,
                      club=club, player=player)
    return _pack_response(pack, format, f"{feed_id}-studio-pack-{lang}")


@app.get("/api/matches/{match_id}/recap", tags=["Matches"])
def get_recap(match_id: str, phase: str = "ft", voice: str = "fan", lang: str = "en"):
    if phase not in ("ht", "ft") or voice not in ("fan", "analyst"):
        raise HTTPException(400, "phase must be ht|ft and voice fan|analyst")
    path = DATA / "recaps" / f"{match_id}_{phase}_{voice}_{lang}.json"
    if path.exists():
        return public(_read(path), match_id)
    f = facts(match(match_id), timeline(match_id), phase)
    return public(template_recap(f) | {"note": "Template recap: no Claude recap has been generated for this view yet.",
                                       "facts": f}, match_id)


@app.get("/api/matches/{match_id}/incidents/{incident_id}/saved-investigation", tags=["Investigation"])
def saved_investigation(match_id: str, incident_id: str):
    """The saved AI investigation, if one exists for the current agent code. Never calls a model."""
    case_for(match_id, incident_id)
    hit = policy.cached(match_id, incident_id)
    if hit is None:
        raise HTTPException(404, "no saved AI investigation for the current agent version")
    return public(hit | {"cached": True}, match_id)


@app.get("/api/matches/{match_id}/incidents/{incident_id}/truth", tags=["Investigation"])
def get_truth(match_id: str, incident_id: str):
    m = match(match_id)
    if incident_id != m["incident_id"]:
        raise HTTPException(404, "ground truth is only measured for the featured incident")
    return public(_read(DATA / "truth" / f"{match_id}.json"), match_id)


@app.get("/api/benchmark", tags=["Investigation"])
def benchmark():
    out = {}
    for name in ("phase0", "slice2_sceptic", "slice3_agents", "agents_heldout2", "agents_heldout_v21"):
        path = RESULTS / f"{name}.json"
        if path.exists():
            out[name] = _read(path)
    return public(out)


# ---------- feedback ----------

from server.feedback import FeedbackIn, FeedbackService, make_store  # noqa: E402

feedback = FeedbackService(make_store(RUNTIME), per_hour=int(os.environ.get("BTR_FEEDBACK_PER_HOUR", "6")))


@app.post("/api/feedback", status_code=201, tags=["Feedback"], summary="Send feedback",
          responses={429: {"model": ApiError, "description": "Too much feedback from one address in an hour"}})
def send_feedback(body: FeedbackIn, request: Request):
    """A rating, who you are, and the one thing we should improve. Emails are stored only for a reply and never shown."""
    client = request.client.host if request.client else "unknown"
    if not feedback.allow(client):
        raise FeedError(429, "slow_down", "Thanks! You've sent several notes this hour; please try again later.")
    return feedback.submit(body, client)


@app.get("/api/feedback/summary", tags=["Feedback"], summary="What people think")
def feedback_summary():
    """Counts, average ratings by role and the latest comments (never emails)."""
    return feedback.summary()


# ---------- A2A: the match analyst as an agent other agents can call ----------

def _a2a_answer(text: str) -> str:
    from analytics.studio_pack import build_pack
    from server.a2a_agent import answer
    return answer(
        text, index=index, public=public, match=match,
        investigate_saved=lambda mid: public(policy.cached(mid, match(mid)["incident_id"]), mid) if policy.cached(mid, match(mid)["incident_id"]) else None,
        investigate_stats=lambda mid: public(investigate(case_for(mid, match(mid)["incident_id"])), mid),
        narrative_en=lambda mid: public(render_narrative(narrative(mid), match(mid), "en"), mid),
        pack_en=lambda mid: public(build_pack(match(mid), localize(timeline(mid), match(mid), "en"),
                                              render_narrative(narrative(mid), match(mid), "en"), "en"), mid))


try:
    from starlette.applications import Starlette

    from server.a2a_agent import MatchAnalystAgent, a2a_routes
    app.mount("/a2a", Starlette(routes=a2a_routes(MatchAnalystAgent(_a2a_answer))))
except ImportError as exc:  # the A2A extra is optional; the rest of the app works without it
    log.warning("A2A endpoint disabled: %s", exc)


if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        file = WEB / path
        return FileResponse(file if path and file.is_file() else WEB / "index.html")
