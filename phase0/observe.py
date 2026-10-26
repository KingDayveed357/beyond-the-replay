"""The observation boundary: the only match data investigators are allowed to see."""
from __future__ import annotations

from dataclasses import dataclass

from .engine import PITCH_X, PITCH_Y, lane_of

OBSERVABLE_FIELDS = (
    "id", "t", "team", "player_id", "type", "outcome", "x", "y",
    "end_x", "end_y", "opponent_id", "receiver_id", "possession_id", "under_pressure", "speed_kmh",
)
EVENT_TYPES = {"pass", "carry", "dribble", "cross", "shot", "foul", "card", "tackle", "interception", "clearance"}
# Words that would only appear if hidden simulation state leaked into the observable stream.
HIDDEN_TERMS = ("fatigue", "overload", "magnitude", "rating", "weak", "decoy", "factor", "onset", "stamina")


class SchemaError(ValueError):
    pass


@dataclass
class Case:
    case_id: str
    home: str
    away: str
    roster: dict      # public line-ups
    events: list      # observable events only
    incident_id: str  # the goal under investigation


def project(events: list) -> list:
    return [{k: e.get(k) for k in OBSERVABLE_FIELDS} for e in events]


def event_lane(e: dict, home: str) -> str:
    """Lane of an event from the acting team's attacking point of view."""
    return lane_of(e["y"], e["team"] == home)


def validate_events(events: list, roster: dict) -> None:
    errors = []
    seen = set()
    last_t = -1.0
    for e in events:
        missing = [k for k in OBSERVABLE_FIELDS if k not in e]
        if missing:
            errors.append(f"{e.get('id', '?')}: missing {missing}")
            continue
        extra = set(e) - set(OBSERVABLE_FIELDS)
        if extra:
            errors.append(f"{e['id']}: unexpected fields {sorted(extra)}")
        if e["id"] in seen:
            errors.append(f"{e['id']}: duplicate id")
        seen.add(e["id"])
        if e["type"] not in EVENT_TYPES:
            errors.append(f"{e['id']}: unknown type {e['type']!r}")
        if not isinstance(e["t"], (int, float)) or e["t"] < last_t:
            errors.append(f"{e['id']}: time out of order")
        else:
            last_t = e["t"]
        if e["player_id"] not in roster:
            errors.append(f"{e['id']}: unknown player {e['player_id']!r}")
        elif roster[e["player_id"]]["team"] != e["team"]:
            errors.append(f"{e['id']}: player {e['player_id']} does not play for {e['team']}")
        for ref in ("opponent_id", "receiver_id"):
            if e[ref] is not None and e[ref] not in roster:
                errors.append(f"{e['id']}: unknown {ref} {e[ref]!r}")
        if not (0 <= e["x"] <= PITCH_X and 0 <= e["y"] <= PITCH_Y):
            errors.append(f"{e['id']}: off the pitch")
    if errors:
        raise SchemaError("; ".join(errors[:10]))
