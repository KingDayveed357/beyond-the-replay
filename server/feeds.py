"""Live ingestion: a data provider pushes synthetic match events as they happen, and every batch runs through
the match pipeline (a Microsoft Agent Framework workflow):

    ingest -> interpret -> explain -> render ---> publish
                                  \\-> narrate -/

  ingest     validates each event (schema, roster, pitch bounds, clock order) and keeps the accepted ones;
  interpret  turns everything received so far into per-minute states, xG, pass difficulty and player stats;
  explain    finds new key moments and why they matter;
  render     emits new overlay cues (name tags, speed/distance alerts, lower thirds) for a graphics engine;
  narrate    updates the storylines, milestones and the story so far;
  publish    pushes only what is new to every live subscriber, in their language, and acknowledges the batch.

Feeds live in memory with hard limits (count, size, lifetime). Each feed has its own write token; reading
is public, like a match centre.
"""
from __future__ import annotations

import asyncio
import hmac
import secrets
import time
from dataclasses import dataclass, field

from agent_framework import Case as Route, Default, Executor, WorkflowBuilder, WorkflowContext, handler

from phase0.engine import PITCH_X, PITCH_Y
from phase0.observe import EVENT_TYPES, OBSERVABLE_FIELDS

MAX_FEEDS = 24
MAX_EVENTS = 4000
MAX_BATCH = 500
FEED_TTL_S = 3 * 3600
MATCH_END_S = 100 * 60


class FeedError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass
class Feed:
    id: str
    token: str
    match: dict                     # home, away, names, roster, metadata, events (accepted so far)
    source: str
    created: float = field(default_factory=time.time)
    timeline: dict | None = None
    narrative: dict | None = None
    sent: dict = field(default_factory=lambda: {"events": 0, "minute": 0, "moments": set(), "cues": set(),
                                                "storylines": {}, "milestones": set(), "summaries": set()})
    subscribers: list = field(default_factory=list)   # (queue, lang)
    stats: dict = field(default_factory=lambda: {"batches": 0, "accepted": 0, "rejected": 0, "last_stage_ms": {}})
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    finished: bool = False

    def summary(self) -> dict:
        m, tl = self.match, self.timeline
        last = tl["states"][-1] if tl and tl["states"] else None
        return {"feed_id": self.id, "source": self.source, "home": m["home"], "away": m["away"],
                "home_name": m["home_name"], "away_name": m["away_name"], "metadata": m.get("metadata", {}),
                "events": len(m["events"]), "minute": last["minute"] if last else 0,
                "score": {t: (last["teams"][t]["goals"] if last else 0) for t in (m["home"], m["away"])},
                "finished": self.finished, "stats": self.stats, "subscribers": len(self.subscribers),
                "age_s": round(time.time() - self.created)}


# ---------- validation ----------

def validate_create(body: dict) -> dict:
    """A new feed's match sheet: two teams and a roster. Returns the internal match dict."""
    if not isinstance(body, dict):
        raise FeedError(400, "bad_request", "Body must be a JSON object.")
    teams = {}
    for side in ("home", "away"):
        t = body.get(side)
        if not isinstance(t, dict) or not isinstance(t.get("code"), str) or not (2 <= len(t["code"]) <= 4) \
                or not t["code"].isalnum() or not isinstance(t.get("name"), str) or not t["name"].strip():
            raise FeedError(400, "bad_team", f"'{side}' needs a code (2-4 letters or digits) and a name.")
        teams[side] = {"code": t["code"].upper(), "name": t["name"].strip()[:40],
                       "colours": [c for c in t.get("colours", []) if isinstance(c, str) and c.startswith("#")][:2]}
    if teams["home"]["code"] == teams["away"]["code"]:
        raise FeedError(400, "bad_team", "Home and away need different codes.")
    roster = body.get("roster")
    if not isinstance(roster, dict) or not roster or len(roster) > 60:
        raise FeedError(400, "bad_roster", "'roster' must map 1-60 player ids to {team, role, name}.")
    clean = {}
    codes = {teams["home"]["code"], teams["away"]["code"]}
    for pid, p in roster.items():
        if not isinstance(pid, str) or not (1 <= len(pid) <= 32) or not isinstance(p, dict) \
                or p.get("team") not in codes or not isinstance(p.get("name"), str):
            raise FeedError(400, "bad_roster", f"Roster entry {pid!r} needs team (one of {sorted(codes)}) and name.")
        clean[pid] = {"team": p["team"], "role": str(p.get("role", ""))[:8], "name": p["name"][:40]}
    meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
    meta = {k: meta[k] for k in ("competition", "venue", "kickoff", "referee", "matchweek", "attendance") if k in meta}
    home, away = teams["home"]["code"], teams["away"]["code"]
    colours = {t["code"]: t["colours"] for t in teams.values() if len(t["colours"]) == 2}
    return {"home": home, "away": away, "home_name": teams["home"]["name"], "away_name": teams["away"]["name"],
            "roster": clean, "events": [], "synthetic": True,
            "metadata": meta | {"simulated": True, **({"colours": colours} if colours else {})}}


