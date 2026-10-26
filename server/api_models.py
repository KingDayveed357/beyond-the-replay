"""Request and response models for the ingestion API: they power the interactive reference at /docs.

Batches are validated event by event (server/feeds.py): one bad event comes back with a reason instead of
failing the whole batch. So `EventBatch.events` accepts any object, while the documented item type is `Event`.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal["pass", "carry", "dribble", "cross", "shot", "foul", "card", "tackle", "interception", "clearance"]

EXAMPLE_EVENT = {
    "id": "e00000", "t": 7.5, "team": "SBR", "player_id": "SBR-RW", "type": "pass", "outcome": "success",
    "x": 52.5, "y": 6.9, "end_x": 65.6, "end_y": 17.3, "opponent_id": None, "receiver_id": "SBR-CMR",
    "possession_id": "p0000", "under_pressure": False, "speed_kmh": 54.0,
}


class Team(BaseModel):
    code: str = Field(description="2-4 letters or digits, unique in the match", examples=["SBR"])
    name: str = Field(description="Display name, up to 40 characters", examples=["Seabright Albion"])
    colours: list[str] = Field(default=[], description="Up to two hex colours: primary, secondary", examples=[["#0057B8", "#FFFFFF"]])


class Player(BaseModel):
    team: str = Field(description="One of the two team codes", examples=["SBR"])
    name: str = Field(examples=["Kofi Ashby"])
    role: str = Field(default="", description="GK, RB, CB1, CB2, LB, DM, CMR, CML, RW, ST or LW. Full-back roles (RB, LB) "
                                                "power the 'is he tiring?' and flank storylines.", examples=["RW"])


class MatchMetadata(BaseModel):
    competition: str | None = None
    venue: str | None = None
    kickoff: str | None = Field(default=None, examples=["Sat 15:00"])
    referee: str | None = None
    matchweek: int | None = None
    attendance: int | None = None


class MatchSheet(BaseModel):
    """Who is playing. Send once, when you open the feed."""
    home: Team
    away: Team
    roster: dict[str, Player] = Field(description="Player id -> player. Ids are yours; events refer to them.")
    metadata: MatchMetadata = MatchMetadata()

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "home": {"code": "SBR", "name": "Seabright Albion", "colours": ["#0057B8", "#FFFFFF"]},
        "away": {"code": "HLD", "name": "Halden Town", "colours": ["#241F20", "#FFFFFF"]},
        "roster": {"SBR-RW": {"team": "SBR", "role": "RW", "name": "Kofi Ashby"},
                   "SBR-CMR": {"team": "SBR", "role": "CMR", "name": "Leon Marby"},
                   "HLD-LB": {"team": "HLD", "role": "LB", "name": "Nils Grieve"}},
        "metadata": {"venue": "The Pavilion", "kickoff": "Sat 15:00"}}]})


class Event(BaseModel):
    """One thing that happened on the pitch. Coordinates are metres on a 105 x 68 pitch; the home side attacks
    towards x = 105, the away side towards x = 0. Every field is required; use null where it doesn't apply."""
    id: str = Field(description="Unique within the feed, 1-32 characters")
    t: float = Field(ge=0, le=6000, description="Seconds since kick-off. Must not go backwards.")
    team: str = Field(description="Team code of the player who acted")
    player_id: str = Field(description="Roster id of the player who acted")
    type: EventType
    outcome: str = Field(description="success or fail for actions; goal, saved or off_target for shots")
    x: float = Field(ge=0, le=105, description="Where it started (metres)")
    y: float = Field(ge=0, le=68)
    end_x: float | None = Field(ge=0, le=105, description="Where the ball or player ended up, or null")
    end_y: float | None = Field(ge=0, le=68)
    opponent_id: str | None = Field(description="The opponent involved (duel, tackle, interception), or null")
    receiver_id: str | None = Field(description="Intended receiver of a pass or cross, or null")
    possession_id: str | None = Field(description="Groups events of one spell of possession, or null")
    under_pressure: bool
    speed_kmh: float | None = Field(ge=0, le=200, description="Ball speed for passes and shots, running speed for carries and dribbles")

    model_config = ConfigDict(extra="forbid", strict=True, json_schema_extra={"examples": [EXAMPLE_EVENT]})


class EventBatch(BaseModel):
    """Events in clock order. Send one batch every second or so while the match is live."""
    events: list[Event | dict[str, Any]] = Field(max_length=500, description="Up to 500 events, each an `Event`. "
                                                 "Invalid ones are rejected individually, with a reason.")
    final: bool = Field(default=False, description="true on the last batch: full-time. The feed then closes.")

    model_config = ConfigDict(json_schema_extra={"examples": [{"events": [EXAMPLE_EVENT], "final": False}]})

    def raw_events(self) -> list:
        return [e.model_dump() if isinstance(e, Event) else e for e in self.events]


class Limits(BaseModel):
    max_batch: int
    max_events: int


class FeedCreated(BaseModel):
    feed_id: str = Field(examples=["fa691ac6736"])
    write_token: str = Field(description="Shown once. Send it as `Authorization: Bearer <write_token>` when pushing events.")
    events_url: str = Field(examples=["/api/feeds/fa691ac6736/events"])
    live_url: str = Field(description="Server-sent events stream for viewers", examples=["/api/feeds/fa691ac6736/live"])
    limits: Limits


class Rejection(BaseModel):
    index: int = Field(description="Position of the event in your batch")
    id: str | None
    reason: str = Field(examples=["x/y must be on the pitch (0-105 by 0-68 metres)"])


class IngestAck(BaseModel):
    feed_id: str
    accepted: int = Field(description="Events added to the match")
    rejected: list[Rejection] = Field(description="First 50 rejected events, with reasons")
    rejected_count: int
    events_total: int = Field(description="Events accepted so far in this feed")
    stage_ms: dict[str, float] = Field(description="Time spent in each pipeline stage for this batch")
    pipeline: list[str] = Field(examples=[["ingest", "interpret", "explain", "render", "narrate", "publish"]])


class ApiError(BaseModel):
    detail: dict[str, str] = Field(examples=[{"code": "bad_token", "message": "This feed needs its write token."}])
