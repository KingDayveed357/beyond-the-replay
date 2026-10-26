"""Plain-language names for players, lanes and minutes, derived from public line-ups only."""
from __future__ import annotations

from phase0.engine import CLUBS, role_of, team_of

ROLE_NAMES = {
    "GK": "goalkeeper", "RB": "right-back", "LB": "left-back", "CB1": "centre-back", "CB2": "centre-back",
    "DM": "defensive midfielder", "CMR": "right-sided midfielder", "CML": "left-sided midfielder",
    "RW": "right winger", "ST": "striker", "LW": "left winger",
}


def club(team: str) -> str:
    return CLUBS.get(team, team)


def player(roster: dict, player_id: str) -> str:
    return roster[player_id]["name"] if player_id in roster else player_id


def player_long(roster: dict, player_id: str) -> str:
    return f"{player(roster, player_id)}, {club(team_of(player_id))}'s {ROLE_NAMES[role_of(player_id)]}"


def minute(t: float) -> str:
    return f"{int(t // 60) + 1}'"


def flank(team: str, lane: str) -> str:
    if lane == "center":
        return f"the middle for {club(team)}"
    return f"{club(team)}'s {lane} flank"