def validate_event(e, match: dict, seen: set, last_t: float) -> str | None:
    """None if the event is acceptable, else the reason it was rejected."""
    if not isinstance(e, dict):
        return "not an object"
    missing = [k for k in OBSERVABLE_FIELDS if k not in e]
    if missing:
        return f"missing {', '.join(missing)}"
    extra = set(e) - set(OBSERVABLE_FIELDS)
    if extra:
        return f"unexpected fields {', '.join(sorted(extra))}"
    if not isinstance(e["id"], str) or not (1 <= len(e["id"]) <= 32):
        return "id must be a string of 1-32 characters"
    if e["id"] in seen:
        return "duplicate id"
    if not isinstance(e["t"], (int, float)) or not (0 <= e["t"] <= MATCH_END_S):
        return "t must be seconds from kick-off (0-6000)"
    if e["t"] < last_t:
        return f"out of order: t={e['t']} is before the last accepted event (t={last_t})"
    if e["team"] not in (match["home"], match["away"]):
        return f"unknown team {e['team']!r}"
    roster = match["roster"]
    if e["player_id"] not in roster:
        return f"unknown player {e['player_id']!r}"
    if roster[e["player_id"]]["team"] != e["team"]:
        return f"{e['player_id']} does not play for {e['team']}"
    if e["type"] not in EVENT_TYPES:
        return f"unknown type {e['type']!r}"
    if not isinstance(e["outcome"], str):
        return "outcome must be a string"
    for ref in ("opponent_id", "receiver_id"):
        if e[ref] is not None and e[ref] not in roster:
            return f"unknown {ref} {e[ref]!r}"
    for x, y in (("x", "y"), ("end_x", "end_y")):
        if x == "end_x" and e[x] is None and e[y] is None:
            continue
        if not isinstance(e[x], (int, float)) or not isinstance(e[y], (int, float)) \
                or not (0 <= e[x] <= PITCH_X and 0 <= e[y] <= PITCH_Y):
            return f"{x}/{y} must be on the pitch (0-{PITCH_X:g} by 0-{PITCH_Y:g} metres)"
    if not isinstance(e["under_pressure"], bool):
        return "under_pressure must be true or false"
    if e["speed_kmh"] is not None and not (isinstance(e["speed_kmh"], (int, float)) and 0 <= e["speed_kmh"] <= 200):
        return "speed_kmh must be 0-200 or null"
    if e["possession_id"] is not None and not isinstance(e["possession_id"], str):
        return "possession_id must be a string or null"
    return None


# ---------- the match pipeline (Microsoft Agent Framework) ----------

@dataclass
class Batch:
    feed: Feed
    events: list
    service: "FeedService"
    final: bool = False
    accepted: int = 0
    rejected: list = field(default_factory=list)
    new: dict = field(default_factory=dict)
    stage_ms: dict = field(default_factory=dict)

    def __deepcopy__(self, memo):  # holds the live feed (locks, subscriber queues): see orchestration.Job
        return self

    def timed(self, stage: str, started: float) -> None:
        self.stage_ms[stage] = round((time.perf_counter() - started) * 1000, 1)


class Ingest(Executor):
    @handler
    async def ingest(self, b: Batch, ctx: WorkflowContext[Batch]) -> None:
        t0 = time.perf_counter()
        m = b.feed.match
        seen = {e["id"] for e in m["events"]}
        last_t = m["events"][-1]["t"] if m["events"] else 0.0
        room = MAX_EVENTS - len(m["events"])
        for i, e in enumerate(b.events):
            reason = "feed is full" if room <= 0 else validate_event(e, m, seen, last_t)
            if reason:
                b.rejected.append({"index": i, "id": e.get("id") if isinstance(e, dict) else None, "reason": reason})
                continue
            m["events"].append({k: e[k] for k in OBSERVABLE_FIELDS})
            seen.add(e["id"])
            last_t, room, b.accepted = e["t"], room - 1, b.accepted + 1
        b.timed("ingest", t0)
        await ctx.send_message(b)


class Interpret(Executor):
    @handler
    async def interpret(self, b: Batch, ctx: WorkflowContext[Batch]) -> None:
        t0 = time.perf_counter()
        f = b.feed
        m = f.match | {"names": {f.match["home"]: f.match["home_name"], f.match["away"]: f.match["away_name"]}}
        f.timeline = await asyncio.to_thread(b.service.build_timeline, m)
        b.timed("interpret", t0)
        await ctx.send_message(b)


