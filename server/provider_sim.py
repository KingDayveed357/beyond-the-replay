"""A simulated data provider: kicks off a brand-new synthetic match and pushes its events into a live feed on a
clock, through the same validation and pipeline as any external provider (see scripts/feed_simulator.py for
the same thing over HTTP)."""
from __future__ import annotations

import asyncio
import logging
import random

from phase0.engine import make_config, metadata, roster, simulate
from phase0.observe import project

log = logging.getLogger("btr")
DEMO_SEEDS = (700_001, 799_999)  # disjoint from development, held-out and showcase seeds


def new_match(seed: int | None = None) -> tuple[dict, list]:
    """A match sheet (the POST /api/feeds body) and the observable events of a never-seen synthetic match."""
    seed = seed if seed is not None else random.randint(*DEMO_SEEDS)
    cfg = make_config(seed)
    meta = metadata(cfg)
    names = meta.get("club_names", {})
    colours = meta.get("colours", {})
    sheet = {
        "home": {"code": cfg.home, "name": names.get(cfg.home, cfg.home), "colours": colours.get(cfg.home, [])},
        "away": {"code": cfg.away, "name": names.get(cfg.away, cfg.away), "colours": colours.get(cfg.away, [])},
        "roster": roster(cfg),
        "metadata": {k: meta[k] for k in ("competition", "venue", "kickoff", "referee", "matchweek", "attendance") if k in meta},
    }
    return sheet, project(simulate(cfg).events)


async def stream_match(feeds, feed, events: list, speed: float) -> None:
    """Deliver events in one batch per real second, each holding the match seconds that elapsed."""
    i, clock = 0, 0.0
    try:
        while i < len(events):
            clock += speed
            batch = []
            while i < len(events) and events[i]["t"] <= clock:
                batch.append(events[i])
                i += 1
            await feeds.ingest(feed, batch, final=i >= len(events))
            if i < len(events):
                await asyncio.sleep(1.0)
    except Exception as exc:  # the feed expired or the server is shutting down: stop quietly
        log.info("demo feed %s stopped: %s", feed.id, exc)