class Explain(Executor):
    @handler
    async def explain(self, b: Batch, ctx: WorkflowContext[Batch]) -> None:
        t0 = time.perf_counter()
        sent = b.feed.sent["moments"]
        b.new["moments"] = [i for i, x in enumerate(b.feed.timeline["moments"]) if _key(x) not in sent]
        b.timed("explain", t0)
        await ctx.send_message(b)


class Render(Executor):
    @handler
    async def render(self, b: Batch, ctx: WorkflowContext[Batch]) -> None:
        t0 = time.perf_counter()
        sent = b.feed.sent["cues"]
        b.new["cues"] = [i for i, c in enumerate(b.feed.timeline["cues"]) if _cue_key(c) not in sent]
        b.timed("render", t0)
        await ctx.send_message(b)


class Narrate(Executor):
    @handler
    async def narrate(self, b: Batch, ctx: WorkflowContext[Batch]) -> None:
        t0 = time.perf_counter()
        from analytics.narrative import build_narrative
        f = b.feed
        f.narrative = await asyncio.to_thread(build_narrative, f.match, f.timeline, None, b.final)
        b.timed("narrate", t0)
        await ctx.send_message(b)


class Publish(Executor):
    @handler
    async def publish_all(self, batches: list[Batch], ctx: WorkflowContext[None, dict]) -> None:
        await self._publish(batches[0], ctx)

    @handler
    async def publish_one(self, b: Batch, ctx: WorkflowContext[None, dict]) -> None:  # nothing accepted: just acknowledge
        await self._publish(b, ctx)

    async def _publish(self, b: Batch, ctx) -> None:
        t0 = time.perf_counter()
        f = b.feed
        f.stats["batches"] += 1
        f.stats["accepted"] += b.accepted
        f.stats["rejected"] += len(b.rejected)
        if b.accepted or b.final:
            await b.service.broadcast(f, b)
        b.timed("publish", t0)
        f.stats["last_stage_ms"] = b.stage_ms
        await ctx.yield_output({"feed_id": f.id, "accepted": b.accepted, "rejected": b.rejected[:50],
                                "rejected_count": len(b.rejected), "events_total": len(f.match["events"]),
                                "stage_ms": b.stage_ms, "pipeline": PIPELINE["executors"]})


PIPELINE = {
    "framework": "Microsoft Agent Framework", "workflow": "match-pipeline",
    "executors": ["ingest", "interpret", "explain", "render", "narrate", "publish"],
    "edges": [["ingest", "interpret", "events accepted"], ["ingest", "publish", "nothing accepted"],
              ["interpret", "explain"], ["explain", "render"], ["explain", "narrate"],
              ["render", "publish"], ["narrate", "publish"]],
}


def build_pipeline():
    ingest, interpret, explain = Ingest("ingest"), Interpret("interpret"), Explain("explain")
    render, narrate, publish = Render("render"), Narrate("narrate"), Publish("publish")
    return (WorkflowBuilder(start_executor=ingest, name="match-pipeline",
                            description="Ingest, interpret, explain, render and narrate synthetic match events")
            .add_switch_case_edge_group(ingest, [Route(condition=lambda b: b.accepted > 0 or b.final, target=interpret),
                                                 Default(target=publish)])
            .add_edge(interpret, explain)
            .add_fan_out_edges(explain, [render, narrate])
            .add_fan_in_edges([render, narrate], publish)
            .build())


def _key(m: dict) -> tuple:
    return (m["type"], round(m["t"], 1), m.get("player_id"), m.get("team"))


def _cue_key(c: dict) -> tuple:
    return (c["kind"], round(c["t_in"], 1), c.get("player_id"), c.get("metric"))


# ---------- the service ----------

class FeedService:
    def __init__(self, build_timeline, localize):
        """build_timeline(match) -> timeline; localize(match, timeline, narrative, lang) -> (timeline, narrative)
        in the viewer's language with public names."""
        self.build_timeline = build_timeline
        self.localize = localize
        self.feeds: dict[str, Feed] = {}

    def _expire(self) -> None:
        now = time.time()
        for fid in [k for k, f in self.feeds.items() if now - f.created > FEED_TTL_S]:
            self.feeds.pop(fid, None)

    def create(self, match: dict, source: str) -> Feed:
        self._expire()
        if len(self.feeds) >= MAX_FEEDS:
            oldest = min(self.feeds.values(), key=lambda f: f.created)
            if time.time() - oldest.created < 600:
                raise FeedError(429, "too_many_feeds", "The server is hosting too many live feeds. Try again shortly.")
            self.feeds.pop(oldest.id)
        fid = "f" + secrets.token_hex(5)
        feed = Feed(fid, secrets.token_urlsafe(24), match, source)
        self.feeds[fid] = feed
        return feed

    def get(self, fid: str) -> Feed:
        feed = self.feeds.get(fid)
        if feed is None:
            raise FeedError(404, "unknown_feed", f"No live feed {fid!r} (feeds expire after {FEED_TTL_S // 3600} hours).")
        return feed

    def authorise(self, feed: Feed, authorization: str | None) -> None:
        token = (authorization or "").removeprefix("Bearer ").strip()
        if not token or not hmac.compare_digest(token, feed.token):
            raise FeedError(401, "bad_token", "This feed needs its write token: Authorization: Bearer <token>.")

    async def ingest(self, feed: Feed, events, final: bool = False) -> dict:
        if not isinstance(events, list) or len(events) > MAX_BATCH:
            raise FeedError(400, "bad_batch", f"'events' must be a list of at most {MAX_BATCH} events.")
        if feed.finished:
            raise FeedError(409, "finished", "This feed has ended.")
        async with feed.lock:  # one batch at a time per feed, in arrival order
            result = await build_pipeline().run(Batch(feed, events, self, final))
            if final:
                feed.finished = True
            return result.get_outputs()[0]

    def subscribe(self, feed: Feed, lang: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        feed.subscribers.append((q, lang))
        return q

    def unsubscribe(self, feed: Feed, q: asyncio.Queue) -> None:
        feed.subscribers[:] = [(x, lang) for x, lang in feed.subscribers if x is not q]

    def snapshot(self, feed: Feed, lang: str) -> dict:
        tl, nar = (feed.timeline, feed.narrative) if feed.timeline else ({"events": [], "states": [], "moments": [], "cues": [], "players": {}}, None)
        tl, nar = self.localize(feed.match, tl, nar, lang) if feed.timeline else (tl, nar)
        sheet = {k: feed.match[k] for k in ("home", "away", "home_name", "away_name", "roster", "metadata")}
        return {"summary": feed.summary(), "sheet": sheet, "timeline": tl, "narrative": nar}

    async def broadcast(self, feed: Feed, b: Batch) -> None:
        tl, sent = feed.timeline, feed.sent
        new_events = list(range(sent["events"], len(tl["events"])))
        new_states = [i for i, s in enumerate(tl["states"]) if s["minute"] > sent["minute"]]
        nar = feed.narrative or {"storylines": [], "milestones": [], "summaries": []}
        new_story = [i for i, s in enumerate(nar["storylines"]) if sent["storylines"].get(s["id"]) != len(s["beats"])]
        new_miles = [i for i, x in enumerate(nar["milestones"]) if (x["key"]) not in sent["milestones"]]
        new_sums = [i for i, x in enumerate(nar["summaries"]) if x["key"] not in sent["summaries"]]
        langs = {lang for _, lang in feed.subscribers}
        views = {lang: self.localize(feed.match, tl, nar, lang) for lang in langs}
        for q, lang in list(feed.subscribers):
            ltl, lnar = views[lang]
            msgs = [("event", ltl["events"][i]) for i in new_events] + [("state", ltl["states"][i]) for i in new_states]
            msgs += [("moment", ltl["moments"][i]) for i in b.new.get("moments", [])]
            msgs += [("cue", ltl["cues"][i]) for i in b.new.get("cues", [])]
            msgs += [("storyline", lnar["storylines"][i]) for i in new_story]
            msgs += [("milestone", lnar["milestones"][i]) for i in new_miles]
            msgs += [("summary", lnar["summaries"][i]) for i in new_sums]
            msgs.append(("ingest", {"accepted": b.accepted, "rejected": len(b.rejected), "stage_ms": b.stage_ms,
                                    "summary": feed.summary()}))
            if b.final:
                msgs.append(("phase", {"phase": "full_time"}))
            for kind, payload in msgs:
                try:
                    q.put_nowait((kind, payload))
                except asyncio.QueueFull:  # a stalled viewer must not hold up the feed
                    self.unsubscribe(feed, q)
                    break
        sent["events"] = len(tl["events"])
        sent["minute"] = max([s["minute"] for s in tl["states"]] or [0])
        sent["moments"] |= {_key(tl["moments"][i]) for i in b.new.get("moments", [])}
        sent["cues"] |= {_cue_key(tl["cues"][i]) for i in b.new.get("cues", [])}
        sent["storylines"] = {s["id"]: len(s["beats"]) for s in nar["storylines"]}
        sent["milestones"] |= {x["key"] for x in nar["milestones"]}
        sent["summaries"] |= {x["key"] for x in nar["summaries"]}

